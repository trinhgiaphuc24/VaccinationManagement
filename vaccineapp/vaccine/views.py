import uuid
from threading import activeCount

from django.core.mail import send_mail
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse
from django.db.models import Count
from rest_framework.filters import OrderingFilter
from rest_framework.views import APIView
from settings import IP_URL_VIEW
from vaccine.models import *
from vaccine import serializers, paginators, perms
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from vaccine.serializers import VaccineTypeSerializer, UserRegisterSerializer, InformationSerializer, AppointmentSerializer, AppointmentReadSerializer, AppointmentDetailReadSerializer, AttendantCommunicationSerializer, CommunicationVaccinationSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets, generics, permissions, parsers, status
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ViewSet, generics.CreateAPIView):
    queryset = User.objects.filter(is_active=True)
    serializer_class = serializers.UserSerializer
    parser_classes = [parsers.MultiPartParser]

    @action(methods=['GET', 'PUT'], url_path='current-user', detail=False, permission_classes=[permissions.IsAuthenticated])
    def current_user(self, request):
        user = request.user
        if request.method == 'GET':
            return Response(serializers.UserSerializer(user).data)
        elif request.method == 'PUT':
            serializer = self.get_serializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RegisterViewSet(viewsets.ViewSet):
    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        user = request.user
        data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": getattr(user, 'phone_number', ""),
            "email": user.email,
        }
        return Response(data)


class VaccineViewSet(viewsets.ViewSet, generics.ListAPIView, generics.RetrieveAPIView):
    queryset = Vaccine.objects.filter(active=True).select_related('vaccine_type', 'country_produce')
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.VaccineSerializer
    pagination_class = paginators.VaccinePagination
    filter_backends = [OrderingFilter]
    ordering_fields = ['id', 'price', 'name', 'vaccine_type__name', 'country_produce__name']
    ordering = ['id']

    def get_queryset(self):
        queryset = self.queryset

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(description__icontains=q))

        vaccine_type_id = self.request.query_params.get('vaccine_type_id')
        if vaccine_type_id:
            queryset = queryset.filter(vaccine_type_id=vaccine_type_id)

        country_produce_id = self.request.query_params.get('country_produce_id')
        if country_produce_id:
            queryset = queryset.filter(country_produce_id=country_produce_id)

        return queryset

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class VaccineTypeViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = VaccineType.objects.filter(active=True)
    permission_classes = [IsAuthenticated]
    serializer_class = VaccineTypeSerializer


class HealthCenterViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = HealthCenter.objects.filter(active=True)
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.HealthCenterSerializer
    pagination_class = paginators.HealthCenterPagination


class TimeViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = Time.objects.filter(active=True)
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.TimeSerializer
    pagination_class = paginators.TimePagination


class InformationViewSet(viewsets.ViewSet, generics.ListAPIView,generics.RetrieveAPIView,generics.CreateAPIView,generics.UpdateAPIView):
    queryset = Information.objects.filter()
    serializer_class = InformationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset.filter(user=self.request.user)
        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(phone_number__icontains=q)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        instance.delete()


class AppointmentViewSet(viewsets.ViewSet,generics.ListAPIView,generics.RetrieveAPIView,generics.CreateAPIView,generics.UpdateAPIView):
    queryset = Appointment.objects.select_related('information', 'health_centre', 'time').prefetch_related('appointment_details__vaccine')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ['id', 'created_at', 'status', 'health_centre__name']
    ordering = ['created_at']



    def get_queryset(self):
        queryset = Appointment.objects.select_related('information', 'health_centre', 'time').prefetch_related('appointment_details__vaccine')
        if self.request.user.userRole == "staff":
            return queryset

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(
                Q(information__first_name__icontains=q) |
                Q(information__last_name__icontains=q) |
                Q(information__phone_number__icontains=q) |
                Q(id__icontains=q)
            )
        date = self.request.query_params.get('date')
        if date:
            parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
            queryset = queryset.filter(created_at__date=parsed_date)
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        return queryset


    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        # ppointmentReadSerializer trả về dữ liệu chi tiết sau khi tạo
        response_serializer = AppointmentReadSerializer(serializer.instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                serializer.save()
                instance.refresh_from_db()

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = AppointmentReadSerializer(instance)
        return Response(response_serializer.data)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='details')
    def get_appointment_details(self, request, pk=None):
        appointment = self.get_object()
        details = AppointmentDetail.objects.filter(appointment=appointment).select_related('vaccine')
        serializer = AppointmentDetailReadSerializer(details, many=True)
        return Response(serializer.data)

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve', 'get_appointment_details']:
            return AppointmentReadSerializer
        return AppointmentSerializer


