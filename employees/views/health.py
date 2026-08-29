from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from employees.repositories import CompanyRepository, EmployeeRepository, SyncRunRepository


@api_view(["GET"])
@permission_classes([AllowAny])
def healthcheck(request):
    employees = EmployeeRepository()
    last_run = SyncRunRepository().last_finished()
    return Response(
        {
            "status": "ok",
            "employees_total": employees.count(),
            "employees_active": employees.published().count(),
            "companies": [
                {"code": company.code, "employees": company.employees_active}
                for company in CompanyRepository().active()
            ],
            "last_sync": {
                "mode": last_run.mode,
                "company": last_run.company.code if last_run.company else None,
                "finished_at": last_run.finished_at,
                "entries_read": last_run.entries_read,
            }
            if last_run
            else None,
        }
    )
