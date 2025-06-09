from django.contrib.auth.hashers import make_password
from vaccine.models import Vaccine, VaccineType, CommunicationVaccination, User, RoleEnum, CountryProduce, HealthCenter, \
    AppointmentDetail, Information, Appointment, New, Time, AttendantCommunication
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, SerializerMethodField


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'phone_number', 'first_name', 'last_name', 'userRole', 'avatarUrl']

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

class VaccineTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VaccineType
        fields = ['id', 'name']

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CountryProduce
        fields = ['id', 'name']

class VaccineSerializer(ModelSerializer):
    vaccine_type = VaccineTypeSerializer(read_only=True)
    country_produce = CountrySerializer(read_only=True)

    class Meta:
        model = Vaccine
        fields = ['id', 'name', 'price', 'country_produce', 'vaccine_type', 'imgUrl', 'description']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['imgUrl'] = instance.imgUrl.url if instance.imgUrl else None
        return data

class HealthCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthCenter
        fields = ['id', 'name', 'address']

class TimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Time
        fields = ['id', 'time_start', 'time_end']

class InformationSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.DateField(format="%d/%m/%Y", input_formats=["%d/%m/%Y"])

    class Meta:
        model = Information
        fields = ["id", "first_name", "last_name", "phone_number", "date_of_birth", "sex", "address", "email", "user"]
        read_only_fields = ['user']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class AppointmentDetailSerializer(serializers.ModelSerializer):
    vaccine = serializers.PrimaryKeyRelatedField(queryset=Vaccine.objects.all())

    class Meta:
        model = AppointmentDetail
        fields = ['id', 'vaccine']

class AppointmentSerializer(serializers.ModelSerializer):
    appointment_details = AppointmentDetailSerializer(many=True, required=False)
    information = serializers.PrimaryKeyRelatedField(queryset=Information.objects.all(), required=False)
    health_centre = serializers.PrimaryKeyRelatedField(queryset=HealthCenter.objects.all(), required=False)
    time = serializers.PrimaryKeyRelatedField(queryset=Time.objects.all(), required=False)
    date = serializers.DateField(required=False)

    class Meta:
        model = Appointment
        fields = ['id', 'date', 'status', 'created_at', 'note', 'information', 'health_centre', 'time', 'appointment_details']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        appointment_details_data = validated_data.pop('appointment_details', [])
        appointment = Appointment.objects.create(**validated_data)
        for detail_data in appointment_details_data:
            AppointmentDetail.objects.create(appointment=appointment, **detail_data)
        return appointment


class CommunicationVaccinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunicationVaccination
        fields = ['id', 'name', 'date', 'time','address', 'description', 'slotPatient', 'slotStaff', 'emptyStaff', 'emptyPatient', 'imgUrl']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['imgUrl'] = instance.imgUrl.url if instance.imgUrl else None
        return data


class AttendantCommunicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendantCommunication
        fields = ['id', 'user', 'communication', 'quantity', 'registration_type']

class AppointmentDetailReadSerializer(serializers.ModelSerializer):
    vaccine = VaccineSerializer(read_only=True)

    class Meta:
        model = AppointmentDetail
        fields = ['id', 'vaccine']

class AppointmentReadSerializer(serializers.ModelSerializer):
    appointment_details = AppointmentDetailReadSerializer(many=True, read_only=True)
    information = InformationSerializer(read_only=True)
    health_centre = HealthCenterSerializer(read_only=True)
    time = TimeSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = ['id', 'date', 'status', 'created_at', 'note', 'information', 'health_centre', 'time', 'appointment_details']
        read_only_fields = ['id', 'created_at']