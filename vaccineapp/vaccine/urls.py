from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register('vaccines',views.VaccineViewSet, basename='vaccine')
router.register('vaccine-types', views.VaccineTypeViewSet, basename='vaccine-type')
router.register('health-centers', views.HealthCenterViewSet, basename='health-center')
router.register('times', views.TimeViewSet, basename='time')
router.register('users',views.UserViewSet, basename='user')
router.register('registers',views.RegisterViewSet, basename='register')
router.register('profiles',views.UserProfileViewSet, basename='profile')


urlpatterns = [
    path('', include(router.urls)),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]