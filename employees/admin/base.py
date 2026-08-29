from django.contrib import messages
from unfold.admin import ModelAdmin


class BaseModelAdmin(ModelAdmin):
    list_per_page = 50
    readonly_base_fields = ("created_at", "updated_at", "deactivated_at")

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        model_fields = {f.name for f in self.model._meta.get_fields()}
        return fields + tuple(
            name for name in self.readonly_base_fields
            if name in model_fields and name not in fields
        )

    def notify(self, request, message: str, level=messages.SUCCESS):
        self.message_user(request, message, level)


class CeleryTriggerMixin:
    def enqueue(self, request, task, message: str, **kwargs):
        from employees.services.celery_status import dispatch

        result = dispatch(task, **kwargs)
        if result["queued"]:
            self.message_user(
                request,
                f"{message} Задача поставлена в очередь Celery (id {result['task_id']}).",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                f"{message} Celery недоступен ({result['error']}), выполнено синхронно.",
                messages.WARNING,
            )
        return result
