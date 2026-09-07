from django.apps import AppConfig
from django.core.checks import Warning, register


class EmployeesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "employees"
    verbose_name = "Справочник сотрудников"

    def ready(self):
        register(check_database_supports_search)


def check_database_supports_search(app_configs, **kwargs):
    """SQLite сравнивает без учёта регистра только латиницу.

    Поиск "иванов" не найдёт "Иванов" - для справочника это неприемлемо,
    поэтому предупреждаем сразу, а не при разборе жалоб на поиск.
    """
    from django.db import connection

    if connection.vendor != "sqlite":
        return []
    return [
        Warning(
            "База SQLite: поиск по русским ФИО работает с учётом регистра.",
            hint=(
                "Годится для проверки подключения к AD и маппинга, но не для API "
                "справочника. Для поиска используйте PostgreSQL: DB_ENGINE=postgres."
            ),
            id="employees.W001",
        )
    ]
