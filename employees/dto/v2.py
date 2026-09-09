from django.conf import settings
from django.urls import reverse
from rest_framework import serializers

from employees.models import Company, Employee, SyncRun


class PhotoUrlsMixin(serializers.Serializer):
    photo = serializers.SerializerMethodField()

    def get_photo(self, employee) -> dict:
        if not employee.has_photo:
            return {}
        path = reverse("v2:employee-photo", args=[str(employee.object_guid)])
        request = self.context.get("request")
        urls = {}
        for size in settings.PHOTO_SIZES:
            address = f"{path}?size={size}"
            urls[size] = request.build_absolute_uri(address) if request else address
        return urls


class ManagerDTO(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ("object_guid", "full_name", "title")


class EmployeeListDTO(serializers.ModelSerializer):
    company = serializers.CharField(source="company.name", default="", read_only=True)

    class Meta:
        model = Employee
        fields = ("object_guid", "full_name", "title", "department", "phone_mobile", "company")


class EmployeeDetailDTO(PhotoUrlsMixin, serializers.ModelSerializer):
    manager = ManagerDTO(read_only=True)
    company = serializers.CharField(source="company.name", default="", read_only=True)
    birthday = serializers.CharField(source="birthday_str", read_only=True)

    class Meta:
        model = Employee
        fields = (
            "object_guid", "sam_account_name", "full_name", "title", "department",
            "phone_mobile", "phone_mobile_work", "phone_internal", "email", "company",
            "office", "region", "birthday", "photo", "manager", "is_active", "last_synced_at",
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
