from django.db import models

from .abstract import BaseModel


class Company(BaseModel):
    code = models.SlugField("Код", max_length=64, unique=True)
    name = models.CharField("Название", max_length=255)
    short_name = models.CharField("Короткое название", max_length=128, blank=True)
    description = models.TextField("Описание", blank=True)
    is_default = models.BooleanField("По умолчанию", default=False)

    org_id = models.CharField("org_id старой системы", max_length=128, blank=True, db_index=True)
    domain = models.CharField("Домен AD", max_length=128, blank=True)
    country_id = models.CharField("Код страны", max_length=8, blank=True, default="ru")
    country_name = models.CharField("Страна", max_length=128, blank=True, default="Россия")
    integrations = models.JSONField(
        "Интеграции 1С", default=dict, blank=True,
        help_text="URL и логины сервисов 1С ЗУП/ДО. Пароли берутся из переменных окружения.",
    )

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name or self.code

    @property
    def employees_total(self) -> int:
        return self.employees.count()

    @property
    def employees_active(self) -> int:
        return self.employees.filter(is_active=True, is_hidden=False).count()
