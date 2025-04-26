from django.contrib.auth.hashers import make_password

from vaccine.models import Vaccine, VaccineType, CommunicationVaccination, User, RoleEnum, CountryProduce, HealthCenter, AppointmentDetail, Information, Appointment, New, Time
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, SerializerMethodField


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'phone_number', 'first_name', 'last_name', 'userRole', 'avatarUrl']
        extra_kwargs = {
            'password': {
                'write_only': True
            }
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['avatar'] = instance.avatarUrl.url if instance.avatarUrl else None
        return data

    def create(self, validated_data):
        data = validated_data.copy()
        u = User(**data)
        u.set_password(u.password)
        u.save()

        return u

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    avatarUrl = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'phone_number', 'first_name', 'last_name', 'userRole', 'avatarUrl']

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        validated_data['userRole'] = RoleEnum.PATIENT
        user = User.objects.create(**validated_data)
        return user

    def update(self, instance, validated_data):
        validated_data.pop('userRole', None)
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
        return super().update(instance, validated_data)

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

class HealthCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthCenter
        fields = ['id', 'name', 'address']


class TimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Time
        fields = ['id', 'time_start', 'time_end']