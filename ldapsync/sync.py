from __future__ import annotations

import logging
from datetime import timedelta
from typing import Callable, Optional

from django.db import transaction
from django.utils import timezone

from employees.models import Employee, SyncRun

from .client import LdapClient, LdapSyncError
from .config import load_settings
from .mapping import build_payload, to_generalized_time

logger = logging.getLogger("ldapsync")

SYNCED_FIELDS = (
    "sam_account_name", "user_principal_name", "distinguished_name",
    "display_name", "full_name", "last_name", "first_name", "middle_name",
    "email", "phone", "mobile_phone", "internal_phone", "search_phone",
    "department", "title", "company", "office", "city", "employee_id",
    "description", "manager_dn", "ad_enabled", "account_control",
    "when_created", "when_changed", "usn_changed",
)

INCREMENTAL_OVERLAP = timedelta(minutes=10)


def _last_successful_watermark() -> Optional[timezone.datetime]:
    run = (
        SyncRun.objects.filter(status=SyncRun.Status.SUCCESS, dry_run=False)
        .exclude(max_when_changed=None)
        .order_by("-max_when_changed")
        .first()
    )
    return run.max_when_changed if run else None


def run_sync(
    mode: str = SyncRun.Mode.FULL,
    changed_since=None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    overrides: Optional[dict] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> SyncRun:
    settings_obj = load_settings(overrides)
    say = progress or (lambda message: None)

    if mode == SyncRun.Mode.INCREMENTAL and changed_since is None:
        watermark = _last_successful_watermark()
        if watermark:
            changed_since = watermark - INCREMENTAL_OVERLAP
        else:
            say("Водяного знака нет - выполняю полную синхронизацию.")
            mode = SyncRun.Mode.FULL

    run = SyncRun.objects.create(mode=mode, dry_run=dry_run, changed_since=changed_since)
    seen_guids: set = set()
    manager_dns: dict = {}
    max_when_changed = None

    try:
        with LdapClient(settings_obj) as client:
            say(f"Подключение: {client.server_info()}")
            since_str = to_generalized_time(changed_since) if changed_since else None

            for entry in client.iter_users(changed_since=since_str, limit=limit):
                payload = build_payload(entry, settings_obj.profile)
                run.entries_read += 1
                seen_guids.add(payload["object_guid"])

                if payload["when_changed"] and (
                    max_when_changed is None or payload["when_changed"] > max_when_changed
                ):
                    max_when_changed = payload["when_changed"]

                if payload.get("manager_dn"):
                    manager_dns[payload["object_guid"]] = payload["manager_dn"]

                if dry_run:
                    run.skipped += 1
                    say(f"[dry-run] {payload.get('full_name')} <{payload.get('email')}>")
                    continue

                result = _upsert(payload)
                setattr(run, result, getattr(run, result) + 1)

                if run.entries_read % 500 == 0:
                    say(f"Обработано записей: {run.entries_read}")

        if not dry_run:
            _link_managers(manager_dns)
            if mode == SyncRun.Mode.FULL and settings_obj.deactivate_missing:
                run.deactivated = _deactivate_missing(seen_guids, settings_obj, say)

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

    return run


def _upsert(payload: dict) -> str:
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
        changed_fields = []
        for field in SYNCED_FIELDS:
            if field in locked or field not in payload:
                continue
            new_value = payload[field]
            if getattr(employee, field) != new_value:
                setattr(employee, field, new_value)
                changed_fields.append(field)

        desired_active = bool(payload.get("ad_enabled", True))
        if employee.is_active != desired_active:
            employee.is_active = desired_active
            employee.deactivated_at = None if desired_active else now
            changed_fields.append("is_active")

        employee.last_synced_at = now
        employee.save()

    if created:
        return "created"
    return "updated" if changed_fields else "unchanged"


def _link_managers(manager_dns: dict) -> None:
    if not manager_dns:
        return
    by_dn = {
        dn.lower(): pk
        for dn, pk in Employee.objects.filter(distinguished_name__in=set(manager_dns.values()))
        .values_list("distinguished_name", "pk")
    }
    for guid, manager_dn in manager_dns.items():
        manager_pk = by_dn.get((manager_dn or "").lower())
        if manager_pk:
            Employee.objects.filter(object_guid=guid).exclude(pk=manager_pk).update(manager_id=manager_pk)


def _deactivate_missing(seen_guids: set, settings_obj, say: Callable[[str], None]) -> int:
    if len(seen_guids) < settings_obj.min_entries_for_deactivation:
        say(
            f"Получено {len(seen_guids)} записей - меньше порога "
            f"{settings_obj.min_entries_for_deactivation}, деактивацию пропускаю."
        )
        return 0

    stale = Employee.objects.filter(is_active=True).exclude(object_guid__in=seen_guids)
    count = stale.count()
    if count:
        stale.update(is_active=False, deactivated_at=timezone.now())
        say(f"Деактивировано пропавших из AD: {count}")
    return count
