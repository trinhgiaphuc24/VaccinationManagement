from threading import activeCount
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
    serializer_class = InformationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Information.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        instance.delete()

class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.select_related('information', 'health_centre', 'time').prefetch_related('appointment_details__vaccine')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve', 'get_appointment_details']:
            return AppointmentReadSerializer
        return AppointmentSerializer

    def get_queryset(self):
        print("Current user:", self.request.user.id, "Role:", self.request.user.userRole)
        if self.request.user.userRole == "staff":
            return self.queryset
        return self.queryset.filter(information__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
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