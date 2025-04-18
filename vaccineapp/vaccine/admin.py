from django.contrib import admin
from django.urls import path
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django.utils.html import mark_safe
from django import forms
from django.db.models import Count
from django.template.response import TemplateResponse

from vaccine.models import User, Information, Vaccine, HealthCenter, Time, Appointment, VaccineType, AppointmentDetail


class MyVaccineAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'active', 'createdAt', 'vaccine_type']
    search_fields = ['name']
    list_filter = ['id', 'createdAt']
    list_editable = ['name']
    readonly_fields = ['image_view']
    list_per_page = 10

    def image_view(self, course):
        return mark_safe(f"<img src='/static/{course.image.name}' width='200' />")



class MyCourseAdminSite(admin.AdminSite):
    site_header = 'Vaccine Management Admin'


    def get_urls(self):
        return [path('cate-stats/', self.cate_stats_view)] + super().get_urls()


    def cate_stats_view(self, request):
        stats = VaccineType.objects.annotate(vaccine_count=Count('vaccinetype')).values('id', 'name', 'vaccine_count')

        return TemplateResponse(request, 'admin/stats.html', {
            'stats': stats
        })


admin_site = MyCourseAdminSite(name='vaccine')

admin_site.register(Vaccine, MyVaccineAdmin)
admin_site.register(Information)
admin_site.register(Appointment)
admin_site.register(AppointmentDetail)
admin_site.register(User)
admin_site.register(HealthCenter)
admin_site.register(Time)
