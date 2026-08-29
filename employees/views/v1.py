from django.conf import settings
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.dto import LegacyDepartmentDTO, LegacyEmployeeDTO
from employees.permissions import LegacyV1Permission
from employees.services import EmployeeService


class LegacyApiView(APIView):
    authentication_classes = [BasicAuthentication, SessionAuthentication]
    permission_classes = [LegacyV1Permission]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = EmployeeService()
        self.dto = LegacyEmployeeDTO()

    @property
    def config(self) -> dict:
        return settings.LEGACY_V1

    def param(self, request, key: str, default: str = "") -> str:
        return request.query_params.get(self.config[key], default)


class LegacyEmployeeListView(LegacyApiView):
    def get(self, request):
        limit_raw = request.query_params.get(self.config["LIMIT_PARAM"])
        try:
            limit = int(limit_raw) if limit_raw else self.config["DEFAULT_LIMIT"]
        except ValueError:
            limit = self.config["DEFAULT_LIMIT"]

        employees = self.service.search(
            query=self.param(request, "SEARCH_PARAM"),
            department=self.param(request, "DEPARTMENT_PARAM"),
            company=self.param(request, "COMPANY_PARAM"),
            phone=request.query_params.get("phone", ""),
            limit=limit,
        )
        return Response(self.dto.envelope(self.dto.to_list(employees)))


class LegacyEmployeeDetailView(LegacyApiView):
    def get(self, request, login: str):
        employee = self.service.get_by_login(login)
        if employee is None or not employee.is_published:
            return Response({"error": "Сотрудник не найден"}, status=404)
        return Response(self.dto.envelope(self.dto.to_dict(employee, detail=True)))


class LegacyDepartmentListView(LegacyApiView):
    def get(self, request):
        rows = self.service.departments(company=self.param(request, "COMPANY_PARAM"))
        return Response(LegacyDepartmentDTO().to_list(rows))
