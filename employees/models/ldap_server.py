import os

from django.db import models

from .abstract import BaseModel


class LdapServer(BaseModel):
    class Profile(models.TextChoices):
        AD = "ad", "Active Directory"
        OPENLDAP = "openldap", "OpenLDAP"

    class Auth(models.TextChoices):
        SIMPLE = "SIMPLE", "Simple bind"
        NTLM = "NTLM", "NTLM"
        ANONYMOUS = "ANONYMOUS", "Анонимно"

    name = models.CharField("Название", max_length=128, unique=True)
    company = models.ForeignKey(
        "employees.Company", verbose_name="Организация",
        on_delete=models.CASCADE, related_name="ldap_servers",
    )
    profile = models.CharField("Профиль каталога", max_length=16, choices=Profile.choices, default=Profile.AD)

    server_uri = models.CharField("Адрес сервера", max_length=255, help_text="ldaps://dc01.corp.local")
    port = models.PositiveIntegerField("Порт", null=True, blank=True)
    use_ssl = models.BooleanField("LDAPS", default=True)
    start_tls = models.BooleanField("StartTLS", default=False)
    tls_validate = models.BooleanField("Проверять сертификат", default=True)
    ca_certs_file = models.CharField("Файл корневого сертификата", max_length=512, blank=True)

    authentication = models.CharField("Авторизация", max_length=16, choices=Auth.choices, default=Auth.SIMPLE)
    bind_dn = models.CharField("Учётная запись", max_length=512, blank=True)
    bind_password = models.CharField(
        "Пароль", max_length=255, blank=True,
        help_text="Хранится в БД. Надёжнее оставить пустым и указать имя переменной окружения ниже.",
    )
    bind_password_env = models.CharField(
        "Пароль из переменной окружения", max_length=128, blank=True,
        help_text="Имя переменной окружения, например LDAP_CDTEK_BIND_PASSWORD.",
    )

    base_dn = models.CharField("Базовая ветка", max_length=512)
    search_ous = models.JSONField("Ветки поиска (OU)", default=list, blank=True)
    user_filter = models.CharField("Фильтр пользователей", max_length=512, blank=True)
    include_disabled = models.BooleanField("Забирать отключённые учётки", default=False)

    page_size = models.PositiveIntegerField("Размер страницы", default=500)
    timeout = models.PositiveIntegerField("Таймаут подключения, с", default=30)
    receive_timeout = models.PositiveIntegerField("Таймаут ответа, с", default=60)
    deactivate_missing = models.BooleanField("Деактивировать пропавших", default=True)
    min_entries_for_deactivation = models.PositiveIntegerField("Порог для деактивации", default=1)

    last_sync_at = models.DateTimeField("Последняя синхронизация", null=True, blank=True)
    last_sync_status = models.CharField("Результат", max_length=32, blank=True)

    class Meta:
        verbose_name = "LDAP-подключение"
        verbose_name_plural = "LDAP-подключения"
        ordering = ("company__name", "name")

    def __str__(self) -> str:
        return f"{self.name} ({self.server_uri})"

    def resolve_password(self) -> str:
        if self.bind_password_env:
            return os.environ.get(self.bind_password_env, "")
        return self.bind_password

    @property
    def password_source(self) -> str:
        if self.bind_password_env:
            return f"переменная окружения {self.bind_password_env}"
        return "хранится в БД" if self.bind_password else "не задан"

    def as_overrides(self) -> dict:
        return {
            "PROFILE": self.profile,
            "SERVER_URI": self.server_uri,
            "PORT": self.port,
            "USE_SSL": self.use_ssl,
            "START_TLS": self.start_tls,
            "TLS_VALIDATE": self.tls_validate,
            "CA_CERTS_FILE": self.ca_certs_file or None,
            "AUTHENTICATION": self.authentication,
            "BIND_DN": self.bind_dn,
            "BIND_PASSWORD": self.resolve_password(),
            "BASE_DN": self.base_dn,
            "SEARCH_OUS": list(self.search_ous or []),
            "USER_FILTER": self.user_filter,
            "INCLUDE_DISABLED": self.include_disabled,
            "PAGE_SIZE": self.page_size,
            "TIMEOUT": self.timeout,
            "RECEIVE_TIMEOUT": self.receive_timeout,
            "DEACTIVATE_MISSING": self.deactivate_missing,
            "MIN_ENTRIES_FOR_DEACTIVATION": self.min_entries_for_deactivation,
        }
