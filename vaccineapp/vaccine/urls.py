from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import send_email, TotalVaccinatedView, CompletionRateView, PopularVaccinesView

# from .views import certificate_view

router = DefaultRouter()
router.register('vaccines',views.VaccineViewSet, basename='vaccine')
router.register('vaccine-types', views.VaccineTypeViewSet, basename='vaccine-type')
router.register('health-centers', views.HealthCenterViewSet, basename='health-center')
router.register('times', views.TimeViewSet, basename='time')
router.register('users',views.UserViewSet, basename='user')
router.register('registers',views.RegisterViewSet, basename='register')
router.register('profiles',views.UserProfileViewSet, basename='profile')
router.register('informations',views.InformationViewSet, basename='information')
router.register('appointments',views.AppointmentViewSet, basename='appointment')

urlpatterns = [
    path('', include(router.urls)),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('send-email/', send_email, name='send_email'),
    path('statistics/total-vaccinated/', TotalVaccinatedView.as_view(), name='total_vaccinated'),
    path('statistics/completion-rate/', CompletionRateView.as_view(), name='completion_rate'),
    path('statistics/popular-vaccines/', PopularVaccinesView.as_view(), name='popular_vaccines'),
    # path('appointments/<int:appointment_id>/certificate/', certificate_view, name='generate_certificate'),
    # path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]