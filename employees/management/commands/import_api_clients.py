from django.core.management.base import BaseCommand

from employees.services import ApiClientService


class Command(BaseCommand):
    help = "Переносит клиентов старого API из переменной LEGACY_V1_CLIENTS в базу."

    def handle(self, *args, **options):
        stats = ApiClientService().import_from_settings()
        self.stdout.write(self.style.SUCCESS(
            f"Создано клиентов: {stats['created']}, уже были в базе: {stats['skipped']}."
        ))
