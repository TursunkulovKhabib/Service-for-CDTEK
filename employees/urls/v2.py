from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from employees.views import CompanyViewSet, EmployeeViewSet, SyncRunViewSet, healthcheck

app_name = "v2"

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")
router.register("companies", CompanyViewSet, basename="company")
router.register("sync-runs", SyncRunViewSet, basename="syncrun")

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token-obtain"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("health/", healthcheck, name="health"),
    path("", include(router.urls)),
]
