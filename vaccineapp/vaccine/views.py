from threading import activeCount
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from io import BytesIO
import pdfplumber
from django.http import JsonResponse
from rest_framework.decorators import api_view
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from .models import Appointment, AppointmentDetail, Vaccine
from datetime import datetime
import calendar
from rest_framework import viewsets, generics, permissions, parsers, status
from rest_framework.filters import OrderingFilter
from rest_framework.views import APIView
from vaccine.models import Vaccine, VaccineType, CommunicationVaccination, User, RoleEnum, CountryProduce, HealthCenter, AppointmentDetail, Information, Appointment, New, Time
from vaccine import serializers, paginators, perms
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from vaccine.serializers import VaccineTypeSerializer, UserRegisterSerializer, InformationSerializer, \
    AppointmentSerializer, AppointmentReadSerializer, AppointmentDetailReadSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny


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


class VaccineViewSet(viewsets.ModelViewSet):
    queryset = Vaccine.objects.filter(active=True).select_related('vaccine_type', 'country_produce')
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


class VaccineTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VaccineType.objects.filter(active=True)
    serializer_class = VaccineTypeSerializer


class HealthCenterViewSet(viewsets.ModelViewSet):
    queryset = HealthCenter.objects.filter(active=True)
    serializer_class = serializers.HealthCenterSerializer
    pagination_class = paginators.HealthCenterPagination


class TimeViewSet(viewsets.ModelViewSet):
    queryset = Time.objects.filter(active=True)
    serializer_class = serializers.TimeSerializer
    pagination_class = paginators.TimePagination


class InformationViewSet(viewsets.ModelViewSet):
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


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.select_related('information', 'health_centre', 'time').prefetch_related('appointment_details__vaccine')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        # Sử dụng AppointmentReadSerializer cho các hành động đọc
        if self.action in ['list', 'retrieve', 'get_appointment_details']:
            return AppointmentReadSerializer
        # Sử dụng AppointmentSerializer cho các hành động ghi (như create, update)
        return AppointmentSerializer

    def get_queryset(self):
        print("Current user:", self.request.user.id)
        return self.queryset.filter(information__user=self.request.user)

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