from django.core.management.base import BaseCommand

from employees.services import CompanyService


class Command(BaseCommand):
    help = "Создаёт организации и их LDAP-подключения из settings/companies.py."

    def handle(self, *args, **options):
        stats = CompanyService().load_from_settings()
        self.stdout.write(
            self.style.SUCCESS(
                f"Организаций обработано: {stats['companies']}, "
                f"LDAP-подключений: {stats['servers']}."
            )
        )
