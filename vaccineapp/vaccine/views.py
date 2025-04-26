from threading import activeCount
from rest_framework import viewsets, generics, permissions, parsers, status
from rest_framework.filters import OrderingFilter
from rest_framework.views import APIView
from vaccine.models import Vaccine, VaccineType, CommunicationVaccination, User, RoleEnum, CountryProduce, HealthCenter, AppointmentDetail, Information, Appointment, New, Time
from vaccine import serializers, paginators, perms
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from vaccine.serializers import VaccineTypeSerializer, UserRegisterSerializer
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