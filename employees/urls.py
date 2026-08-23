from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet, EmployeeViewSet, SyncRunViewSet, healthcheck

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")
router.register("departments", DepartmentViewSet, basename="department")
router.register("sync-runs", SyncRunViewSet, basename="syncrun")

urlpatterns = [
    path("", include(router.urls)),
    path("health/", healthcheck, name="health"),
]
