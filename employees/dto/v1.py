from django.conf import settings


class LegacyEmployeeDTO:
    """Собирает запись сотрудника в формате старого Java-сервиса.

    Набор полей задаётся в settings/legacy.py, поэтому контракт правится
    настройками, а не кодом.
    """

    def __init__(self, config: dict = None):
        self.config = config or settings.LEGACY_V1
        self.date_format = self.config.get("DATE_FORMAT", "%d.%m.%Y")

    def _value(self, employee, source: str):
        if source == "updated":
            value = employee.when_changed or employee.updated_at
            return value.strftime(self.date_format) if value else ""
        if source == "zup_state_dateto":
            value = employee.zup_state_dateto
            return value.strftime(self.date_format) if value else ""

        value = getattr(employee, source, None)
        if value is None:
            return ""
        if isinstance(value, bool):
            return 1 if value else 0
        if hasattr(value, "strftime"):
            return value.strftime(self.date_format)
        return value

    def to_dict(self, employee, full: bool = False, extended: bool = False,
                photo_big: bool = False, consent: bool = False) -> dict:
        mapping = dict(self.config["BASE_FIELDS"])
        if consent:
            mapping.update(self.config["CONSENT_FIELD"])
        if photo_big:
            mapping.update(self.config["BIG_PHOTO_FIELD"])
        if full:
            mapping.update(self.config["FULL_FIELDS"])
        if full and extended:
            mapping.update(self.config["EXTENDED_FIELDS"])
        return {key: self._value(employee, source) for key, source in mapping.items()}

    def to_list(self, employees, **kwargs) -> list:
        return [self.to_dict(employee, **kwargs) for employee in employees]


class LegacyResponse:
    """Конверт ответа старого сервиса: code / message / object (+ пагинация)."""

    @staticmethod
    def ok(message: str, obj, **extra) -> dict:
        payload = {"code": "ok", "message": message, "object": obj}
        payload.update(extra)
        return payload

    @staticmethod
    def error(message: str) -> dict:
        return {"code": "error", "message": message, "object": None}


class LegacyRefDataDTO:
    def to_list(self, rows, code_field: str, label_field: str) -> list:
        return [{"code": row[code_field], "label": row[label_field]} for row in rows]
