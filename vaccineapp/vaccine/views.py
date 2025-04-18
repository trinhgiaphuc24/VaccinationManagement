from threading import activeCount

from rest_framework import viewsets, generics, permissions, parsers, status
from rest_framework.filters import OrderingFilter
from vaccine.models import Vaccine, VaccineType, CommunicationVaccination, User, RoleEnum, CountryProduce, HealthCenter, AppointmentDetail, Information, Appointment, New, Time
from vaccine import serializers, paginators, perms
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from vaccine.serializers import VaccineTypeSerializer


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