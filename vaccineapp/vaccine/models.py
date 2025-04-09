from django.db import models
from django.contrib.auth.models import AbstractUser
from cloudinary.models import CloudinaryField


class RoleEnum(models.TextChoices):
    ADMIN = "admin", "Admin"
    STAFF = "staff", "Staff"
    PATIENT = "patient", "Patient"


class BaseModel(models.Model):
    name = models.CharField(max_length=100, null=False, unique=True)
    # active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    sex = models.BooleanField(null=True)  # Thêm sex
    dateOfBirth = models.DateField(null=True)
    is_active = models.BooleanField(default=True)
    createdAt = models.DateTimeField(auto_now_add=True, null=True)
    avatarUrl = CloudinaryField('avatar', null=True)
    userRole = models.CharField(max_length=20, choices=RoleEnum.choices,
                                default=RoleEnum.PATIENT)

    def __str__(self):
        return self.username


class Account(models.Model):
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="account")

    def __str__(self):
        return self.username


class Information(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    date_of_birth = models.DateField()
    sex = models.BooleanField()
    address = models.TextField()
    email = models.EmailField(null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="information")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class HealthCentre(BaseModel):
    address = models.TextField()

    def __str__(self):
        return self.name


class VaccineType(BaseModel):

    def __str__(self):
        return self.name


class CountryProduce(BaseModel):

    def __str__(self):
        return self.name

class Vaccine(BaseModel):
    description = models.TextField()
    price = models.FloatField()
    vaccine_type = models.ForeignKey(VaccineType, on_delete=models.CASCADE,null=True,
    blank=True, related_name="vaccinetype")
    country_produce = models.ForeignKey(CountryProduce, on_delete=models.SET_NULL,
        null=True,
        blank=True, related_name="countryproduce")

    def __str__(self):
        return self.name


class Time(models.Model):
    time_start = models.DateTimeField()
    time_end = models.DateTimeField()

    def __str__(self):
        return f"{self.time_start} - {self.time_end}"


class Appointment(models.Model):
    date = models.DateField()
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="appointments")
    health_centre = models.ForeignKey(HealthCentre, on_delete=models.CASCADE, related_name="appointments")
    # vaccines = models.ManyToManyField(Vaccine, related_name="appointments")
    time = models.ForeignKey(Time, on_delete=models.CASCADE, related_name="appointments")

    def __str__(self):
        return f"Appointment on {self.date} - {self.user.username}"


class AppointmentDetail(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name="appointment_details")
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name="appointment_details")
    quantity = models.IntegerField()

    def __str__(self):
        return f"Detail for {self.appointment} - Vaccine: {self.vaccine.name}"


class CommunicationVaccination(BaseModel):
    date = models.DateField()
    time = models.DateTimeField()
    address = models.TextField()
    description = models.TextField()

    def __str__(self):
        return self.name