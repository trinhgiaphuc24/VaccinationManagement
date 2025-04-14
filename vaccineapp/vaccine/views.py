from rest_framework import viewsets, generics, permissions, parsers, status
from vaccine.models import Vaccine, VaccineType, CommunicationVaccination, Account, User, RoleEnum, CountryProduce, HealthCentre, AppointmentDetail, Information, Appointment, New, Time
from vaccine import serializers, paginators, perms
from rest_framework.response import Response
from rest_framework.decorators import action

class VaccineViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = Vaccine.objects.filter(active=True)
    serializer_class = serializers.VaccineSerializer
    pagination_class = paginators.VaccinePagination

    # def get_queryset(self):
    #     query = self.queryset
    #
    #     q = self.request.query_params.get('q')
    #     if q:
    #         query = query.filter(subject__icontains=q)
    #
    #     cate_id = self.request.query_params.get('category_id')
    #     if cate_id:
    #         query = query.filter(category_id=cate_id)
    #
    #     return query
