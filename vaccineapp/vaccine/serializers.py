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
        fields = ['id', 'name', 'price', 'country_produce', 'vaccine_type', 'imgUrl', 'description']

class HealthCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthCenter
        fields = ['id', 'name', 'address']


class TimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Time
        fields = ['id', 'time_start', 'time_end']


class InformationSerializer(serializers.ModelSerializer):
    # Tùy chỉnh trường date_of_birth để nhận dữ liệu dạng chuỗi "DD/MM/YYYY"
    date_of_birth = serializers.DateField(format="%d/%m/%Y", input_formats=["%d/%m/%Y"])

    class Meta:
        model = Information
        fields = [
            "id", "first_name", "last_name", "phone_number", "date_of_birth", "sex", "address", "email", "user",
        ]

    # def validate_phone_number(self, value):
    #     # Kiểm tra định dạng số điện thoại (ví dụ: 10-15 chữ số)
    #     if not value.isdigit() or len(value) < 10 or len(value) > 11:
    #         raise serializers.ValidationError("Số điện thoại phải chứa từ 10 đến 11 chữ số.")
    #     return value

    # def validate_email(self, value):
    #     # Kiểm tra email duy nhất (nếu có)
    #     if value and Information.objects.filter(email=value).exists():
    #         raise serializers.ValidationError("Email này đã được sử dụng.")
    #     return value

    def create(self, validated_data):
        # Tạo mới một Information object
        return Information.objects.create(**validated_data)

    def update(self, instance, validated_data):
        # Cập nhật Information object
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.phone_number = validated_data.get("phone_number", instance.phone_number)
        instance.date_of_birth = validated_data.get("date_of_birth", instance.date_of_birth)
        instance.sex = validated_data.get("sex", instance.sex)
        instance.address = validated_data.get("address", instance.address)
        instance.email = validated_data.get("email", instance.email)
        instance.user = validated_data.get("user", instance.user)
        instance.save()
        return instance


class AppointmentDetailSerializer(serializers.ModelSerializer):
    vaccine = serializers.PrimaryKeyRelatedField(queryset=Vaccine.objects.all())

    class Meta:
        model = AppointmentDetail
        fields = ['id', 'vaccine']  # Không cần quantity vì đã bị comment trong model

class AppointmentSerializer(serializers.ModelSerializer):
    appointment_details = AppointmentDetailSerializer(many=True, write_only=True)
    information = serializers.PrimaryKeyRelatedField(queryset=Information.objects.all())  # Nhận ID của Information
    health_centre = serializers.PrimaryKeyRelatedField(queryset=HealthCenter.objects.all())
    time = serializers.PrimaryKeyRelatedField(queryset=Time.objects.all())

    class Meta:
        model = Appointment
        fields = ['id', 'date', 'status', 'created_at', 'note', 'information', 'health_centre', 'time', 'appointment_details']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        # Lấy danh sách appointment_details (các vaccine được chọn)
        appointment_details_data = validated_data.pop('appointment_details')
        # Tạo Appointment
        appointment = Appointment.objects.create(**validated_data)
        # Tạo các AppointmentDetail tương ứng với mỗi vaccine
        for detail_data in appointment_details_data:
            AppointmentDetail.objects.create(appointment=appointment, **detail_data)
        return appointment


class AppointmentDetailReadSerializer(serializers.ModelSerializer):
    vaccine = VaccineSerializer(read_only=True)  # Trả về thông tin chi tiết của vaccine

    class Meta:
        model = AppointmentDetail
        fields = ['id', 'vaccine']

# Serializer dùng để hiển thị thông tin chi tiết của Appointment (đọc dữ liệu)
class AppointmentReadSerializer(serializers.ModelSerializer):
    appointment_details = AppointmentDetailReadSerializer(many=True, read_only=True)
    information = InformationSerializer(read_only=True)
    health_centre = HealthCenterSerializer(read_only=True)  # Trả về thông tin chi tiết của health_centre
    time = TimeSerializer(read_only=True)  # Trả về thông tin chi tiết của time

    class Meta:
        model = Appointment
        fields = ['id', 'date', 'status', 'created_at', 'note', 'information', 'health_centre', 'time', 'appointment_details']
        read_only_fields = ['id', 'created_at']