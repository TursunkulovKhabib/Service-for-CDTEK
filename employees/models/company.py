from django.db import models

from .abstract import BaseModel


class Company(BaseModel):
    code = models.SlugField("Код", max_length=64, unique=True)
    name = models.CharField("Название", max_length=255)
    short_name = models.CharField("Короткое название", max_length=128, blank=True)
    description = models.TextField("Описание", blank=True)
    is_default = models.BooleanField("По умолчанию", default=False)

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
