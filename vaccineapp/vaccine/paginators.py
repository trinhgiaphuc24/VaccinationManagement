from rest_framework.pagination import PageNumberPagination
from rest_framework import pagination


class VaccinePagination(PageNumberPagination):
    page_size = 10

class HealthCenterPagination(PageNumberPagination):
    page_size = 10

class TimePagination(PageNumberPagination):
    page_size = 10

class AppointmentPagination(PageNumberPagination):
    page_size = 10