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

from vaccine.perms import IsOwner, IsPatient, IsStaff
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

    @action(methods=['GET', 'PUT'], url_path='current-user', detail=False, permission_classes=[IsAuthenticated, IsOwner])
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
    permission_classes = [IsAuthenticated, IsOwner]

    @action(methods=['get'], detail=False, url_path='profile')
    def get_user_profile(self, request):
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
    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = serializers.VaccineSerializer
    pagination_class = paginators.VaccinePagination
    # filter_backends = [OrderingFilter]

    def get_queryset(self):
        queryset = self.queryset

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(description__icontains=q))

        vaccine_type_id = self.request.query_params.get('vaccine_type_id')
        if vaccine_type_id:
            queryset = queryset.filter(vaccine_type_id=vaccine_type_id)

        return queryset

    @action(detail=False, methods=['get'], url_path='list')
    def get_list_vaccines(self, request):
        vaccines = self.get_object().vaccine_set.filter(active=True)
        return Response(serializers.VaccineSerializer(vaccines, many=True).data, status=status.HTTP_200_OK)


class VaccineTypeViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = VaccineType.objects.filter(active=True)
    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = VaccineTypeSerializer


class HealthCenterViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = HealthCenter.objects.filter(active=True)
    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = serializers.HealthCenterSerializer
    pagination_class = paginators.HealthCenterPagination


class TimeViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = Time.objects.filter(active=True)
    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = serializers.TimeSerializer
    pagination_class = paginators.TimePagination


class InformationViewSet(viewsets.ViewSet,generics.ListAPIView,generics.RetrieveAPIView,generics.CreateAPIView,generics.UpdateAPIView):
    queryset = Information.objects.all()
    serializer_class = InformationSerializer
    permission_classes = [IsAuthenticated, IsOwner]

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

    @action(methods=['post'], detail=False, url_path='create-info', permission_classes= [IsPatient])
    def create_info(self, request):
        data = request.data.copy()
        data['user'] = request.user.id
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(methods=['patch'], detail=True, url_path='update-info', permission_classes= [IsPatient])
    def update_info(self, request, pk=None):
        instance = self.get_object()
        data = request.data.copy()
        data['user'] = request.user.id
        serializer = self.serializer_class(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['delete'], detail=True, url_path='delete-info', permission_classes= [IsPatient])
    def delete_info(self, request, pk=None):
        instance = self.get_object()
        instance.delete()  # Xóa bản ghi
        return Response({"message": "Thông tin đã được xóa thành công."}, status=status.HTTP_204_NO_CONTENT)


class AppointmentViewSet(viewsets.ViewSet,generics.ListAPIView,generics.RetrieveAPIView,generics.CreateAPIView,generics.UpdateAPIView):
    queryset = Appointment.objects.select_related('information', 'health_centre', 'time').prefetch_related('appointment_details__vaccine')
    permission_classes = [IsAuthenticated]

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

        return queryset.filter(information__user=self.request.user)

    @action(methods=['get'], detail=False, url_path='all', permission_classes=[IsOwner])
    def list_appointments(self, request):
        appointments = self.get_queryset()
        return Response(AppointmentReadSerializer(appointments, many=True).data)

    @action(methods=['post'], detail=False, url_path='create-appointment', permission_classes= [IsPatient, IsOwner])
    def create_appointment(self, request):
        serializer = self.get_serializer(data=request.data)
        return Response(AppointmentReadSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)

    @action(methods=['patch'], detail=True, url_path='update-appointment', permission_classes= [IsStaff, IsOwner])
    def update_appointment(self, request, pk=None):
        appointments = self.get_object().appointment_set.filter(active=True)
        return Response(AppointmentSerializer(appointments, many=True).data)

    @action(methods=['get'], detail=True, url_path='details')
    def get_appointment_details(self, request, pk=None):
        details = AppointmentDetail.objects.filter(appointment=self.get_object()).select_related('vaccine')
        return Response(AppointmentDetailReadSerializer(details, many=True).data)


    def get_serializer_class(self):
        if self.action in ['list_appointments', 'get_appointment_details']:
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
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        queryset = self.queryset
        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(address__icontains=q))
        return queryset

    @action(methods=['patch'], detail=True, permission_classes=[IsPatient])
    def update_empty_patient(self, request, pk=None):
            communication = self.get_object()
            new_empty_patient = request.data.get('emptyPatient')
            communication.emptyPatient = new_empty_patient
            communication.save()
            return Response(
                CommunicationVaccinationSerializer(communication).data,
                status=status.HTTP_200_OK
            )

    @action(methods=['patch'], detail=True, url_path='update-empty-staff', permission_classes= [IsStaff])
    def update_empty_staff(self, request, pk=None):
            communication = self.get_object()
            empty_staff = request.data.get('emptyStaff')
            communication.emptyStaff = empty_staff
            communication.save()
            return Response({"message": "Updated emptyStaff successfully"}, status=status.HTTP_200_OK)



class AttendantCommunicationViewSet(viewsets.ViewSet, generics.ListAPIView, generics.CreateAPIView, generics.DestroyAPIView):
    queryset = AttendantCommunication.objects.all()
    serializer_class = AttendantCommunicationSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    @action(methods=['post'], detail=False)
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

    @action(methods=['get'], detail=False, url_path='check-registration/(?P<communication_id>\d+)')
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


    @action(methods=['post'], detail=False, url_path='cancel-registration')
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


class StatisticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsOwner]

    def filter_appointments(self, request, queryset):
        month = request.query_params.get('month')
        quarter = request.query_params.get('quarter')
        year = request.query_params.get('year')

        if year:
            queryset = queryset.filter(date__year=year)
        if month:
            queryset = queryset.filter(date__month=month)
        if quarter:
            start_month = (int(quarter) - 1) * 3 + 1
            end_month = start_month + 2
            queryset = queryset.filter(date__month__gte=start_month, date__month__lte=end_month)

        return queryset

    @action(detail=False, methods=['get'], url_path='total-vaccinated', permission_classes= [IsPatient])
    def total_vaccinated(self, request):
        appointments = self.filter_appointments(request, Appointment.objects.filter(status='completed'))
        total = appointments.count()
        return Response({'total': total})

    @action(detail=False, methods=['get'], url_path='completion-rate', permission_classes= [IsPatient])
    def completion_rate(self, request):
        total_appointments = self.filter_appointments(request, Appointment.objects.all())
        completed_appointments = self.filter_appointments(request, Appointment.objects.filter(status='completed'))

        total_count = total_appointments.count()
        completed_count = completed_appointments.count()

        rate = (completed_count / total_count * 100) if total_count > 0 else 0
        return Response({'rate': rate})

    @action(detail=False, methods=['get'], url_path='popular-vaccines', permission_classes= [IsPatient])
    def popular_vaccines(self, request):
        appointments = self.filter_appointments(request, Appointment.objects.all())
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