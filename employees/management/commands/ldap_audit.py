from django.core.management.base import BaseCommand, CommandError

from ldapsync.client import LdapClient, LdapSyncError
from ldapsync.config import load_settings
from ldapsync.mapping import build_payload, clean_str, parse_birthday

DATE_CANDIDATES = {
    "MM.dd.yyyy": "%m.%d.%Y",
    "dd.MM.yyyy": "%d.%m.%Y",
    "yyyy-MM-dd": "%Y-%m-%d",
    "yyyy.MM.dd": "%Y.%m.%d",
    "dd-MM-yyyy": "%d-%m-%Y",
    "MM/dd/yyyy": "%m/%d/%Y",
}


class Command(BaseCommand):
    help = (
        "Сверка маппинга с каталогом: сколько записей имеет каждый атрибут. "
        "Значения не выводятся и в БД ничего не пишется."
    )

    def add_arguments(self, parser):
        parser.add_argument("--connection", dest="connection_name", required=True,
                            help="Название LDAP-подключения из админки")
        parser.add_argument("--limit", type=int, default=200,
                            help="Сколько записей просмотреть (по умолчанию 200)")
        parser.add_argument("--show-example", action="store_true",
                            help="Показать одну запись целиком - в ней персональные данные")

    def handle(self, *args, **options):
        server = resolve_connection(options["connection_name"])

        config = load_settings(server.as_overrides())
        requested = config.profile.attributes()
        filled = {name: 0 for name in requested}
        mapped_filled = {}
        date_shapes = {name: {} for name in config.profile.date_attributes.values()}
        date_parsed = {name: 0 for name in config.profile.date_attributes.values()}
        date_candidates = {name: {} for name in config.profile.date_attributes.values()}
        flag_on = {name: 0 for name in config.profile.flag_attributes.values()}
        flag_values = {name: {} for name in config.profile.flag_attributes.values()}
        total = 0
        example = None

        try:
            with LdapClient(config) as client:
                available = client.supported_attributes(requested)
                for entry in client.iter_users(limit=options["limit"]):
                    total += 1
                    attrs = entry.get("attributes") or {}
                    for name in available:
                        value = attrs.get(name)
                        if value not in (None, "", [], b""):
                            filled[name] += 1
                    for name in date_shapes:
                        raw = clean_str(attrs.get(name), 64)
                        if raw:
                            shape = f"{len(raw)} симв."
                            date_shapes[name][shape] = date_shapes[name].get(shape, 0) + 1
                            if parse_birthday(raw, config.birthday_formats or None):
                                date_parsed[name] += 1
                            for label, pattern in DATE_CANDIDATES.items():
                                if parse_birthday(raw, (pattern,)):
                                    date_candidates[name][label] = (
                                        date_candidates[name].get(label, 0) + 1
                                    )

                    for name in flag_values:
                        raw = clean_str(attrs.get(name), 32)
                        if raw:
                            flag_values[name][raw] = flag_values[name].get(raw, 0) + 1
                            if raw == "1":
                                flag_on[name] += 1

                    payload = build_payload(entry, config.profile, config.birthday_formats)
                    for field, value in payload.items():
                        if value not in (None, "", b"", False):
                            mapped_filled[field] = mapped_filled.get(field, 0) + 1
                    if example is None:
                        example = payload
        except LdapSyncError as exc:
            raise CommandError(str(exc)) from exc

        if not total:
            self.stdout.write(self.style.WARNING("Каталог не вернул ни одной записи."))
            return

        missing = sorted(set(requested) - set(available))
        if missing:
            self.stdout.write(self.style.WARNING(
                "\nНет в схеме каталога (маппинг по ним работать не будет):\n  "
                + ", ".join(missing)
            ))

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nАтрибуты каталога - заполнено из {total} записей"
        ))
        for name in sorted(available):
            count = filled[name]
            share = round(count * 100 / total)
            mark = "  " if count else "! "
            self.stdout.write(f"  {mark}{name:32} {count:5} ({share:3}%)")

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nПоля модели после маппинга - заполнено из {total} записей"
        ))
        for field in sorted(mapped_filled):
            count = mapped_filled[field]
            self.stdout.write(f"    {field:32} {count:5} ({round(count * 100 / total):3}%)")

        for name, shapes in date_shapes.items():
            if not shapes:
                continue
            filled_count = sum(shapes.values())
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\nДаты в {name} - значения не выводятся"
            ))
            self.stdout.write(f"    заполнено:  {filled_count}")
            self.stdout.write(f"    распознано: {date_parsed[name]}")
            for shape, count in sorted(shapes.items()):
                self.stdout.write(f"      {shape:12} {count:5}")
            self.stdout.write("    подходит формат:")
            for label, count in sorted(date_candidates[name].items(), key=lambda pair: -pair[1]):
                share = round(count * 100 / filled_count)
                mark = " <- покрывает все значения" if count == filled_count else ""
                self.stdout.write(f"      {label:12} {count:5} ({share:3}%){mark}")

            if date_parsed[name] < filled_count:
                self.stdout.write(self.style.WARNING(
                    f"    не разобрано {filled_count - date_parsed[name]} значений - "
                    "нужен ещё один формат даты"
                ))

        for name, values in flag_values.items():
            if not values:
                continue
            self.stdout.write(self.style.MIGRATE_HEADING(f"\nЗначения флага {name}"))
            for value, count in sorted(values.items(), key=lambda pair: -pair[1]):
                mark = " <- срабатывает" if value == "1" else ""
                self.stdout.write(f"    {value:20} {count:5}{mark}")

        empty_fields = sorted(
            f for f in build_payload({"dn": "", "attributes": {}}, config.profile)
            if f not in mapped_filled
        )
        if empty_fields:
            self.stdout.write(self.style.WARNING(
                "\nПусто у всех записей - проверить маппинг:\n  " + ", ".join(empty_fields)
            ))

        if options["show_example"] and example:
            self.stdout.write(self.style.MIGRATE_HEADING("\nПример записи"))
            for field, value in sorted(example.items()):
                if field == "photo":
                    value = f"<{len(value or b'')} байт>"
                self.stdout.write(f"    {field:32} {value}")

        self.stdout.write(self.style.SUCCESS(f"\nПросмотрено записей: {total}"))


def resolve_connection(name: str):
    """Находит подключение по названию, а при ошибке показывает список доступных."""
    from django.core.management.base import CommandError

    from employees.repositories import LdapServerRepository

    repository = LdapServerRepository()
    server = repository.get_by_name(name)
    if server is not None:
        return server

    available = list(repository.all().values_list("name", flat=True))
    if not available:
        raise CommandError(
            "В базе нет ни одного LDAP-подключения. Выполните: manage.py load_companies"
        )
    raise CommandError(
        f"LDAP-подключение '{name}' не найдено. Доступны: " + ", ".join(f"'{n}'" for n in available)
    )
