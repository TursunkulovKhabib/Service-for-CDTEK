from django.conf import settings


class LegacyEmployeeDTO:
    def __init__(self, config: dict = None):
        self.config = config or settings.LEGACY_V1

    def _value(self, employee, source: str):
        value = getattr(employee, source, None)
        if callable(value):
            value = value()
        if value is None:
            return self.config.get("EMPTY_VALUE", "")
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if not isinstance(value, (str, int, float, bool)):
            value = str(value)
        if value == "":
            return self.config.get("EMPTY_VALUE", "")
        return value

    def to_dict(self, employee, detail: bool = False) -> dict:
        mapping = self.config["DETAIL_FIELDS"] if detail else self.config["FIELDS"]
        return {key: self._value(employee, source) for key, source in mapping.items()}

    def to_list(self, employees) -> list:
        return [self.to_dict(employee) for employee in employees]

    def envelope(self, payload):
        name = self.config.get("ENVELOPE")
        return {name: payload} if name else payload


class LegacyDepartmentDTO:
    def to_list(self, rows) -> list:
        return [
            {"department": row["department"], "count": row["employees"]}
            for row in rows
        ]
