from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from unfold.decorators import action, display

from employees.models import ApiClient
from employees.services import ApiClientService

from .base import BaseModelAdmin


class ApiClientForm(forms.ModelForm):
    new_password = forms.CharField(
        label="Пароль", required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Оставьте пустым, чтобы не менять пароль. В базе хранится только хеш.",
    )
    permissions = forms.MultipleChoiceField(
        label="Разрешённые методы", required=False,
        choices=settings.LEGACY_V1_ACTIONS, widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = ApiClient
        fields = ("login", "description", "is_active", "permissions")

    def clean_new_password(self):
        value = self.cleaned_data.get("new_password")
        if not value and not self.instance.has_password:
            raise forms.ValidationError("У нового клиента должен быть пароль.")
        return value

    def save(self, commit=True):
        client = super().save(commit=False)
        password = self.cleaned_data.get("new_password")
        if password:
            client.set_password(password)
        if commit:
            client.save()
        return client


@admin.register(ApiClient)
class ApiClientAdmin(BaseModelAdmin):
    form = ApiClientForm
    list_display = ("login", "description", "methods_col", "password_col", "last_used_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("login", "description")
    readonly_fields = ("last_used_at",)
    actions_list = ["import_from_env"]

    fieldsets = (
        ("Клиент", {"fields": ("login", "description", "is_active")}),
        ("Доступ", {"fields": ("new_password", "permissions", "last_used_at")}),
    )

    @display(description="Методы")
    def methods_col(self, obj):
        count = len(obj.permissions or [])
        return f"{count} из {len(settings.LEGACY_V1_ACTIONS)}"

    @display(description="Пароль", label={"задан": "success", "не задан": "danger"})
    def password_col(self, obj):
        return "задан" if obj.has_password else "не задан"

    @action(description="Перенести клиентов из .env", url_path="import-from-env")
    def import_from_env(self, request):
        stats = ApiClientService().import_from_settings()
        self.message_user(
            request,
            f"Перенесено логинов: {stats['created']}, уже было в базе: {stats['skipped']}.",
            messages.SUCCESS,
        )
        return redirect(reverse("admin:employees_apiclient_changelist"))
