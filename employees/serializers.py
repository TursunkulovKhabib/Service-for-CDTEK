from rest_framework import serializers

from .models import Employee, SyncRun


class ManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ("object_guid", "full_name", "title", "email", "phone")


class EmployeeListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Employee
        fields = (
            "object_guid", "sam_account_name", "full_name", "display_name",
            "title", "department", "company", "email",
            "phone", "mobile_phone", "internal_phone",
        )


class EmployeeDetailSerializer(serializers.ModelSerializer):
    manager = ManagerSerializer(read_only=True)

    class Meta:
        model = Employee
        fields = (
            "object_guid", "sam_account_name", "user_principal_name",
            "full_name", "display_name", "last_name", "first_name", "middle_name",
            "email", "phone", "mobile_phone", "internal_phone",
            "department", "title", "company", "office", "city",
            "employee_id", "description", "manager", "notes",
            "is_active", "ad_enabled", "when_changed", "last_synced_at",
        )


class SyncRunSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = SyncRun
        fields = (
            "id", "mode", "status", "started_at", "finished_at", "duration_seconds",
            "entries_read", "created", "updated", "unchanged", "deactivated",
            "skipped", "dry_run", "max_when_changed", "error",
        )
