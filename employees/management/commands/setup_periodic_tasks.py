from django.conf import settings
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Создаёт/обновляет периодические задачи синхронизации с AD."

    def handle(self, *args, **options):
        interval, _ = IntervalSchedule.objects.get_or_create(
            every=settings.LDAP_SYNC_INCREMENTAL_MINUTES,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.update_or_create(
            name="AD: инкрементальная синхронизация",
            defaults={
                "task": "employees.sync_employees_incremental",
                "interval": interval,
                "crontab": None,
                "enabled": True,
            },
        )

        minute, hour, day_of_month, month_of_year, day_of_week = settings.LDAP_SYNC_FULL_CRON.split()
        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            day_of_week=day_of_week,
            timezone=settings.TIME_ZONE,
        )
        PeriodicTask.objects.update_or_create(
            name="AD: полная синхронизация",
            defaults={
                "task": "employees.sync_employees_full",
                "crontab": crontab,
                "interval": None,
                "enabled": True,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Расписание создано: инкрементально каждые "
                f"{settings.LDAP_SYNC_INCREMENTAL_MINUTES} мин, "
                f"полная синхронизация по cron '{settings.LDAP_SYNC_FULL_CRON}'."
            )
        )
