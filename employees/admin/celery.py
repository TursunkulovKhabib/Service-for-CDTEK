from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.shortcuts import redirect
from django.urls import reverse
from django_celery_beat.admin import ClockedScheduleAdmin as BaseClockedAdmin
from django_celery_beat.admin import CrontabScheduleAdmin as BaseCrontabAdmin
from django_celery_beat.admin import PeriodicTaskAdmin as BasePeriodicTaskAdmin
from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    PeriodicTasks,
    SolarSchedule,
)
from django_celery_results.models import GroupResult, TaskResult
from unfold.admin import ModelAdmin
from unfold.decorators import action, display

from employees.services.celery_status import worker_status


def _unregister(*models):
    for model in models:
        try:
            admin.site.unregister(model)
        except admin.sites.NotRegistered:
            pass


_unregister(
    User, Group, PeriodicTask, IntervalSchedule, CrontabSchedule,
    SolarSchedule, ClockedSchedule, PeriodicTasks, TaskResult, GroupResult,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    pass


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


@admin.register(PeriodicTask)
class PeriodicTaskAdmin(BasePeriodicTaskAdmin, ModelAdmin):
    actions_list = ["check_workers"]

    @action(description="Проверить брокер и воркеры", url_path="check-workers")
    def check_workers(self, request):
        status = worker_status()
        if not status["broker"]:
            self.message_user(request, f"Брокер недоступен: {status['error']}", messages.ERROR)
        elif not status["workers"]:
            self.message_user(request, "Брокер доступен, но ни один воркер не отвечает.", messages.WARNING)
        else:
            self.message_user(
                request, f"Воркеры на связи: {', '.join(status['workers'])}", messages.SUCCESS
            )
        return redirect(reverse("admin:django_celery_beat_periodictask_changelist"))


@admin.register(IntervalSchedule)
class IntervalScheduleAdmin(ModelAdmin):
    pass


@admin.register(CrontabSchedule)
class CrontabScheduleAdmin(BaseCrontabAdmin, ModelAdmin):
    pass


@admin.register(SolarSchedule)
class SolarScheduleAdmin(ModelAdmin):
    pass


@admin.register(ClockedSchedule)
class ClockedScheduleAdmin(BaseClockedAdmin, ModelAdmin):
    pass


@admin.register(TaskResult)
class TaskResultAdmin(ModelAdmin):
    list_display = ("task_id", "task_name", "status_col", "date_created", "date_done")
    list_filter = ("status", "task_name")
    search_fields = ("task_id", "task_name")
    ordering = ("-date_created",)

    @display(description="Статус", label={"SUCCESS": "success", "FAILURE": "danger", "STARTED": "info"})
    def status_col(self, obj):
        return obj.status


@admin.register(GroupResult)
class GroupResultAdmin(ModelAdmin):
    list_display = ("group_id", "date_created", "date_done")
    ordering = ("-date_created",)
