from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from unfold.decorators import action, display

from employees.models import Employee, SyncRun
from employees.tasks import sync_employees_full, sync_employees_incremental

from .base import BaseModelAdmin, CeleryTriggerMixin


@admin.register(Employee)
class EmployeeAdmin(CeleryTriggerMixin, BaseModelAdmin):
    list_display = ("full_name_col", "title", "department", "company", "contacts_col", "status_col", "last_synced_at")
    list_filter = ("is_active", "is_hidden", "ad_enabled", "company", "ldap_server", "department")
    search_fields = (
        "full_name", "display_name", "sam_account_name", "email",
        "search_phone", "department", "title", "employee_id",
    )
    ordering = ("full_name",)
    autocomplete_fields = ("manager", "company")
    date_hierarchy = "when_changed"
    actions_list = ["run_full_sync", "run_incremental_sync"]

    readonly_fields = (
        "object_guid", "sam_account_name", "user_principal_name", "distinguished_name",
        "ldap_server", "ad_enabled", "account_control", "when_created", "when_changed",
        "usn_changed", "first_seen_at", "last_synced_at",
    )
    fieldsets = (
        ("Сотрудник", {
            "fields": ("full_name", "display_name", ("last_name", "first_name", "middle_name"), "title"),
        }),
        ("Контакты", {
            "fields": ("email", ("phone", "mobile_phone", "internal_phone"), "search_phone"),
        }),
        ("Оргструктура", {
            "fields": ("company", "company_name", "department", "office", "city",
                       "employee_id", "manager", "manager_dn"),
        }),
        ("Публикация", {
            "fields": ("is_active", "is_hidden", "locked_fields", "notes", "description"),
        }),
        ("Данные Active Directory", {
            "classes": ("collapse",),
            "fields": (
                "object_guid", "sam_account_name", "user_principal_name", "distinguished_name",
                "ldap_server", "ad_enabled", "account_control", "when_created", "when_changed",
                "usn_changed", "first_seen_at", "last_synced_at", "deactivated_at",
                "created_at", "updated_at",
            ),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("manager", "company", "ldap_server")

    @display(description="ФИО", ordering="full_name")
    def full_name_col(self, obj):
        return obj.full_name or obj.display_name or obj.sam_account_name

    @display(description="Контакты")
    def contacts_col(self, obj):
        return format_html("{}<br><span style='opacity:.7'>{}</span>", obj.email or "—", obj.any_phone or "—")

    @display(
        description="Статус",
        label={"в справочнике": "success", "скрыт": "warning", "неактивен": "danger"},
    )
    def status_col(self, obj):
        if not obj.is_active:
            return "неактивен"
        return "скрыт" if obj.is_hidden else "в справочнике"

    @action(description="Полная синхронизация с AD", url_path="run-full-sync")
    def run_full_sync(self, request):
        self.enqueue(request, sync_employees_full, "Полная синхронизация запущена.")
        return redirect(reverse("admin:employees_employee_changelist"))

    @action(description="Инкрементальная синхронизация", url_path="run-incremental-sync")
    def run_incremental_sync(self, request):
        self.enqueue(request, sync_employees_incremental, "Инкрементальная синхронизация запущена.")
        return redirect(reverse("admin:employees_employee_changelist"))


@admin.register(SyncRun)
class SyncRunAdmin(BaseModelAdmin):
    list_display = (
        "started_at", "company", "mode", "status_col", "trigger",
        "entries_read", "created", "updated", "deactivated", "duration_col",
    )
    list_filter = ("mode", "status", "trigger", "company", "dry_run")
    date_hierarchy = "started_at"
    ordering = ("-started_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @display(
        description="Статус",
        label={"Успешно": "success", "Выполняется": "info", "Ошибка": "danger"},
    )
    def status_col(self, obj):
        return obj.get_status_display()

    @display(description="Длительность")
    def duration_col(self, obj):
        return f"{obj.duration_seconds} с" if obj.duration_seconds is not None else "—"
