from rest_framework import serializers

from employees.models import Company, Employee, SyncRun


class ManagerDTO(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ("object_guid", "full_name", "title")


class EmployeeListDTO(serializers.ModelSerializer):
    company = serializers.CharField(source="company.name", default="", read_only=True)

    class Meta:
        model = Employee
        fields = ("object_guid", "full_name", "title", "department", "phone", "company")


class EmployeeDetailDTO(serializers.ModelSerializer):
    manager = ManagerDTO(read_only=True)
    company = serializers.CharField(source="company.name", default="", read_only=True)

    class Meta:
        model = Employee
        fields = (
            "object_guid", "sam_account_name", "full_name", "title", "department",
            "phone", "mobile_phone", "internal_phone", "email", "company",
            "office", "manager", "is_active", "last_synced_at",
        )


class CompanyDTO(serializers.ModelSerializer):
    employees = serializers.IntegerField(source="employees_active", read_only=True)

    class Meta:
        model = Company
        fields = ("code", "name", "short_name", "is_active", "employees")


class SyncRunDTO(serializers.ModelSerializer):
    duration_seconds = serializers.FloatField(read_only=True)
    company = serializers.CharField(source="company.code", default="", read_only=True)

    class Meta:
        model = SyncRun
        fields = (
            "id", "company", "mode", "status", "trigger", "started_at", "finished_at",
            "duration_seconds", "entries_read", "created", "updated", "unchanged",
            "deactivated", "skipped", "dry_run", "error",
        )
