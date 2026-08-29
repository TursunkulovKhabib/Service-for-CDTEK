from datetime import datetime, timezone

from employees.models import Company, LdapServer


def ad_entry(**overrides):
    attrs = {
        "objectGUID": "{c9b1e2d4-1111-4222-8333-444455556666}",
        "sAMAccountName": "ivanov",
        "userPrincipalName": "ivanov@corp.local",
        "displayName": "Иванов Иван Иванович",
        "givenName": "Иван",
        "sn": "Иванов",
        "middleName": "Иванович",
        "mail": "ivanov@corp.local",
        "telephoneNumber": "+7 (495) 123-45-67",
        "mobile": "+7 916 000-11-22",
        "ipPhone": "1234",
        "department": "Отдел разработки",
        "title": "Инженер",
        "company": "ЦЦ ТЭК",
        "userAccountControl": 512,
        "whenChanged": datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        "uSNChanged": 100500,
    }
    attrs.update(overrides)
    dn = attrs.pop("dn", "CN=Ivanov,OU=Users,DC=corp,DC=local")
    return {"dn": dn, "attributes": attrs}


def make_company(code="cdtek", name="ЦЦ ТЭК", **kwargs):
    return Company.objects.create(code=code, name=name, **kwargs)


def make_server(company, name="AD тест", **kwargs):
    defaults = {
        "profile": "ad",
        "server_uri": "ldap://fake",
        "base_dn": "DC=corp,DC=local",
        "search_ous": [],
        "min_entries_for_deactivation": 1,
    }
    defaults.update(kwargs)
    return LdapServer.objects.create(company=company, name=name, **defaults)


class FakeClient:
    entries_by_uri = {}
    entries = []

    def __init__(self, config):
        self.config = config

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def server_info(self):
        return {"сервер": self.config.host, "порт": self.config.effective_port}

    def iter_users(self, changed_since=None, limit=None):
        entries = self.entries_by_uri.get(self.config.server_uri, self.entries)
        yield from entries[:limit] if limit else entries
