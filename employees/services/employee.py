from employees.repositories import EmployeeRepository

from .base import BaseService


class EmployeeService(BaseService):
    repository_class = EmployeeRepository

    def published(self):
        return self.repository.published()

    def get_by_guid(self, object_guid):
        return self.repository.get_by_guid(object_guid)

    def get_by_login(self, login: str):
        return self.repository.get_by_login(login)

    def search(self, query: str = "", department: str = "", company: str = "",
               phone: str = "", include_inactive: bool = False, limit: int = None):
        queryset = self.repository.all() if include_inactive else self.repository.published()
        queryset = self.repository.search(
            queryset=queryset, query=query, department=department, company=company
        )
        if phone:
            queryset = self.repository.search_by_phone(phone, queryset=queryset)
        queryset = queryset.order_by("full_name")
        return queryset[:limit] if limit else queryset

    def departments(self, company: str = ""):
        return list(self.repository.departments(company))

    def hide(self, employee):
        return self.repository.update(employee, is_hidden=True)

    def unhide(self, employee):
        return self.repository.update(employee, is_hidden=False)

    def lock_fields(self, employee, fields):
        locked = sorted(set(employee.locked_fields or []) | set(fields))
        return self.repository.update(employee, locked_fields=locked)
