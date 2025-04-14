from vaccine.models import Vaccine, VaccineType, CommunicationVaccination, Account, User, RoleEnum, CountryProduce, HealthCentre, AppointmentDetail, Information, Appointment, New, Time
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, SerializerMethodField

class VaccineSerializer(ModelSerializer):
    class Meta:
        model = Vaccine
        fields = ['id', 'name', 'price', 'country_produce', 'vaccine_type', 'imgUrl']

