import base64

from django.conf import settings

from employees.models import SettingsApiClient, canonical_action
from employees.repositories import ApiClientRepository

from .base import BaseService


class ApiClientService(BaseService):
    """Проверка логина и пароля клиентов старого API.

    Сначала ищем в базе - это то, что заводится в админке. Если логина там нет,
    смотрим список из переменной окружения: он остаётся на время переезда.
    """

    repository_class = ApiClientRepository

    def authenticate(self, login: str, password: str):
        if not login:
            return None

        client = self.repository.get_by_login(login)
        if client is not None:
            return client if client.check_password(password) else None

        fallback = self.from_settings(login)
        if fallback is not None and fallback.check_password(password):
            return fallback
        return None

    def authorize(self, header: str, action: str):
        """Возвращает клиента, если заголовок верный и метод ему разрешён."""
        login, password = decode_basic(header)
        client = self.authenticate(login, password)
        if client is None:
            return None, "Unauthorized"
        if action and not client.allows(action):
            return None, "Forbidden"
        client.touch()
        return client, ""

    @staticmethod
    def from_settings(login: str):
        item = getattr(settings, "LEGACY_V1_CLIENTS", {}).get(login)
        if item is None:
            return None
        return SettingsApiClient(login, item["password"], item["permissions"])

    def import_from_settings(self) -> dict:
        """Переносит логины из переменной окружения в базу - по одному разу."""
        stats = {"created": 0, "skipped": 0}
        for login, item in getattr(settings, "LEGACY_V1_CLIENTS", {}).items():
            if self.repository.exists(login=login):
                stats["skipped"] += 1
                continue
            client = self.repository.create(
                login=login,
                description="Перенесён из переменной LEGACY_V1_CLIENTS",
                permissions=sorted({canonical_action(name) for name in item["permissions"]}),
            )
            client.set_password(item["password"], save=True)
            stats["created"] += 1
        return stats


def decode_basic(header: str) -> tuple:
    if not header.lower().startswith("basic "):
        return "", ""
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
    except Exception:
        return "", ""
    login, _, password = decoded.partition(":")
    return login, password
