from django.db import models


class BaseRepository:
    model: models.Model = None

    def get_queryset(self) -> models.QuerySet:
        return self.model.objects.all()

    def all(self) -> models.QuerySet:
        return self.get_queryset()

    def active(self) -> models.QuerySet:
        return self.get_queryset().filter(is_active=True)

    def filter(self, **kwargs) -> models.QuerySet:
        return self.get_queryset().filter(**kwargs)

    def get_by_pk(self, pk):
        return self.get_queryset().filter(pk=pk).first()

    def first(self, **kwargs):
        return self.get_queryset().filter(**kwargs).first()

    def exists(self, **kwargs) -> bool:
        return self.get_queryset().filter(**kwargs).exists()

    def count(self, **kwargs) -> int:
        return self.get_queryset().filter(**kwargs).count()

    def create(self, **fields):
        return self.model.objects.create(**fields)

    def update(self, instance, **fields):
        changed = []
        for name, value in fields.items():
            if getattr(instance, name) != value:
                setattr(instance, name, value)
                changed.append(name)
        if changed:
            instance.save()
        return instance

    def save(self, instance, update_fields=None):
        instance.save(update_fields=update_fields)
        return instance

    def delete(self, instance):
        return instance.delete()

    def bulk_create(self, objects, batch_size: int = 500):
        return self.model.objects.bulk_create(objects, batch_size=batch_size)
