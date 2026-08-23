from __future__ import annotations

from django.db import models
from django.utils import timezone


class EmployeeQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_active=True, is_hidden=False)


class Employee(models.Model):

    object_guid = models.UUIDField("objectGUID", unique=True, db_index=True)
    sam_account_name = models.CharField("sAMAccountName", max_length=128, blank=True, db_index=True)
    user_principal_name = models.CharField("UPN", max_length=255, blank=True)
    distinguished_name = models.CharField("DN", max_length=512, blank=True)

    display_name = models.CharField("Отображаемое имя", max_length=255, blank=True)
    full_name = models.CharField("ФИО", max_length=255, blank=True, db_index=True)
    last_name = models.CharField("Фамилия", max_length=128, blank=True)
    first_name = models.CharField("Имя", max_length=128, blank=True)
    middle_name = models.CharField("Отчество", max_length=128, blank=True)

    email = models.CharField("Email", max_length=254, blank=True, db_index=True)
    phone = models.CharField("Телефон", max_length=64, blank=True)
    mobile_phone = models.CharField("Мобильный", max_length=64, blank=True)
    internal_phone = models.CharField("Внутренний", max_length=32, blank=True)
    search_phone = models.CharField(
        "Телефоны (цифры)", max_length=128, blank=True, db_index=True,
        help_text="Служебное поле для поиска по номеру без форматирования.",
    )

    department = models.CharField("Подразделение", max_length=255, blank=True, db_index=True)
    title = models.CharField("Должность", max_length=255, blank=True)
    company = models.CharField("Организация", max_length=255, blank=True, db_index=True)
    office = models.CharField("Офис", max_length=255, blank=True)
    city = models.CharField("Город", max_length=128, blank=True)
    employee_id = models.CharField("Табельный номер", max_length=64, blank=True)
    description = models.CharField("Описание", max_length=255, blank=True)
    manager_dn = models.CharField("DN руководителя", max_length=512, blank=True)
    manager = models.ForeignKey(
        "self", verbose_name="Руководитель", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="subordinates",
    )

    is_active = models.BooleanField(
        "Активен", default=True, db_index=True,
        help_text="Снимается автоматически, если учётка пропала из выдачи AD или отключена.",
    )
    is_hidden = models.BooleanField(
        "Скрыт из API", default=False,
        help_text="Ручной флаг: сотрудник есть в AD, но не должен попадать в бота.",
    )
    ad_enabled = models.BooleanField("Учётка включена в AD", default=True)
    account_control = models.IntegerField("userAccountControl", null=True, blank=True)
    notes = models.TextField("Заметки", blank=True, help_text="Заполняется вручную, синхронизация не трогает.")
    locked_fields = models.JSONField(
        "Поля, закреплённые вручную", default=list, blank=True,
        help_text='Список полей, которые синхронизация не перезаписывает, например ["phone", "title"].',
    )

    when_created = models.DateTimeField("Создан в AD", null=True, blank=True)
    when_changed = models.DateTimeField("Изменён в AD", null=True, blank=True, db_index=True)
    usn_changed = models.BigIntegerField("uSNChanged", null=True, blank=True)
    first_seen_at = models.DateTimeField("Впервые получен", default=timezone.now)
    last_synced_at = models.DateTimeField("Последняя синхронизация", null=True, blank=True)
    deactivated_at = models.DateTimeField("Деактивирован", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    objects = EmployeeQuerySet.as_manager()

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ("full_name", "sam_account_name")
        indexes = [
            models.Index(fields=["department", "full_name"]),
            models.Index(fields=["is_active", "is_hidden"]),
        ]

    def __str__(self) -> str:
        return self.full_name or self.display_name or self.sam_account_name or str(self.object_guid)


class SyncRun(models.Model):

    class Mode(models.TextChoices):
        FULL = "full", "Полная"
        INCREMENTAL = "incremental", "Инкрементальная"

    class Status(models.TextChoices):
        RUNNING = "running", "Выполняется"
        SUCCESS = "success", "Успешно"
        FAILED = "failed", "Ошибка"

    mode = models.CharField("Режим", max_length=16, choices=Mode.choices, default=Mode.FULL)
    status = models.CharField("Статус", max_length=16, choices=Status.choices, default=Status.RUNNING)
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
