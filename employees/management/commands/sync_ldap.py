from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from employees.models import SyncRun


class Command(BaseCommand):
    help = "Забирает сотрудников из AD/LDAP и складывает их в БД."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--full", action="store_true", help="Полный обход (по умолчанию)")
        mode.add_argument("--incremental", action="store_true", help="Только изменённые с прошлого запуска")
        parser.add_argument("--changed-since", help="ISO-дата для инкрементальной выборки")
        parser.add_argument("--limit", type=int, help="Ограничить число записей (отладка)")
        parser.add_argument("--dry-run", action="store_true", help="Ничего не писать в БД")
        parser.add_argument("--demo", action="store_true", help="Тянуть с публичного ldap.forumsys.com")
        parser.add_argument("--profile", choices=["ad", "openldap"])
        parser.add_argument("--server", dest="server_uri")
        parser.add_argument("--bind-dn", dest="bind_dn")
        parser.add_argument("--password", dest="bind_password")
        parser.add_argument("--base-dn", dest="base_dn")
        parser.add_argument("--ou", dest="search_ous", action="append")
        parser.add_argument("--no-ssl", action="store_true")
        parser.add_argument("--insecure", action="store_true")

    def handle(self, *args, **options):
        from employees.management.commands.ldap_test import DEMO
        from ldapsync.sync import run_sync

        overrides = dict(DEMO) if options["demo"] else {}
        for cli_name, key in {
            "profile": "PROFILE", "server_uri": "SERVER_URI", "bind_dn": "BIND_DN",
            "bind_password": "BIND_PASSWORD", "base_dn": "BASE_DN",
        }.items():
            if options.get(cli_name):
                overrides[key] = options[cli_name]
        if options.get("search_ous"):
            overrides["SEARCH_OUS"] = options["search_ous"]
        if options["no_ssl"]:
            overrides["USE_SSL"] = False
        if options["insecure"]:
            overrides["TLS_VALIDATE"] = False

        changed_since = None
        if options["changed_since"]:
            changed_since = parse_datetime(options["changed_since"])
            if changed_since is None:
                raise CommandError("--changed-since ожидает ISO-дату, например 2026-08-01T00:00:00")

        mode = SyncRun.Mode.INCREMENTAL if options["incremental"] else SyncRun.Mode.FULL

        run = run_sync(
            mode=mode,
            changed_since=changed_since,
            limit=options["limit"],
            dry_run=options["dry_run"],
            overrides=overrides,
            progress=lambda message: self.stdout.write(f"  {message}"),
        )

        self.stdout.write(self.style.MIGRATE_HEADING(f"\nСинхронизация #{run.id} ({run.get_mode_display()})"))
        self.stdout.write(f"  прочитано:      {run.entries_read}")
        self.stdout.write(f"  создано:        {run.created}")
        self.stdout.write(f"  обновлено:      {run.updated}")
        self.stdout.write(f"  без изменений:  {run.unchanged}")
        self.stdout.write(f"  деактивировано: {run.deactivated}")
        if run.dry_run:
            self.stdout.write(f"  пропущено (dry-run): {run.skipped}")
        self.stdout.write(f"  длительность:   {run.duration_seconds} с")

        if run.status != SyncRun.Status.SUCCESS:
            raise CommandError(run.error or "Синхронизация завершилась с ошибкой")
        self.stdout.write(self.style.SUCCESS("Готово"))
