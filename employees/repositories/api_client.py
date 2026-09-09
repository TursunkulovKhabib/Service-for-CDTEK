from employees.models import ApiClient

from .base import BaseRepository


class ApiClientRepository(BaseRepository):
    model = ApiClient

    def get_by_login(self, login: str):
        return self.active().filter(login=login).first()

    def update_or_create(self, login: str, **fields):
        return ApiClient.objects.update_or_create(login=login, defaults=fields)
