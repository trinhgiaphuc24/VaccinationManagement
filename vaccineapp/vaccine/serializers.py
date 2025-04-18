from vaccine.models import Vaccine, VaccineType, CommunicationVaccination, User, RoleEnum, CountryProduce, HealthCentre, AppointmentDetail, Information, Appointment, New, Time
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, SerializerMethodField


class VaccineTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VaccineType
        fields = ['id', 'name']

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CountryProduce
        fields = ['id', 'name']

class VaccineSerializer(ModelSerializer):
    vaccine_type = VaccineTypeSerializer(read_only=True)  # Sử dụng nested serializer
    country_produce = CountrySerializer(read_only=True)  # Sử dụng nested serializer
    class Meta:
        model = Vaccine
        fields = ['id', 'name', 'price', 'country_produce', 'vaccine_type', 'imgUrl']