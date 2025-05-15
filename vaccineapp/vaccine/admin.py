from django.contrib import admin
from django.urls import path
from django.utils.html import mark_safe
from django.db.models import Count, Q, F
from django.db.models.functions import TruncDay, TruncMonth, TruncQuarter
from django.template.response import TemplateResponse
from datetime import datetime, timedelta
from django.utils import timezone
import calendar

from vaccine.models import User, Information, Vaccine, HealthCenter, Time, Appointment, VaccineType, AppointmentDetail, \
    CommunicationVaccination


class MyVaccineAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'active', 'createdAt', 'vaccine_type']
    search_fields = ['name']
    list_filter = ['id', 'createdAt']
    list_editable = ['name']
    readonly_fields = ['image_view']
    list_per_page = 10

    def image_view(self, course):
        return mark_safe(f"<img src='/static/{course.image.name}' width='200' />")

class MyCommunicationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'active', 'date', 'time']
    search_fields = ['name']
    list_filter = ['id']
    list_editable = ['name']
    list_per_page = 10


class MyHealthCenterAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'active', 'address']
    search_fields = ['name']
    list_filter = ['id']
    list_editable = ['name']
    list_per_page = 10


class MyInformationAdmin(admin.ModelAdmin):
    list_display = ['id', 'first_name', 'last_name']
    search_fields = ['first_name', 'last_name']
    list_filter = ['id']
    list_editable = ['first_name', 'last_name']
    list_per_page = 10


class MyTimeAdmin(admin.ModelAdmin):
    list_display = ['id', 'time_start', 'time_end']
    search_fields = ['time_start', 'time_end']
    list_filter = ['id']
    list_editable = ['time_start', 'time_end']
    list_per_page = 10


class MyUserAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'userRole']
    search_fields = ['username']
    list_filter = ['id']
    list_editable = ['username']
    list_per_page = 10


