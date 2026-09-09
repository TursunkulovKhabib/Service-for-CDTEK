from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from .abstract import BaseModel


class ApiClient(BaseModel):
    """Клиент старого API: логин, пароль и список разрешённых методов.

    Заводится в админке, поэтому новых потребителей можно подключать без
    выкладки кода. Пароль хранится только хешем.
    """

    login = models.CharField("Логин", max_length=150, unique=True, db_index=True)
    password_hash = models.CharField("Пароль (хеш)", max_length=256, blank=True, editable=False)
    description = models.CharField(
        "Назначение", max_length=255, blank=True,
        help_text="Какое приложение ходит под этим логином и кто владелец.",
    )
    permissions = models.JSONField(
        "Разрешённые методы", default=list, blank=True,
        help_text="Методы старого API, доступные этому клиенту.",
    )
    last_used_at = models.DateTimeField("Последний запрос", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Клиент API"
        verbose_name_plural = "Клиенты API"
        ordering = ("login",)

    def __str__(self) -> str:
        return self.login

    def set_password(self, raw_password: str, save: bool = False):
        self.password_hash = make_password(raw_password)
        if save:
            self.save(update_fields=["password_hash", "updated_at"])
        return self

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash or not raw_password:
            return False
        return check_password(raw_password, self.password_hash)

    def allows(self, action: str) -> bool:
        if not action:
            return False
        granted = {str(item).lower() for item in self.permissions or []}
        return action in granted or canonical_action(action) in granted

    def touch(self, interval_seconds: int = 60) -> None:
        """Отмечает время запроса, но не чаще раза в минуту - чтобы не писать в БД на каждый вызов."""
        now = timezone.now()
        if self.last_used_at and (now - self.last_used_at).total_seconds() < interval_seconds:
            return
        self.last_used_at = now
        self.save(update_fields=["last_used_at", "updated_at"])

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)

    @property
    def permission_labels(self) -> list:
        labels = dict(settings.LEGACY_V1_ACTIONS)
        return [labels.get(name, name) for name in self.permissions or []]


def canonical_action(action: str) -> str:
    """Приводит номер метода к имени: '1' и 'getuserlist' - одно и то же право."""
    action = (action or "").strip().lower()
    return settings.LEGACY_V1_ACTION_ALIASES.get(action, action)


class SettingsApiClient:
    """Клиент из .env - тот же интерфейс, что у записи в БД.

    Нужен на время переезда: пока не все логины заведены в админке,
    сервис принимает и старый список из переменной окружения.
    """

    def __init__(self, login: str, password: str, permissions):
        self.login = login
        self.password = password
        self.permissions = list(permissions or [])

    def check_password(self, raw_password: str) -> bool:
        from django.utils.crypto import constant_time_compare

        return constant_time_compare(raw_password, self.password)

    def allows(self, action: str) -> bool:
        granted = {str(item).lower() for item in self.permissions}
        return action in granted or canonical_action(action) in granted

    def touch(self, interval_seconds: int = 60) -> None:
        return None
