from django.conf import settings
from django.core.management.base import BaseCommand

from employees.repositories import EmployeeRepository
from employees.services import PhotoService


class Command(BaseCommand):
    help = "Пересоздаёт уменьшенные форматы фотографий из оригиналов на диске."

    def add_arguments(self, parser):
        parser.add_argument("--company", dest="company", default="",
                            help="Код организации, например cdtek")
        parser.add_argument("--limit", type=int, default=0, help="Ограничить число сотрудников")

    def handle(self, *args, **options):
        photos = PhotoService()
        queryset = EmployeeRepository().all().exclude(photo_hash="").select_related("company")
        if options["company"]:
            queryset = queryset.filter(company__code=options["company"])
        if options["limit"]:
            queryset = queryset[:options["limit"]]

        sizes = [name for name in settings.PHOTO_SIZES if name != "original"]
        self.stdout.write(f"Форматы: {', '.join(sizes)}")

        done = 0
        missing = 0
        for employee in queryset.iterator(chunk_size=200):
            created = photos.rebuild(employee)
            if created:
                done += 1
            else:
                missing += 1

        self.stdout.write(self.style.SUCCESS(f"Обработано сотрудников: {done}"))
        if missing:
            self.stdout.write(self.style.WARNING(
                f"Без оригинала на диске: {missing}. Помогает полная синхронизация."
            ))
