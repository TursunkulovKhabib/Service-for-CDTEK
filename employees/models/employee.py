from django.db import models

from .abstract import ActiveQuerySet, BaseModel


class EmployeeQuerySet(ActiveQuerySet):
    def published(self):
        """То, что отдаётся наружу.

        Записи без почты отсекаются: в старом сервисе каждый запрос содержал
        "u.email is not null", и это отсекало служебные учётки вроде SR Toir.
        """
        return self.filter(is_active=True, is_hidden=False).exclude(email="")

    def for_company(self, code: str):
        return self.filter(company__code=code)

    def with_consent(self):
        return self.filter(personal_data_consent=True)


class EmployeeManager(models.Manager.from_queryset(EmployeeQuerySet)):
    pass


class Employee(BaseModel):
    object_guid = models.UUIDField("objectGUID", unique=True, db_index=True)
    sam_account_name = models.CharField("Логин", max_length=128, blank=True, db_index=True)
    user_principal_name = models.CharField("UPN", max_length=255, blank=True)
    distinguished_name = models.CharField("DN", max_length=512, blank=True)
    userid = models.CharField(
        "userid старой системы", max_length=255, blank=True, db_index=True,
        help_text="sAMAccountName@domain - ключ записи в прежнем сервисе.",
    )

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
    birthday = models.DateField("Дата рождения", null=True, blank=True)

    email = models.CharField("Email", max_length=254, blank=True, db_index=True)
    phone_mobile = models.CharField("Мобильный", max_length=128, blank=True)
    phone_mobile_work = models.CharField("Рабочий", max_length=255, blank=True)
    phone_internal = models.CharField("Внутренний", max_length=128, blank=True)
    search_phone = models.CharField("Телефоны (цифры)", max_length=128, blank=True, db_index=True)

    region = models.CharField("Регион", max_length=255, blank=True)
    office = models.CharField("Офис", max_length=255, blank=True)
    department = models.CharField("Подразделение", max_length=255, blank=True, db_index=True)
    department_code = models.CharField("Код подразделения", max_length=64, blank=True)
    title = models.CharField("Должность", max_length=255, blank=True)
    project_name = models.CharField("Проект", max_length=255, blank=True)
    description = models.CharField("Описание", max_length=255, blank=True)

    manager_dn = models.CharField("DN руководителя", max_length=512, blank=True)
    manager = models.ForeignKey(
        "self", verbose_name="Руководитель", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="subordinates",
    )

    photo_dir = models.CharField(
        "Папка с фото", max_length=255, blank=True,
        help_text="Организация и UID из 1С внутри хранилища фотографий.",
    )
    photo_hash = models.CharField("Отпечаток фото", max_length=64, blank=True)
    photo_updated_at = models.DateTimeField("Фото обновлено", null=True, blank=True)

    is_hidden = models.BooleanField("Скрыт из API", default=False)
    ad_enabled = models.BooleanField("Учётка включена в AD", default=True)
    account_control = models.IntegerField("userAccountControl", null=True, blank=True)
    personal_data_consent = models.BooleanField("Согласие на обработку ПДн", default=False)
    notes = models.TextField("Заметки", blank=True)
    locked_fields = models.JSONField("Поля, закреплённые вручную", default=list, blank=True)

    zup_uid = models.CharField("UID в 1С ЗУП", max_length=64, blank=True, db_index=True)
    zup_state = models.CharField("Статус в 1С ЗУП", max_length=128, blank=True)
    zup_state_dateto = models.DateField("Статус до", null=True, blank=True)
    do_user_uid = models.CharField("UID в 1С ДО", max_length=64, blank=True)
    do_user_state = models.IntegerField("Статус в 1С ДО", default=0)
    do_user_role = models.CharField("Роль в 1С ДО", max_length=128, blank=True)
    vacation_days = models.CharField("Дни отпуска", max_length=64, blank=True)

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
        return self.phone_mobile or self.phone_mobile_work or self.phone_internal

    @property
    def is_published(self) -> bool:
        return self.is_active and not self.is_hidden and bool(self.email)

    @property
    def state(self) -> int:
        """Старая система хранила состояние числом: 1 - работает, 0 - уволен."""
        return 1 if self.is_active else 0

    @property
    def birthday_str(self) -> str:
        """День и месяц без года: год рождения наружу не отдаём."""
        return self.birthday.strftime("%d.%m") if self.birthday else ""

    @property
    def has_photo(self) -> bool:
        return bool(self.photo_hash)

    def photos(self):
        from employees.services import PhotoService

        return PhotoService()

    @property
    def photo_base64(self) -> str:
        return self.photos().base64(self, "thumb")

    @property
    def photo_big_base64(self) -> str:
        return self.photos().base64(self, "card")

    @property
    def org_id(self) -> str:
        return self.company.org_id if self.company else ""

    @property
    def org_name(self) -> str:
        return self.company.name if self.company else ""

    @property
    def country_id(self) -> str:
        return self.company.country_id if self.company else ""

    @property
    def country_name(self) -> str:
        return self.company.country_name if self.company else ""
