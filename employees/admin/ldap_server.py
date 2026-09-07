from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from unfold.decorators import action, display

from employees.models import Company, LdapServer
from employees.services import CompanyService
from employees.tasks import sync_employees_full

from .base import BaseModelAdmin, CeleryTriggerMixin


class LdapServerForm(forms.ModelForm):
    bind_password = forms.CharField(
        label="Пароль", required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Оставьте пустым, чтобы не менять сохранённый пароль.",
    )

    class Meta:
        model = LdapServer
        fields = "__all__"

    def clean_bind_password(self):
        value = self.cleaned_data.get("bind_password")
        if not value and self.instance.pk:
            return self.instance.bind_password
        return value


@admin.register(LdapServer)
class LdapServerAdmin(CeleryTriggerMixin, BaseModelAdmin):
    form = LdapServerForm
    list_display = ("name", "company", "profile", "server_uri", "security_col",
                    "password_col", "last_sync_at", "status_col")
    list_filter = ("company", "profile", "is_active", "use_ssl")
    search_fields = ("name", "server_uri", "base_dn", "bind_dn")
    actions_list = ["test_connection", "sync_now"]
    readonly_fields = ("last_sync_at", "last_sync_status")

    fieldsets = (
        ("Подключение", {
            "fields": ("name", "company", "is_active", "profile", "server_uri", "port"),
        }),
        ("Безопасность", {
            "fields": ("use_ssl", "start_tls", "tls_validate", "ca_certs_file",
                       "authentication", "domain", "bind_dn", "bind_password",
                       "bind_password_env"),
        }),
        ("Поиск", {
            "fields": ("base_dn", "search_ous", "user_filter", "include_disabled", "page_size"),
        }),
        ("Синхронизация", {
            "fields": ("timeout", "receive_timeout", "deactivate_missing",
                       "min_entries_for_deactivation", "last_sync_at", "last_sync_status"),
        }),
    )

    @display(description="Защита", label={"LDAPS": "success", "StartTLS": "info", "без TLS": "danger"})
    def security_col(self, obj):
        if obj.use_ssl:
            return "LDAPS"
        return "StartTLS" if obj.start_tls else "без TLS"

    @display(description="Пароль")
    def password_col(self, obj):
        return obj.password_source

    @display(description="Последний результат", label={"success": "success", "failed": "danger"})
    def status_col(self, obj):
        return obj.last_sync_status or "—"

    @action(description="Проверить подключение", url_path="test-connection")
    def test_connection(self, request):
        from ldapsync.client import LdapClient, LdapSyncError
        from ldapsync.config import load_settings

        for server in LdapServer.objects.filter(is_active=True):
            try:
                with LdapClient(load_settings(server.as_overrides())) as client:
                    info = client.server_info()
                self.message_user(request, f"{server.name}: подключение успешно, {info}", messages.SUCCESS)
            except LdapSyncError as exc:
                self.message_user(request, f"{server.name}: {exc}", messages.ERROR)
        return redirect(reverse("admin:employees_ldapserver_changelist"))

    @action(description="Синхронизировать все подключения", url_path="sync-now")
    def sync_now(self, request):
        self.enqueue(request, sync_employees_full, "Синхронизация всех подключений запущена.")
        return redirect(reverse("admin:employees_ldapserver_changelist"))


@admin.register(Company)
class CompanyAdmin(BaseModelAdmin):
    list_display = ("name", "code", "is_default", "is_active", "employees_col", "servers_col")
    list_filter = ("is_active", "is_default")
    search_fields = ("name", "code", "short_name")
    actions_list = ["load_from_settings"]

    @display(description="Сотрудников")
    def employees_col(self, obj):
        return f"{obj.employees_active} из {obj.employees_total}"

    @display(description="LDAP-подключений")
    def servers_col(self, obj):
        return obj.ldap_servers.count()

    @action(description="Загрузить организации из настроек", url_path="load-from-settings")
    def load_from_settings(self, request):
        stats = CompanyService().load_from_settings()
        self.message_user(
            request,
            f"Организаций обработано: {stats['companies']}, LDAP-подключений: {stats['servers']}.",
            messages.SUCCESS,
        )
        return redirect(reverse("admin:employees_company_changelist"))