@csrf_exempt
def send_email(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            to_email = data.get('to')
            subject = data.get('subject')
            body = data.get('body')

            if not all([to_email, subject, body]):
                return JsonResponse({'error': 'Missing required fields'}, status=400)

            send_mail(
                subject,
                body,
                'trinhgiaphuc24@gmail.com',
                [to_email],
                fail_silently=False,
            )
            return JsonResponse({'message': 'Email sent successfully'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid method'}, status=405)


class CommunicationVaccinationViewSet(viewsets.ViewSet,generics.ListAPIView,generics.RetrieveAPIView,generics.CreateAPIView,generics.UpdateAPIView):
    queryset = CommunicationVaccination.objects.filter(active=True)
    serializer_class = CommunicationVaccinationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ['id', 'name']
    ordering = ['id']

    def get_queryset(self):
        queryset = self.queryset
        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(address__icontains=q))
        return queryset

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_empty_patient(self, request, pk=None):
            communication = self.get_object()
            new_empty_patient = request.data.get('emptyPatient')
            communication.emptyPatient = new_empty_patient
            communication.save()
            return Response(
                CommunicationVaccinationSerializer(communication).data,
                status=status.HTTP_200_OK
            )

    @action(detail=True, methods=['patch'], url_path='update-empty-staff')
    def update_empty_staff(self, request, pk=None):
            communication = self.get_object()
            empty_staff = request.data.get('emptyStaff')
            communication.emptyStaff = empty_staff
            communication.save()
            return Response({"message": "Updated emptyStaff successfully"}, status=status.HTTP_200_OK)



class AttendantCommunicationViewSet(viewsets.ViewSet, generics.ListAPIView, generics.CreateAPIView, generics.DestroyAPIView):
    queryset = AttendantCommunication.objects.all()
    serializer_class = AttendantCommunicationSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def register(self, request):
        user = request.user
        communication_id = request.data.get('communication')
        quantity = request.data.get('quantity')
        registration_type = request.data.get('registration_type', 'patient')
        communication = CommunicationVaccination.objects.get(id=communication_id)

        attendant = AttendantCommunication.objects.create(
            user=user,
            communication=communication,
            quantity=quantity,
            registration_type=registration_type
        )

        if registration_type == 'patient':
            communication.emptyPatient -= int(quantity)
        else:
            communication.emptyStaff -= int(quantity)
        communication.save()

        return Response(
            AttendantCommunicationSerializer(attendant).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['get'], url_path='check-registration/(?P<communication_id>\d+)')
    def check_registration(self, request, communication_id=None):
        user = request.user
        registration_type = request.query_params.get('registration_type', 'patient')

        communication = CommunicationVaccination.objects.get(id=communication_id)
        is_registered = AttendantCommunication.objects.filter(
            user=user,
            communication=communication,
            registration_type=registration_type
        ).exists()
        return Response(
            {"is_registered": is_registered},
            status=status.HTTP_200_OK
        )


    @action(detail=False, methods=['post'], url_path='cancel-registration')
    def cancel_registration(self, request):
        user = request.user
        communication_id = request.data.get('communication')
        registration_type = request.data.get('registration_type', 'patient')
        communication = CommunicationVaccination.objects.get(id=communication_id)

        with transaction.atomic():
            try:
                attendant = AttendantCommunication.objects.get(
                    user=user,
                    communication=communication,
                    registration_type=registration_type
                )
                quantity = attendant.quantity

                if registration_type == 'patient':
                    communication.emptyPatient += quantity
                else:
                    communication.emptyStaff += quantity
                communication.save()

                attendant.delete()

                return Response(
                    {"message": "Hủy đăng ký thành công."},
                    status=status.HTTP_200_OK
                )
            except AttendantCommunication.DoesNotExist:
                return Response(
                    {"error": f"Bạn chưa đăng ký chiến dịch này với vai trò {registration_type}."},
                    status=status.HTTP_400_BAD_REQUEST
                )


@method_decorator(csrf_exempt, name='dispatch')
class ChatView(View):
    def post(self, request):
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                user_message = data.get('message')
                session_id = data.get('user_id', str(uuid.uuid4()))
                conversation_history = data.get('conversation_history')
            else:
                user_message = request.POST.get('message')
                session_id = request.POST.get('session_id', str(uuid.uuid4()))
                conversation_history = None

            logger.info(
                f"Nhận yêu cầu POST: message={user_message}, session_id={session_id}, conversation_history={conversation_history}")

            if not user_message:
                logger.warning("Không có message trong yêu cầu POST")
                return JsonResponse({'error': 'Yêu cầu phải có message'}, status=400)

            try:
                rasa_url = IP_URL_VIEW
                payload = {
                    'sender': session_id,
                    'message': user_message
                }
                if conversation_history:
                    payload['metadata'] = {'conversation_history': conversation_history}

                logger.debug(f"Gửi yêu cầu đến Rasa: {payload}")
                response = requests.post(rasa_url, json=payload, timeout=5)
                response.raise_for_status()
                response_data = response.json()

                bot_responses = []
                for item in response_data:
                    if 'text' in item:
                        bot_response = {'text': item['text']}
                        if 'metadata' in item:
                            bot_response['metadata'] = item['metadata']
                        bot_responses.append(bot_response)

                if not bot_responses:
                    logger.warning("Không có phản hồi từ server Rasa")
                    bot_responses = [{'text': 'Xin lỗi, tôi không hiểu. Vui lòng thử lại.'}]

                logger.info(f"Phản hồi bot: {bot_responses}")
                return JsonResponse({'responses': bot_responses})

            except requests.exceptions.ConnectionError as e:
                logger.error(f"Lỗi kết nối đến Rasa: {str(e)}")
                return JsonResponse({'responses': [{'text': 'Xin lỗi, dịch vụ chatbot hiện không khả dụng. Vui lòng liên hệ với chúng tôi qua số điện thoại hoặc email.'}]})
            except requests.exceptions.HTTPError as e:
                logger.error(f"Lỗi HTTP từ Rasa: {str(e)}")
                return JsonResponse({'responses': [
                    {'text': 'Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau hoặc liên hệ đường dây hỗ trợ.'}]})
            except requests.exceptions.Timeout:
                logger.error("Kết nối đến Rasa hết thời gian chờ")
                return JsonResponse(
                    {'responses': [{'text': 'Xin lỗi, hệ thống đang phản hồi chậm. Vui lòng thử lại sau.'}]})

        except json.JSONDecodeError:
            logger.error("Payload JSON không hợp lệ", exc_info=True)
            return JsonResponse({'error': 'Định dạng JSON không hợp lệ'}, status=400)
        except Exception as e:
            logger.error(f"Lỗi bất ngờ: {str(e)}", exc_info=True)
            return JsonResponse(
                {'responses': [{'text': 'Xin lỗi, đã xảy ra lỗi không mong muốn. Vui lòng thử lại sau.'}]}, status=200)


class TotalVaccinatedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        month = request.query_params.get('month')
        quarter = request.query_params.get('quarter')
        year = request.query_params.get('year')

        appointments = Appointment.objects.filter(status='completed')

        if year:
            appointments = appointments.filter(date__year=year)
        if month:
            appointments = appointments.filter(date__month=month)
        if quarter:
            start_month = (int(quarter) - 1) * 3 + 1
            end_month = start_month + 2
            appointments = appointments.filter(date__month__gte=start_month, date__month__lte=end_month)

        total = appointments.count()

        return Response({'total': total})


class CompletionRateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        month = request.query_params.get('month')
        quarter = request.query_params.get('quarter')
        year = request.query_params.get('year')

        total_appointments = Appointment.objects.all()
        completed_appointments = Appointment.objects.filter(status='completed')

        if year:
            total_appointments = total_appointments.filter(date__year=year)
            completed_appointments = completed_appointments.filter(date__year=year)
        if month:
            total_appointments = total_appointments.filter(date__month=month)
            completed_appointments = completed_appointments.filter(date__month=month)
        if quarter:
            start_month = (int(quarter) - 1) * 3 + 1
            end_month = start_month + 2
            total_appointments = total_appointments.filter(date__month__gte=start_month, date__month__lte=end_month)
            completed_appointments = completed_appointments.filter(date__month__gte=start_month,
                                                                   date__month__lte=end_month)

        total_count = total_appointments.count()
        completed_count = completed_appointments.count()
        rate = (completed_count / total_count * 100) if total_count > 0 else 0

        return Response({'rate': rate})


class PopularVaccinesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        month = request.query_params.get('month')
        quarter = request.query_params.get('quarter')
        year = request.query_params.get('year')

        appointments = Appointment.objects.all()

        if year:
            appointments = appointments.filter(date__year=year)
        if month:
            appointments = appointments.filter(date__month=month)
        if quarter:
            start_month = (int(quarter) - 1) * 3 + 1
            end_month = start_month + 2
            appointments = appointments.filter(date__month__gte=start_month, date__month__lte=end_month)

        appointment_ids = appointments.values_list('id', flat=True)
        vaccines = (
            AppointmentDetail.objects.filter(appointment__id__in=appointment_ids)
            .values('vaccine__name')
            .annotate(count=Count('vaccine'))
            .order_by('-count')
        )

        return Response([
            {'vaccine_name': item['vaccine__name'], 'count': item['count']}
            for item in vaccines
        ])