class MyVaccineAdminSite(admin.AdminSite):
    site_header = 'Vaccine Management Admin'

    def get_urls(self):
        return [path('cate-stats/', self.cate_stats_view)] + super().get_urls()

    def cate_stats_view(self, request):
        time_filter = request.GET.get('time_filter', 'month')  # Mặc định là tháng
        year = int(request.GET.get('year', datetime.now().year))
        period = request.GET.get('period', '1')  # Truyền dưới dạng chuỗi

        # Xác định khoảng thời gian
        if time_filter == 'year':
            start_date = timezone.make_aware(datetime(year, 1, 1))
            end_date = timezone.make_aware(datetime(year + 1, 1, 1))
            period_label = f"Năm {year}"
        elif time_filter == 'quarter':
            start_month = (int(period) - 1) * 3 + 1
            end_month = start_month + 2
            start_date = timezone.make_aware(datetime(year, start_month, 1))
            end_date = timezone.make_aware(
                datetime(year, end_month, calendar.monthrange(year, end_month)[1])
            ) + timedelta(days=1)
            period_label = f"Quý {period} - {year}"
        else:  # month
            start_date = timezone.make_aware(datetime(year, int(period), 1))
            end_date = timezone.make_aware(
                datetime(year, int(period), calendar.monthrange(year, int(period))[1])
            ) + timedelta(days=1)
            period_label = f"Tháng {period} - {year}"

        # Dữ liệu cho biểu đồ
        vaccinated_data = []
        completion_data = []
        labels = []
        vaccine_stats = {}  # {vaccine_type_name: [counts]}

        # Lấy danh sách các loại vắc-xin
        vaccine_types = VaccineType.objects.all()
        for vt in vaccine_types:
            vaccine_stats[vt.name] = []

        if time_filter == 'year':
            # Thống kê theo 12 tháng trong năm
            labels = [f"Tháng {i}" for i in range(1, 13)]
            for month in range(1, 13):
                month_start = timezone.make_aware(datetime(year, month, 1))
                month_end = timezone.make_aware(
                    datetime(year, month, calendar.monthrange(year, month)[1])
                ) + timedelta(days=1)

                # Số lượng hồ sơ đã tiêm
                vaccinated_count = Appointment.objects.filter(
                    status='completed',
                    date__range=(month_start, month_end)
                ).count()
                vaccinated_data.append(vaccinated_count)

                # Tỷ lệ hoàn thành lịch tiêm
                total_apps = Appointment.objects.filter(
                    date__range=(month_start, month_end)
                ).count()
                completed_apps = Appointment.objects.filter(
                    status='completed',
                    date__range=(month_start, month_end)
                ).count()
                rate = (completed_apps / total_apps * 100) if total_apps > 0 else 0
                completion_data.append(round(rate, 2))

                # Thống kê số lượng vắc-xin theo loại
                for vt in vaccine_types:
                    count = Appointment.objects.filter(
                        status='completed',
                        date__range=(month_start, month_end),
                        appointment_details__vaccine__vaccine_type=vt
                    ).count()
                    vaccine_stats[vt.name].append(count)

        elif time_filter == 'quarter':
            # Thống kê theo 4 quý trong năm
            labels = ['Quý 1', 'Quý 2', 'Quý 3', 'Quý 4']
            for quarter in range(1, 5):
                start_month = (quarter - 1) * 3 + 1
                end_month = start_month + 2
                quarter_start = timezone.make_aware(datetime(year, start_month, 1))
                quarter_end = timezone.make_aware(
                    datetime(year, end_month, calendar.monthrange(year, end_month)[1])
                ) + timedelta(days=1)

                # Số lượng hồ sơ đã tiêm
                vaccinated_count = Appointment.objects.filter(
                    status='completed',
                    date__range=(quarter_start, quarter_end)
                ).count()
                vaccinated_data.append(vaccinated_count)

                # Tỷ lệ hoàn thành lịch tiêm
                total_apps = Appointment.objects.filter(
                    date__range=(quarter_start, quarter_end)
                ).count()
                completed_apps = Appointment.objects.filter(
                    status='completed',
                    date__range=(quarter_start, quarter_end)
                ).count()
                rate = (completed_apps / total_apps * 100) if total_apps > 0 else 0
                completion_data.append(round(rate, 2))

                # Thống kê số lượng vắc-xin theo loại
                for vt in vaccine_types:
                    count = Appointment.objects.filter(
                        status='completed',
                        date__range=(quarter_start, quarter_end),
                        appointment_details__vaccine__vaccine_type=vt
                    ).count()
                    vaccine_stats[vt.name].append(count)

        else:  # month
            # Thống kê theo từng ngày trong tháng
            days_in_month = calendar.monthrange(year, int(period))[1]
            labels = [f"Ngày {i}" for i in range(1, days_in_month + 1)]
            for day in range(1, days_in_month + 1):
                day_start = timezone.make_aware(datetime(year, int(period), day))
                day_end = day_start + timedelta(days=1)

                # Số lượng hồ sơ đã tiêm
                vaccinated_count = Appointment.objects.filter(
                    status='completed',
                    date__range=(day_start, day_end)
                ).count()
                vaccinated_data.append(vaccinated_count)

                # Tỷ lệ hoàn thành lịch tiêm
                total_apps = Appointment.objects.filter(
                    date__range=(day_start, day_end)
                ).count()
                completed_apps = Appointment.objects.filter(
                    status='completed',
                    date__range=(day_start, day_end)
                ).count()
                rate = (completed_apps / total_apps * 100) if total_apps > 0 else 0
                completion_data.append(round(rate, 2))

                # Thống kê số lượng vắc-xin theo loại
                for vt in vaccine_types:
                    count = Appointment.objects.filter(
                        status='completed',
                        date__range=(day_start, day_end),
                        appointment_details__vaccine__vaccine_type=vt
                    ).count()
                    vaccine_stats[vt.name].append(count)

        return TemplateResponse(request, 'admin/stats.html', {
            'vaccinated_data': vaccinated_data,
            'completion_data': completion_data,
            'vaccine_stats': vaccine_stats,
            'labels': labels,
            'period_label': period_label,
            'time_filter': time_filter,
            'year': year,
            'period': period,
        })


admin_site = MyVaccineAdminSite(name='vaccine')

admin_site.register(Vaccine, MyVaccineAdmin)
admin_site.register(Information, MyInformationAdmin)
# admin_site.register(Appointment)
# admin_site.register(AppointmentDetail)
admin_site.register(User, MyUserAdmin)
admin_site.register(HealthCenter, MyHealthCenterAdmin)
admin_site.register(Time, MyTimeAdmin)
admin_site.register(CommunicationVaccination, MyCommunicationAdmin)