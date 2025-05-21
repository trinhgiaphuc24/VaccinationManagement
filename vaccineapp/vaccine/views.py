import uuid

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
from vaccine.models import *
from vaccine import serializers, paginators, perms
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from vaccine.serializers import VaccineTypeSerializer, UserRegisterSerializer, InformationSerializer, \
    AppointmentSerializer, AppointmentReadSerializer, AppointmentDetailReadSerializer, AttendantCommunicationSerializer, \
    CommunicationVaccinationSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets, generics, permissions, parsers, status
import requests
import logging

logger = logging.getLogger(__name__)



class UserViewSet(viewsets.ViewSet, generics.CreateAPIView, generics.UpdateAPIView):
    queryset = User.objects.filter(is_active=True)
    serializer_class = serializers.UserSerializer
    parser_classes = [parsers.MultiPartParser]

    @action(methods=['get'], url_path='current-user', detail=False, permission_classes=[permissions.IsAuthenticated])
    def get_current_user(self, request):
        return Response(serializers.UserSerializer(request.user).data)

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

    def retrieve(self, request, pk=None):
        user = request.user
        if user.id != int(pk):
            return Response({"error": "You can only view your own profile"}, status=status.HTTP_403_FORBIDDEN)
        serializer = UserRegisterSerializer(user)
        return Response(serializer.data)

    def update(self, request, pk=None):
        user = request.user
        if user.id != int(pk):
            return Response({"error": "You can only update your own profile"}, status=status.HTTP_403_FORBIDDEN)
        serializer = UserRegisterSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Profile updated successfully"}, status=status.HTTP_200_OK)
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


class VaccineViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = Vaccine.objects.filter(active=True).select_related('vaccine_type', 'country_produce')
    # permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.VaccineSerializer
    pagination_class = paginators.VaccinePagination
    filter_backends = [OrderingFilter]  # Thêm OrderingFilter
    ordering_fields = ['id', 'price', 'name', 'vaccine_type__name', 'country_produce__name']  # Các trường cho phép sắp xếp
    ordering = ['id']  # Mặc định sắp xếp theo id

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


class VaccineTypeViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = VaccineType.objects.filter(active=True)
    # permission_classes = [permissions.IsAuthenticated]
    serializer_class = VaccineTypeSerializer



class HealthCenterViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = HealthCenter.objects.filter(active=True)
    # permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.HealthCenterSerializer
    pagination_class = paginators.HealthCenterPagination


class TimeViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = Time.objects.filter(active=True)
    # permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.TimeSerializer
    pagination_class = paginators.TimePagination


class InformationViewSet(viewsets.ViewSet, generics.ListAPIView,generics.RetrieveAPIView,generics.CreateAPIView,generics.UpdateAPIView):
    # queryset = Information.objects.all()
    serializer_class = InformationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Chỉ trả về các bản ghi Information của user hiện tại
        return Information.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Gán user hiện tại cho bản ghi mới
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        # Đảm bảo user hiện tại chỉ có thể cập nhật bản ghi của chính họ
        serializer.save(user=self.request.user)

    # def destroy(self, request, *args, **kwargs):
    #     # Xóa bản ghi
    #     instance = self.get_object()
    #     self.perform_destroy(instance)
    #     return Response({"message": "Thông tin đã được xóa thành công"}, status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        instance.delete()


class AppointmentViewSet(viewsets.ViewSet,generics.ListAPIView,generics.RetrieveAPIView,generics.CreateAPIView,generics.UpdateAPIView,generics.DestroyAPIView):
    queryset = Appointment.objects.select_related('information', 'health_centre', 'time').prefetch_related('appointment_details__vaccine')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        # Sử dụng AppointmentReadSerializer cho các hành động đọc
        if self.action in ['list', 'retrieve', 'get_appointment_details']:
            return AppointmentReadSerializer
        # Sử dụng AppointmentSerializer cho các hành động ghi (như create, update)
        return AppointmentSerializer

    def get_queryset(self):
        # logger.debug(f"Current user: {self.request.user.id}, Role: {self.request.user.userRole}")
        queryset = Appointment.objects.select_related('information', 'health_centre', 'time').prefetch_related('appointment_details__vaccine')
        if self.request.user.userRole == "staff":
            return queryset
        return queryset.filter(information__user=self.request.user)
        # print("Current user:", self.request.user.id)
        # return self.queryset.filter(information__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        # Sử dụng AppointmentReadSerializer để trả về dữ liệu chi tiết sau khi tạo
        response_serializer = AppointmentReadSerializer(serializer.instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save()

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

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.refresh_from_db()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='details')
    def get_appointment_details(self, request, pk=None):
        appointment = self.get_object()
        print("Appointment found:", appointment.id)
        details = AppointmentDetail.objects.filter(appointment=appointment).select_related('vaccine')
        print("Details found:", list(details.values()))
        serializer = AppointmentDetailReadSerializer(details, many=True)
        return Response(serializer.data)


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


class TotalVaccinatedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Lấy tham số từ query
        month = request.query_params.get('month')
        quarter = request.query_params.get('quarter')
        year = request.query_params.get('year')

        # Bắt đầu với queryset cơ bản
        appointments = Appointment.objects.filter(status='completed')

        # Áp dụng bộ lọc
        if year:
            appointments = appointments.filter(date__year=year)
        if month:
            appointments = appointments.filter(date__month=month)
        if quarter:
            start_month = (int(quarter) - 1) * 3 + 1
            end_month = start_month + 2
            appointments = appointments.filter(date__month__gte=start_month, date__month__lte=end_month)

        # Đếm tổng số người đã tiêm
        total = appointments.count()

        return Response({'total': total})


class CompletionRateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        month = request.query_params.get('month')
        quarter = request.query_params.get('quarter')
        year = request.query_params.get('year')

        # Lấy tất cả lịch hẹn
        total_appointments = Appointment.objects.all()
        completed_appointments = Appointment.objects.filter(status='completed')

        # Áp dụng bộ lọc
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

        # Tính tỷ lệ hoàn thành
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

        # Lấy tất cả AppointmentDetail và liên kết với Appointment để lọc theo thời gian
        appointments = Appointment.objects.all()

        # Áp dụng bộ lọc thời gian
        if year:
            appointments = appointments.filter(date__year=year)
        if month:
            appointments = appointments.filter(date__month=month)
        if quarter:
            start_month = (int(quarter) - 1) * 3 + 1
            end_month = start_month + 2
            appointments = appointments.filter(date__month__gte=start_month, date__month__lte=end_month)

        # Lấy danh sách vắc-xin từ các AppointmentDetail liên quan
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
            queryset = queryset.filter(Q(name__icontains=q) | Q(description__icontains=q))
        return queryset

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_empty_patient(self, request, pk=None):
        try:
            communication = self.get_object()  # Lấy chiến dịch theo pk (ID)
            new_empty_patient = request.data.get('emptyPatient')

            if new_empty_patient is None:
                return Response(
                    {"error": "emptyPatient is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            communication.emptyPatient = new_empty_patient
            communication.save()
            return Response(
                CommunicationVaccinationSerializer(communication).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['patch'], url_path='update-empty-staff')
    def update_empty_staff(self, request, pk=None):
        try:
            communication = self.get_object()
            empty_staff = request.data.get('emptyStaff')
            if empty_staff is None:
                return Response(
                    {"error": "emptyStaff is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            communication.emptyStaff = empty_staff
            communication.save()
            return Response({"message": "Updated emptyStaff successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AttendantCommunicationViewSet(viewsets.ViewSet, generics.ListAPIView, generics.CreateAPIView, generics.DestroyAPIView):
    queryset = AttendantCommunication.objects.all()
    serializer_class = AttendantCommunicationSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def register(self, request):
        user = request.user
        communication_id = request.data.get('communication')
        quantity = request.data.get('quantity')
        registration_type = request.data.get('registration_type', 'patient')  # Mặc định là patient

        if not communication_id or not quantity:
            return Response(
                {"error": "Communication ID and quantity are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if registration_type not in ['patient', 'staff']:
            return Response(
                {"error": "Invalid registration type. Must be 'patient' or 'staff'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            communication = CommunicationVaccination.objects.get(id=communication_id)
        except CommunicationVaccination.DoesNotExist:
            return Response(
                {"error": "Communication not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Kiểm tra xem user đã đăng ký với loại này chưa
        if AttendantCommunication.objects.filter(
                user=user,
                communication=communication,
                registration_type=registration_type
        ).exists():
            return Response(
                {"error": f"Bạn đã đăng ký chiến dịch này với vai trò {registration_type} rồi."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Kiểm tra số lượng slot khả dụng
        if registration_type == 'patient':
            if communication.emptyPatient < int(quantity):
                return Response(
                    {"error": "Không đủ slot bệnh nhân để đăng ký."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:  # registration_type == 'staff'
            if communication.emptyStaff < int(quantity):
                return Response(
                    {"error": "Không đủ slot nhân viên để đăng ký."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Tạo bản ghi đăng ký
        attendant = AttendantCommunication.objects.create(
            user=user,
            communication=communication,
            quantity=quantity,
            registration_type=registration_type
        )

        # Cập nhật số lượng slot
        if registration_type == 'patient':
            communication.emptyPatient -= int(quantity)
        else:  # registration_type == 'staff'
            communication.emptyStaff -= int(quantity)
        communication.save()

        # Gửi email xác nhận
        try:
            role_text = "bệnh nhân" if registration_type == 'patient' else "nhân viên y tế"
            email_subject = f"XÁC NHẬN ĐĂNG KÝ CHIẾN DỊCH TIÊM CHỦNG ({role_text})"
            email_body = (
                f"Chào {user.first_name} {user.last_name},\n\n"
                f"Bạn đã đăng ký thành công chiến dịch tiêm chủng với vai trò {role_text}: {communication.name}\n"
                f"Ngày diễn ra: {communication.date}\n"
                f"Thời gian: {communication.time}\n"
                f"Địa chỉ: {communication.address}\n"
                f"Số lượng: {quantity}\n\n"
                f"Thời gian đăng ký: {attendant.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Trân trọng,\nHệ thống tiêm chủng"
            )
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email="your-email@example.com",
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error sending email: {str(e)}")

        return Response(
            AttendantCommunicationSerializer(attendant).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['get'], url_path='check-registration/(?P<communication_id>\d+)')
    def check_registration(self, request, communication_id=None):
        user = request.user
        registration_type = request.query_params.get('registration_type', 'patient')

        if registration_type not in ['patient', 'staff']:
            return Response(
                {"error": "Invalid registration type. Must be 'patient' or 'staff'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
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
        except CommunicationVaccination.DoesNotExist:
            return Response(
                {"error": "Communication not found."},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'], url_path='cancel-registration')
    def cancel_registration(self, request):
        user = request.user
        communication_id = request.data.get('communication')
        registration_type = request.data.get('registration_type', 'patient')

        if not communication_id:
            return Response(
                {"error": "Communication ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if registration_type not in ['patient', 'staff']:
            return Response(
                {"error": "Invalid registration type. Must be 'patient' or 'staff'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            communication = CommunicationVaccination.objects.get(id=communication_id)
        except CommunicationVaccination.DoesNotExist:
            return Response(
                {"error": "Communication not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        with transaction.atomic():
            try:
                # Lấy bản ghi đăng ký của user
                attendant = AttendantCommunication.objects.get(
                    user=user,
                    communication=communication,
                    registration_type=registration_type
                )
                quantity = attendant.quantity

                # Cộng lại quantity vào emptyPatient hoặc emptyStaff
                if registration_type == 'patient':
                    communication.emptyPatient += quantity
                else:  # registration_type == 'staff'
                    communication.emptyStaff += quantity
                communication.save()

                # Xóa bản ghi đăng ký
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
            # Phân tích payload JSON
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

            # Thử kết nối đến Rasa với xử lý lỗi tốt hơn
            try:
                # Gửi yêu cầu đến server Rasa
                rasa_url = 'http://192.168.1.12:5005/webhooks/rest/webhook'
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

                # Định dạng phản hồi cho frontend
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
                # Phản hồi dự phòng khi không thể kết nối đến Rasa
                return JsonResponse({'responses': [{
'text': 'Xin lỗi, dịch vụ chatbot hiện không khả dụng. Vui lòng liên hệ với chúng tôi qua số điện thoại hoặc email.'}]})
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