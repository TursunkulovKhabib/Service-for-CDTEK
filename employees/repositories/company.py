from employees.models import Company

from .base import BaseRepository


class CompanyRepository(BaseRepository):
    model = Company

    def get_by_code(self, code: str):
        return self.get_queryset().filter(code=code).first()

    def default(self):
        return self.get_queryset().filter(is_default=True, is_active=True).first()

    def update_or_create(self, code: str, **fields):
        return Company.objects.update_or_create(code=code, defaults=fields)
