import re

from django.db.models import Count, Q
from django_filters import rest_framework as df
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Employee, SyncRun
from .serializers import EmployeeDetailSerializer, EmployeeListSerializer, SyncRunSerializer


class EmployeeFilter(df.FilterSet):
    department = df.CharFilter(field_name="department", lookup_expr="icontains")
    company = df.CharFilter(field_name="company", lookup_expr="icontains")
    title = df.CharFilter(field_name="title", lookup_expr="icontains")
    office = df.CharFilter(field_name="office", lookup_expr="icontains")
    phone = df.CharFilter(method="filter_phone", label="Телефон (любой формат)")
    q = df.CharFilter(method="filter_q", label="ФИО / подразделение / телефон / почта")

    class Meta:
        model = Employee
        fields = ("department", "company", "title", "office", "phone", "q")

    def filter_phone(self, queryset, name, value):
        digits = re.sub(r"\D", "", value or "")
        if not digits:
            return queryset
        return queryset.filter(search_phone__contains=digits)

    def filter_q(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        digits = re.sub(r"\D", "", value)
        condition = (
            Q(full_name__icontains=value)
            | Q(display_name__icontains=value)
            | Q(sam_account_name__icontains=value)
            | Q(email__icontains=value)
            | Q(department__icontains=value)
            | Q(title__icontains=value)
        )
        if len(digits) >= 3:
            condition |= Q(search_phone__contains=digits)
        return queryset.filter(condition)


class EmployeeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):

    lookup_field = "object_guid"
    filterset_class = EmployeeFilter
    search_fields = ("full_name", "display_name", "department", "title", "email", "search_phone")
    ordering_fields = ("full_name", "department", "title", "when_changed")
    ordering = ("full_name",)

    def get_queryset(self):
        queryset = Employee.objects.published().select_related("manager")
        if self.request.query_params.get("include_inactive") in {"1", "true", "yes"}:
            queryset = Employee.objects.select_related("manager")
        return queryset

    def get_serializer_class(self):
        return EmployeeDetailSerializer if self.action == "retrieve" else EmployeeListSerializer


class DepartmentViewSet(viewsets.ViewSet):

    def list(self, request):
        rows = (
            Employee.objects.published()
            .exclude(department="")
            .values("department")
            .annotate(employees=Count("id"))
            .order_by("department")
        )
        return Response(list(rows))


class SyncRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):

    queryset = SyncRun.objects.all()
    serializer_class = SyncRunSerializer
    filterset_fields = ("mode", "status")


@api_view(["GET"])
@permission_classes([AllowAny])
def healthcheck(request):
    last_run = SyncRun.objects.filter(status=SyncRun.Status.SUCCESS).order_by("-finished_at").first()
    return Response(
        {
            "status": "ok",
            "employees_total": Employee.objects.count(),
            "employees_active": Employee.objects.published().count(),
            "last_sync": {
                "mode": last_run.mode,
                "finished_at": last_run.finished_at,
                "entries_read": last_run.entries_read,
            }
            if last_run
            else None,
        }
    )
