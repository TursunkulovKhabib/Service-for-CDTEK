from django.db import models

from .abstract import ActiveQuerySet, BaseModel


class EmployeeQuerySet(ActiveQuerySet):
    def published(self):
        return self.filter(is_active=True, is_hidden=False)

    def for_company(self, code: str):
        return self.filter(company__code=code)


class EmployeeManager(models.Manager.from_queryset(EmployeeQuerySet)):
    pass


class Employee(BaseModel):
    object_guid = models.UUIDField("objectGUID", unique=True, db_index=True)
    sam_account_name = models.CharField("Логин", max_length=128, blank=True, db_index=True)
    user_principal_name = models.CharField("UPN", max_length=255, blank=True)
    distinguished_name = models.CharField("DN", max_length=512, blank=True)

    company = models.ForeignKey(
        "employees.Company", verbose_name="Организация", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="employees",
    )
    ldap_server = models.ForeignKey(
        "employees.LdapServer", verbose_name="Источник (LDAP)", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="employees",
    )
    company_name = models.CharField("Организация в AD", max_length=255, blank=True)

    display_name = models.CharField("Отображаемое имя", max_length=255, blank=True)
    full_name = models.CharField("ФИО", max_length=255, blank=True, db_index=True)
    last_name = models.CharField("Фамилия", max_length=128, blank=True)
    first_name = models.CharField("Имя", max_length=128, blank=True)
    middle_name = models.CharField("Отчество", max_length=128, blank=True)

    email = models.CharField("Email", max_length=254, blank=True, db_index=True)
    phone = models.CharField("Телефон", max_length=64, blank=True)
    mobile_phone = models.CharField("Мобильный", max_length=64, blank=True)
    internal_phone = models.CharField("Внутренний", max_length=32, blank=True)
    search_phone = models.CharField("Телефоны (цифры)", max_length=128, blank=True, db_index=True)

    department = models.CharField("Подразделение", max_length=255, blank=True, db_index=True)
    title = models.CharField("Должность", max_length=255, blank=True)
    office = models.CharField("Офис", max_length=255, blank=True)
    city = models.CharField("Город", max_length=128, blank=True)
    employee_id = models.CharField("Табельный номер", max_length=64, blank=True)
    description = models.CharField("Описание", max_length=255, blank=True)
    manager_dn = models.CharField("DN руководителя", max_length=512, blank=True)
    manager = models.ForeignKey(
        "self", verbose_name="Руководитель", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="subordinates",
    )

    is_hidden = models.BooleanField("Скрыт из API", default=False)
    ad_enabled = models.BooleanField("Учётка включена в AD", default=True)
    account_control = models.IntegerField("userAccountControl", null=True, blank=True)
    notes = models.TextField("Заметки", blank=True)
    locked_fields = models.JSONField("Поля, закреплённые вручную", default=list, blank=True)

    when_created = models.DateTimeField("Создан в AD", null=True, blank=True)
    when_changed = models.DateTimeField("Изменён в AD", null=True, blank=True, db_index=True)
    usn_changed = models.BigIntegerField("uSNChanged", null=True, blank=True)
    first_seen_at = models.DateTimeField("Впервые получен", null=True, blank=True)
    last_synced_at = models.DateTimeField("Последняя синхронизация", null=True, blank=True)

    objects = EmployeeManager()

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ("full_name", "sam_account_name")
        indexes = [
            models.Index(fields=["department", "full_name"]),
            models.Index(fields=["is_active", "is_hidden"]),
            models.Index(fields=["company", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.full_name or self.display_name or self.sam_account_name or str(self.object_guid)

    @property
    def any_phone(self) -> str:
        return self.phone or self.mobile_phone or self.internal_phone

    @property
    def is_published(self) -> bool:
        return self.is_active and not self.is_hidden
