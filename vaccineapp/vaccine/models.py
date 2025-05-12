from django.db import models
from django.contrib.auth.models import AbstractUser
from cloudinary.models import CloudinaryField


class RoleEnum(models.TextChoices):
    ADMIN = "admin", "Admin"
    STAFF = "staff", "Staff"
    PATIENT = "patient", "Patient"

class StatusEnum(models.TextChoices):
    CHO_XAC_NHAN = "waited", "Waited"
    DA_XAC_NHAN = "confirmed", "Confirmed"
    DA_HOAN_THANH = "completed", "Completed"
    DA_HUY = "canceled", "Canceled"

class SexEnum(models.TextChoices):
    NAM = "male", "Male"
    NU = "female", "Female"


class BaseModel(models.Model):
    active = models.BooleanField(default=True)
    name = models.CharField(max_length=100, null=False, unique=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    sex = models.CharField(max_length=20, choices=SexEnum.choices, null=True, default=SexEnum.NAM)
    dateOfBirth = models.DateField(null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Cho phép truy cập admin
    is_superuser = models.BooleanField(default=False)  # Super quyền
    createdAt = models.DateTimeField(auto_now_add=True, null=True)
    avatarUrl = CloudinaryField('avatar', null=True)
    userRole = models.CharField(max_length=20, choices=RoleEnum.choices,
                                default=RoleEnum.PATIENT)

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


class HealthCenter(BaseModel):
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
    imgUrl = CloudinaryField('imgvaccine', null=True)
    vaccine_type = models.ForeignKey(VaccineType, on_delete=models.CASCADE,null=True,
    blank=True, related_name="vaccinetype")
    createdAt = models.DateTimeField(auto_now_add=True, null=True)
    country_produce = models.ForeignKey(CountryProduce, on_delete=models.SET_NULL,
        null=True,
        blank=True, related_name="countryproduce")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['id']


class Time(models.Model):
    time_start = models.CharField(max_length=255)
    time_end = models.CharField(max_length=255)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.time_start} - {self.time_end}"


class Appointment(models.Model):
    date = models.DateField()
    status = models.CharField(max_length=20, choices=StatusEnum.choices,default=StatusEnum.CHO_XAC_NHAN)
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)
    information = models.ForeignKey(Information, on_delete=models.SET_NULL, related_name="appointments", null=True)
    health_centre = models.ForeignKey(HealthCenter, on_delete=models.CASCADE, related_name="appointments")
    # vaccines = models.ManyToManyField(Vaccine, related_name="appointments")
    time = models.ForeignKey(Time, on_delete=models.CASCADE, related_name="appointments")

    def __str__(self):
        return f"Appointment on {self.date} - {self.user.username}"


class AppointmentDetail(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name="appointment_details")
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name="appointment_details")
    # quantity = models.IntegerField()

    def __str__(self):
        return f"Detail for {self.appointment} - Vaccine: {self.vaccine.name}"


class CommunicationVaccination(BaseModel):
    date = models.DateField()
    time = models.CharField(max_length=255)
    address = models.TextField()
    description = models.TextField()
    slotPatient = models.IntegerField(null=True)
    slotStaff = models.IntegerField(null=True)
    emptyStaff = models.IntegerField(null=True)
    emptyPatient = models.IntegerField(null=True)
    imgUrl = CloudinaryField('imgvaccine', null=True)

    def __str__(self):
        return self.name


class AttendantCommunication(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    communication = models.ForeignKey(CommunicationVaccination, on_delete=models.CASCADE)
    quantity = models.IntegerField(null=True)
    registration_type = models.CharField(
        max_length=10,
        choices=[("patient", "Patient"), ("staff", "Staff")],
        default="patient"
    )

    class Meta:
        unique_together = ('user', 'communication', 'registration_type')

class New(BaseModel):
    imgNew = CloudinaryField('imgnew', null=True)
    createdAt = models.DateField(null=True)
    description = models.TextField()

    def __str__(self):
        return self.name