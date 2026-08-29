from django.db import models
from django.utils import timezone


class ActiveQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

    def deactivate(self):
        return self.update(is_active=False, deactivated_at=timezone.now())

    def activate(self):
        return self.update(is_active=True, deactivated_at=None)


class BaseManager(models.Manager.from_queryset(ActiveQuerySet)):
    pass


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("Создано", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        abstract = True


class ActivatableModel(models.Model):
    is_active = models.BooleanField("Активно", default=True, db_index=True)
    deactivated_at = models.DateTimeField("Деактивировано", null=True, blank=True)

    class Meta:
        abstract = True

    def activate(self, save: bool = True):
        self.is_active = True
        self.deactivated_at = None
        if save:
            self.save(update_fields=["is_active", "deactivated_at", "updated_at"])
        return self

    def deactivate(self, save: bool = True):
        self.is_active = False
        self.deactivated_at = timezone.now()
        if save:
            self.save(update_fields=["is_active", "deactivated_at", "updated_at"])
        return self


class BaseModel(TimeStampedModel, ActivatableModel):
    objects = BaseManager()

    class Meta:
        abstract = True

    def set_fields(self, values: dict, skip: set = None) -> list:
        skip = skip or set()
        changed = []
        for name, value in values.items():
            if name in skip or not hasattr(self, name):
                continue
            if getattr(self, name) != value:
                setattr(self, name, value)
                changed.append(name)
        return changed
