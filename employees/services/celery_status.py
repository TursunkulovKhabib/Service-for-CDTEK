import logging

from django.conf import settings

logger = logging.getLogger("ldapsync")


def broker_available() -> tuple:
    from serviceforcdtek.celery import app

    try:
        connection = app.connection()
        connection.ensure_connection(max_retries=0, timeout=2)
        connection.release()
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def dispatch(task, **kwargs) -> dict:
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return {"queued": False, "task_id": "", "error": "eager mode", "result": task(**kwargs)}

    available, error = broker_available()
    if not available:
        logger.warning("Celery недоступен, выполняю задачу синхронно: %s", error)
        return {"queued": False, "task_id": "", "error": error, "result": task(**kwargs)}

    async_result = task.delay(**kwargs)
    return {"queued": True, "task_id": async_result.id, "error": "", "result": None}


def worker_status() -> dict:
    from serviceforcdtek.celery import app

    available, error = broker_available()
    if not available:
        return {"broker": False, "error": error, "workers": []}

    try:
        pong = app.control.ping(timeout=2) or []
    except Exception as exc:
        return {"broker": True, "error": f"{type(exc).__name__}: {exc}", "workers": []}

    return {
        "broker": True,
        "error": "",
        "workers": [name for reply in pong for name in reply],
    }
