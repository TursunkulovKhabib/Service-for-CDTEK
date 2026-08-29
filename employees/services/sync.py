import logging
from datetime import timedelta
from typing import Callable, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from employees.models import Employee, SyncRun
from employees.repositories import EmployeeRepository, LdapServerRepository, SyncRunRepository
from ldapsync.client import LdapClient, LdapSyncError
from ldapsync.config import load_settings
from ldapsync.mapping import build_payload, to_generalized_time

logger = logging.getLogger("ldapsync")

SYNCED_FIELDS = (
    "sam_account_name", "user_principal_name", "distinguished_name",
    "display_name", "full_name", "last_name", "first_name", "middle_name",
    "email", "phone", "mobile_phone", "internal_phone", "search_phone",
    "department", "title", "company_name", "office", "city", "employee_id",
    "description", "manager_dn", "ad_enabled", "account_control",
    "when_created", "when_changed", "usn_changed",
)


class LdapSyncService:
    def __init__(self, employees=None, servers=None, runs=None):
        self.employees = employees or EmployeeRepository()
        self.servers = servers or LdapServerRepository()
        self.runs = runs or SyncRunRepository()

    def sync_all(self, mode: str = SyncRun.Mode.FULL, trigger: str = SyncRun.Trigger.CLI,
                 progress: Optional[Callable[[str], None]] = None) -> list:
        results = []
        for server in self.servers.enabled():
            results.append(self.run(mode=mode, ldap_server=server, trigger=trigger, progress=progress))
        return results

    def run(self, mode: str = SyncRun.Mode.FULL, ldap_server=None, changed_since=None,
            limit: Optional[int] = None, dry_run: bool = False, overrides: Optional[dict] = None,
            trigger: str = SyncRun.Trigger.CLI, task_id: str = "",
            progress: Optional[Callable[[str], None]] = None) -> SyncRun:
        say = progress or (lambda message: None)
        merged = dict(ldap_server.as_overrides()) if ldap_server else {}
        merged.update({k: v for k, v in (overrides or {}).items() if v is not None})
        config = load_settings(merged)

        if mode == SyncRun.Mode.INCREMENTAL and changed_since is None:
            watermark = self.runs.watermark(ldap_server)
            if watermark:
                overlap = timedelta(minutes=settings.LDAP_INCREMENTAL_OVERLAP_MINUTES)
                changed_since = watermark - overlap
            else:
                say("Водяного знака нет - выполняю полную синхронизацию.")
                mode = SyncRun.Mode.FULL

        run = self.runs.create(
            mode=mode,
            dry_run=dry_run,
            changed_since=changed_since,
            trigger=trigger,
            task_id=task_id,
            ldap_server=ldap_server,
            company=ldap_server.company if ldap_server else None,
        )
        company = ldap_server.company if ldap_server else None
        seen_guids = set()
        manager_dns = {}
        max_when_changed = None

        try:
            with LdapClient(config) as client:
                say(f"Подключение: {client.server_info()}")
                since = to_generalized_time(changed_since) if changed_since else None

                for entry in client.iter_users(changed_since=since, limit=limit):
                    payload = build_payload(entry, config.profile)
                    run.entries_read += 1
                    seen_guids.add(payload["object_guid"])

                    when_changed = payload.get("when_changed")
                    if when_changed and (max_when_changed is None or when_changed > max_when_changed):
                        max_when_changed = when_changed

                    if payload.get("manager_dn"):
                        manager_dns[payload["object_guid"]] = payload["manager_dn"]

                    if dry_run:
                        run.skipped += 1
                        say(f"[dry-run] {payload.get('full_name')} <{payload.get('email')}>")
                        continue

                    counter = self.upsert(payload, company=company, ldap_server=ldap_server)
                    setattr(run, counter, getattr(run, counter) + 1)

                    if run.entries_read % 500 == 0:
                        say(f"Обработано записей: {run.entries_read}")

            if not dry_run:
                self.link_managers(manager_dns)
                if mode == SyncRun.Mode.FULL and config.deactivate_missing:
                    run.deactivated = self.deactivate_missing(seen_guids, config, ldap_server, say)

            run.max_when_changed = max_when_changed
            run.status = SyncRun.Status.SUCCESS
        except LdapSyncError as exc:
            run.status = SyncRun.Status.FAILED
            run.error = str(exc)
            logger.exception("Синхронизация не удалась")
        except Exception as exc:
            run.status = SyncRun.Status.FAILED
            run.error = f"{type(exc).__name__}: {exc}"
            logger.exception("Синхронизация не удалась")
        finally:
            run.finished_at = timezone.now()
            run.save()
            if ldap_server is not None:
                ldap_server.last_sync_at = run.finished_at
                ldap_server.last_sync_status = run.status
                ldap_server.save(update_fields=["last_sync_at", "last_sync_status", "updated_at"])

        return run

    def upsert(self, payload: dict, company=None, ldap_server=None) -> str:
        guid = payload["object_guid"]
        now = timezone.now()

        with transaction.atomic():
            employee = Employee.objects.select_for_update().filter(object_guid=guid).first()

            if employee is None and payload.get("sam_account_name"):
                employee = (
                    Employee.objects.select_for_update()
                    .filter(sam_account_name__iexact=payload["sam_account_name"])
                    .first()
                )
                if employee is not None:
                    employee.object_guid = guid

            created = employee is None
            if created:
                employee = Employee(object_guid=guid, first_seen_at=now)

            locked = set(employee.locked_fields or [])
            values = {name: payload[name] for name in SYNCED_FIELDS if name in payload}
            changed = employee.set_fields(values, skip=locked)

            if company is not None and employee.company_id != company.id:
                employee.company = company
                changed.append("company")
            if ldap_server is not None and employee.ldap_server_id != ldap_server.id:
                employee.ldap_server = ldap_server
                changed.append("ldap_server")

            desired_active = bool(payload.get("ad_enabled", True))
            if employee.is_active != desired_active:
                employee.is_active = desired_active
                employee.deactivated_at = None if desired_active else now
                changed.append("is_active")

            employee.last_synced_at = now
            employee.save()

        if created:
            return "created"
        return "updated" if changed else "unchanged"

    def link_managers(self, manager_dns: dict) -> None:
        if not manager_dns:
            return
        by_dn = self.employees.map_dn_to_pk(manager_dns.values())
        for guid, manager_dn in manager_dns.items():
            manager_pk = by_dn.get((manager_dn or "").lower())
            if manager_pk:
                self.employees.set_manager(guid, manager_pk)

    def deactivate_missing(self, seen_guids: set, config, ldap_server, say: Callable[[str], None]) -> int:
        if len(seen_guids) < config.min_entries_for_deactivation:
            say(
                f"Получено {len(seen_guids)} записей - меньше порога "
                f"{config.min_entries_for_deactivation}, деактивацию пропускаю."
            )
            return 0
        count = self.employees.deactivate_missing(seen_guids, ldap_server=ldap_server)
        if count:
            say(f"Деактивировано пропавших из AD: {count}")
        return count
