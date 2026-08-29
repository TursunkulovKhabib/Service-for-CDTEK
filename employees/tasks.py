import logging

from celery import shared_task

from employees.models import SyncRun
from employees.repositories import LdapServerRepository
from employees.services import CompanyService, LdapSyncService

logger = logging.getLogger("ldapsync")


def _result(run: SyncRun) -> dict:
    return {
        "id": run.id,
        "company": run.company.code if run.company else None,
        "mode": run.mode,
        "status": run.status,
        "entries_read": run.entries_read,
        "created": run.created,
        "updated": run.updated,
        "unchanged": run.unchanged,
        "deactivated": run.deactivated,
        "error": run.error,
    }


def run_sync_task(mode: str, ldap_server_id=None, trigger: str = SyncRun.Trigger.CELERY,
                  dry_run: bool = False, task_id: str = "") -> list:
    service = LdapSyncService()
    servers = LdapServerRepository()

    if ldap_server_id:
        targets = [servers.get_by_pk(ldap_server_id)]
    else:
        targets = list(servers.enabled())

    runs = [
        service.run(mode=mode, ldap_server=server, dry_run=dry_run,
                    trigger=trigger, task_id=task_id, progress=logger.info)
        for server in targets
        if server is not None
    ]
    return [_result(run) for run in runs]


@shared_task(bind=True, name="employees.sync_employees")
def sync_employees(self, mode: str = SyncRun.Mode.FULL, ldap_server_id=None,
                   trigger: str = SyncRun.Trigger.CELERY, dry_run: bool = False) -> list:
    return run_sync_task(
        mode=mode,
        ldap_server_id=ldap_server_id,
        trigger=trigger,
        dry_run=dry_run,
        task_id=getattr(self.request, "id", "") or "",
    )


@shared_task(bind=True, name="employees.sync_employees_full")
def sync_employees_full(self, ldap_server_id=None) -> list:
    return run_sync_task(
        mode=SyncRun.Mode.FULL,
        ldap_server_id=ldap_server_id,
        task_id=getattr(self.request, "id", "") or "",
    )


@shared_task(bind=True, name="employees.sync_employees_incremental")
def sync_employees_incremental(self, ldap_server_id=None) -> list:
    return run_sync_task(
        mode=SyncRun.Mode.INCREMENTAL,
        ldap_server_id=ldap_server_id,
        task_id=getattr(self.request, "id", "") or "",
    )


@shared_task(name="employees.load_companies")
def load_companies() -> dict:
    return CompanyService().load_from_settings()
