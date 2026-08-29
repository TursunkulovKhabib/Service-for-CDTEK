from employees.models import LdapServer

from .base import BaseRepository


class LdapServerRepository(BaseRepository):
    model = LdapServer

    def get_queryset(self):
        return LdapServer.objects.select_related("company")

    def get_by_name(self, name: str):
        return self.get_queryset().filter(name=name).first()

    def for_company(self, code: str):
        return self.active().filter(company__code=code)

    def enabled(self):
        return self.active().filter(company__is_active=True)

    def update_or_create(self, name: str, **fields):
        return LdapServer.objects.update_or_create(name=name, defaults=fields)
