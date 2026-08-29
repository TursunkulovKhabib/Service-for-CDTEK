import re

from django.db.models import Count, Q
from django.utils import timezone

from employees.models import Employee

from .base import BaseRepository


class EmployeeRepository(BaseRepository):
    model = Employee

    def get_queryset(self):
        return Employee.objects.select_related("manager", "company")

    def published(self):
        return self.get_queryset().published()

    def get_by_guid(self, object_guid):
        return self.get_queryset().filter(object_guid=object_guid).first()

    def get_by_login(self, login: str):
        return self.get_queryset().filter(sam_account_name__iexact=login).first()

    def for_company(self, code: str):
        return self.published().for_company(code)

    def search(self, queryset=None, query: str = "", department: str = "", company: str = ""):
        queryset = self.published() if queryset is None else queryset
        query = (query or "").strip()
        if query:
            digits = re.sub(r"\D", "", query)
            condition = (
                Q(full_name__icontains=query)
                | Q(display_name__icontains=query)
                | Q(sam_account_name__icontains=query)
                | Q(email__icontains=query)
                | Q(department__icontains=query)
                | Q(title__icontains=query)
            )
            if len(digits) >= 3:
                condition |= Q(search_phone__contains=digits)
            queryset = queryset.filter(condition)
        if department:
            queryset = queryset.filter(department__icontains=department)
        if company:
            queryset = queryset.filter(
                Q(company__code__iexact=company) | Q(company__name__icontains=company)
            )
        return queryset

    def search_by_phone(self, phone: str, queryset=None):
        queryset = self.published() if queryset is None else queryset
        digits = re.sub(r"\D", "", phone or "")
        if not digits:
            return queryset
        return queryset.filter(search_phone__contains=digits)

    def departments(self, company: str = ""):
        queryset = self.published().exclude(department="")
        if company:
            queryset = queryset.filter(company__code__iexact=company)
        return (
            queryset.values("department")
            .annotate(employees=Count("id"))
            .order_by("department")
        )

    def deactivate_missing(self, seen_guids, ldap_server=None) -> int:
        queryset = self.model.objects.filter(is_active=True)
        if ldap_server is not None:
            queryset = queryset.filter(ldap_server=ldap_server)
        stale = queryset.exclude(object_guid__in=seen_guids)
        count = stale.count()
        if count:
            stale.update(is_active=False, deactivated_at=timezone.now())
        return count

    def map_dn_to_pk(self, dns) -> dict:
        rows = self.model.objects.filter(distinguished_name__in=set(dns)).values_list(
            "distinguished_name", "pk"
        )
        return {dn.lower(): pk for dn, pk in rows}

    def set_manager(self, object_guid, manager_pk) -> None:
        self.model.objects.filter(object_guid=object_guid).exclude(pk=manager_pk).update(
            manager_id=manager_pk
        )
