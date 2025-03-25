from django.contrib import admin
from django.urls import path
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django.utils.html import mark_safe
from django import forms
from django.db.models import Count
from django.template.response import TemplateResponse

from vaccine.models import User, Account, Information, Vaccine, HealthCentre, Time, Appointment


class MyCourseAdminSite(admin.AdminSite):
    site_header = 'Vaccine Management Admin'


    # def get_urls(self):
    #     return [path('cate-stats/', self.cate_stats_view)] + super().get_urls()


    # def cate_stats_view(self, request):
    #     stats = Category.objects.annotate(course_count=Count('course__id')).values('id', 'name', 'course_count')
    #
    #     return TemplateResponse(request, 'admin/stats.html', {
    #         'stats': stats
    #     })


admin_site = MyCourseAdminSite(name='vaccine')

admin_site.register(Vaccine)
admin_site.register(Information)
admin_site.register(Appointment)
admin_site.register(Account)
admin_site.register(User)
admin_site.register(HealthCentre)
admin_site.register(Time)
