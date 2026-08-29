from django.urls import path

from employees.views import (
    LegacyDepartmentListView,
    LegacyEmployeeDetailView,
    LegacyEmployeeListView,
    healthcheck,
)

app_name = "v1"

urlpatterns = [
    path("employees/", LegacyEmployeeListView.as_view(), name="employee-list"),
    path("employees/<str:login>/", LegacyEmployeeDetailView.as_view(), name="employee-detail"),
    path("departments/", LegacyDepartmentListView.as_view(), name="department-list"),
    path("health/", healthcheck, name="health"),
]
