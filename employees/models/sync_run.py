from django.db import models
from django.utils import timezone

from .abstract import TimeStampedModel


class SyncRun(TimeStampedModel):
    class Mode(models.TextChoices):
        FULL = "full", "Полная"
        INCREMENTAL = "incremental", "Инкрементальная"

    class Status(models.TextChoices):
        RUNNING = "running", "Выполняется"
        SUCCESS = "success", "Успешно"
        FAILED = "failed", "Ошибка"

    class Trigger(models.TextChoices):
        ADMIN = "admin", "Админка"
        CELERY = "celery", "Celery"
        CLI = "cli", "Консоль"
        API = "api", "API"

    company = models.ForeignKey(
        "employees.Company", verbose_name="Организация", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sync_runs",
    )
    ldap_server = models.ForeignKey(
        "employees.LdapServer", verbose_name="LDAP-подключение", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sync_runs",
    )

    mode = models.CharField("Режим", max_length=16, choices=Mode.choices, default=Mode.FULL)
    status = models.CharField("Статус", max_length=16, choices=Status.choices, default=Status.RUNNING)
    trigger = models.CharField("Запущено из", max_length=16, choices=Trigger.choices, default=Trigger.CLI)
    task_id = models.CharField("ID задачи Celery", max_length=128, blank=True)

    started_at = models.DateTimeField("Начало", default=timezone.now)
    finished_at = models.DateTimeField("Окончание", null=True, blank=True)
    changed_since = models.DateTimeField("Выборка изменений с", null=True, blank=True)

    entries_read = models.IntegerField("Прочитано записей", default=0)
    created = models.IntegerField("Создано", default=0)
    updated = models.IntegerField("Обновлено", default=0)
    unchanged = models.IntegerField("Без изменений", default=0)
    deactivated = models.IntegerField("Деактивировано", default=0)
    skipped = models.IntegerField("Пропущено", default=0)

    dry_run = models.BooleanField("Пробный прогон", default=False)
    max_when_changed = models.DateTimeField("Максимальный whenChanged", null=True, blank=True)
    error = models.TextField("Ошибка", blank=True)

    class Meta:
        verbose_name = "Запуск синхронизации"
        verbose_name_plural = "Запуски синхронизации"
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"{self.get_mode_display()} {self.started_at:%d.%m.%Y %H:%M} - {self.get_status_display()}"

    @property
    def duration_seconds(self):
        if not self.finished_at:
            return None
        return round((self.finished_at - self.started_at).total_seconds(), 1)

    def finish(self, status: str, error: str = ""):
        self.status = status
        self.error = error
        self.finished_at = timezone.now()
        self.save()
        return self
