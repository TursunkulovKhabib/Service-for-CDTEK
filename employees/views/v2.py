from django_filters import rest_framework as df
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from employees.dto import CompanyDTO, EmployeeDetailDTO, EmployeeListDTO, SyncRunDTO
from employees.models import Employee
from employees.permissions import JwtRequiredPermission
from employees.repositories import CompanyRepository, SyncRunRepository
from employees.services import EmployeeService


class EmployeeFilter(df.FilterSet):
    department = df.CharFilter(field_name="department", lookup_expr="icontains")
    title = df.CharFilter(field_name="title", lookup_expr="icontains")
    company = df.CharFilter(field_name="company__code", lookup_expr="iexact")

    class Meta:
        model = Employee
        fields = ("department", "title", "company")


class BaseApiV2ViewSet(viewsets.GenericViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [JwtRequiredPermission]


class EmployeeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, BaseApiV2ViewSet):
    lookup_field = "object_guid"
    filterset_class = EmployeeFilter
    search_fields = ("full_name", "department", "title", "search_phone", "email")
    ordering_fields = ("full_name", "department", "title")
    ordering = ("full_name",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = EmployeeService()

    def get_queryset(self):
        params = self.request.query_params
        include_inactive = params.get("include_inactive") in {"1", "true", "yes"}
        return self.service.search(
            query=params.get("q", ""),
            phone=params.get("phone", ""),
            include_inactive=include_inactive,
        )

    def get_serializer_class(self):
        return EmployeeDetailDTO if self.action == "retrieve" else EmployeeListDTO

    @action(detail=False, url_path="departments")
    def departments(self, request):
        return Response(self.service.departments(company=request.query_params.get("company", "")))


class CompanyViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, BaseApiV2ViewSet):
    serializer_class = CompanyDTO
    lookup_field = "code"

    def get_queryset(self):
        return CompanyRepository().active()


class SyncRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, BaseApiV2ViewSet):
    serializer_class = SyncRunDTO
    filterset_fields = ("mode", "status", "company__code")

    def get_queryset(self):
        return SyncRunRepository().all()
