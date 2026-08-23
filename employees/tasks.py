import logging

from celery import shared_task

from .models import SyncRun

logger = logging.getLogger("ldapsync")


@shared_task(name="employees.sync_employees")
def sync_employees(mode: str = SyncRun.Mode.FULL, limit: int = None, dry_run: bool = False) -> dict:
    from ldapsync.sync import run_sync

    run = run_sync(mode=mode, limit=limit, dry_run=dry_run, progress=logger.info)
    return {
        "id": run.id,
        "mode": run.mode,
        "status": run.status,
        "entries_read": run.entries_read,
        "created": run.created,
        "updated": run.updated,
        "unchanged": run.unchanged,
        "deactivated": run.deactivated,
        "error": run.error,
    }


@shared_task(name="employees.sync_employees_incremental")
def sync_employees_incremental() -> dict:
    return sync_employees(mode=SyncRun.Mode.INCREMENTAL)


@shared_task(name="employees.sync_employees_full")
def sync_employees_full() -> dict:
    return sync_employees(mode=SyncRun.Mode.FULL)
