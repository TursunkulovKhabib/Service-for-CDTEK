import json

from django.core.management.base import BaseCommand, CommandError

from ldapsync.client import LdapClient, LdapSyncError
from ldapsync.config import load_settings
from ldapsync.mapping import build_payload

DEMO = {
    "PROFILE": "openldap",
    "SERVER_URI": "ldap://ldap.forumsys.com:389",
    "USE_SSL": False,
    "START_TLS": False,
    "BIND_DN": "cn=read-only-admin,dc=example,dc=com",
    "BIND_PASSWORD": "password",
    "BASE_DN": "dc=example,dc=com",
    "SEARCH_OUS": [],
    "AUTHENTICATION": "SIMPLE",
}


class Command(BaseCommand):
    help = "Тестовый LDAP-запрос с забором данных (без записи в БД)."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Публичный ldap.forumsys.com")
        parser.add_argument("--profile", choices=["ad", "openldap"], help="Диалект каталога")
        parser.add_argument("--server", dest="server_uri", help="ldaps://dc01.corp.local")
        parser.add_argument("--connection", dest="connection_name",
                            help="Название LDAP-подключения из админки")
        parser.add_argument("--port", type=int)
        parser.add_argument("--bind-dn", dest="bind_dn")
        parser.add_argument("--password", dest="bind_password")
        parser.add_argument("--base-dn", dest="base_dn")
        parser.add_argument("--ou", dest="search_ous", action="append", help="Можно указывать несколько раз")
        parser.add_argument("--filter", dest="user_filter")
        parser.add_argument("--no-ssl", action="store_true", help="Простой LDAP вместо LDAPS")
        parser.add_argument("--start-tls", action="store_true")
        parser.add_argument("--insecure", action="store_true", help="Не проверять сертификат (только тесты)")
        parser.add_argument("--include-disabled", action="store_true")
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--raw", action="store_true", help="Показать сырые атрибуты каталога")
        parser.add_argument("--json", action="store_true", help="Вывод в JSON")

    def describe(self, payload: dict, entry: dict) -> str:
        """Карточка сотрудника для глаз - поля берём мягко, чтобы вывод не падал."""

        def value(name: str) -> str:
            result = payload.get(name)
            if isinstance(result, (bytes, bytearray)):
                return f"<{len(result)} байт>"
            return str(result) if result not in (None, "", False) else "—"

        lines = [
            f"  • {value('full_name')}",
            f"      guid:    {value('object_guid')}",
            f"      login:   {value('sam_account_name')}",
            f"      почта:   {value('email')}",
            f"      моб.:    {value('phone_mobile')}",
            f"      раб.:    {value('phone_mobile_work')}",
            f"      вн.:     {value('phone_internal')}",
            f"      подр.:   {value('department')} / {value('title')}",
            f"      регион:  {value('region')} / {value('office')}",
            f"      д.р.:    {value('birthday')}   ПДн: {value('personal_data_consent')}",
            f"      ЗУП:     {value('zup_uid')}   проект: {value('project_name')}",
            f"      фото:    {value('photo')}",
            f"      dn:      {entry['dn']}",
        ]
        return "\n".join(lines)

    def handle(self, *args, **options):
        from employees.management.commands.ldap_audit import resolve_connection

        overrides = {}
        if options.get("connection_name"):
            overrides.update(resolve_connection(options["connection_name"]).as_overrides())
        if options["demo"]:
            overrides.update(DEMO)

        cli_map = {
            "profile": "PROFILE", "server_uri": "SERVER_URI", "port": "PORT",
            "bind_dn": "BIND_DN", "bind_password": "BIND_PASSWORD", "base_dn": "BASE_DN",
            "user_filter": "USER_FILTER",
        }
        for cli_name, key in cli_map.items():
            if options.get(cli_name):
                overrides[key] = options[cli_name]
        if options.get("search_ous"):
            overrides["SEARCH_OUS"] = options["search_ous"]
        if options["no_ssl"]:
            overrides["USE_SSL"] = False
        if options["start_tls"]:
            overrides["START_TLS"] = True
        if options["insecure"]:
            overrides["TLS_VALIDATE"] = False
        if options["include_disabled"]:
            overrides["INCLUDE_DISABLED"] = True

        settings_obj = load_settings(overrides)
        limit = options["limit"]

        self.stdout.write(self.style.MIGRATE_HEADING("Параметры подключения"))
        self.stdout.write(f"  сервер:  {settings_obj.host}:{settings_obj.effective_port} (ssl={settings_obj.effective_use_ssl})")
        self.stdout.write(f"  профиль: {settings_obj.profile.name}")
        self.stdout.write(f"  bind:    {settings_obj.bind_dn or '<anonymous>'}")
        self.stdout.write(f"  базы:    {', '.join(settings_obj.search_bases)}")
        self.stdout.write(f"  фильтр:  {settings_obj.build_filter()}")

        results = []
        try:
            with LdapClient(settings_obj) as client:
                info = client.server_info()
                self.stdout.write(self.style.MIGRATE_HEADING("\nСервер"))
                for key, value in info.items():
                    self.stdout.write(f"  {key}: {value}")

                self.stdout.write(self.style.MIGRATE_HEADING("\nЗаписи"))
                for entry in client.iter_users(limit=limit):
                    payload = build_payload(entry, settings_obj.profile)
                    results.append({"raw": entry, "mapped": payload} if options["raw"] else payload)
                    if options["json"]:
                        continue
                    self.stdout.write(self.describe(payload, entry))
                    if options["raw"]:
                        self.stdout.write(f"      raw:   {entry['attributes']}")
        except LdapSyncError as exc:
            raise CommandError(str(exc)) from exc

        if options["json"]:
            self.stdout.write(json.dumps(results, ensure_ascii=False, indent=2, default=str))

        self.stdout.write(self.style.SUCCESS(f"\nПолучено записей: {len(results)}"))
