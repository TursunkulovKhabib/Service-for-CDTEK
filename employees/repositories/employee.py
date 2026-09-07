import re

from django.db.models import Case, Count, IntegerField, Q, Sum, Value, When
from django.utils import timezone

from employees.models import Employee

from .base import BaseRepository

SEARCH_FIELDS = ("full_name", "email", "phone_mobile", "phone_internal", "department", "title")


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

    def updated_since(self, moment):
        return self.published().filter(
            Q(when_changed__gte=moment) | Q(updated_at__gte=moment)
        ).order_by("full_name")

    def by_emails(self, emails, consent: bool = False):
        queryset = self.published().filter(email__in=[e.lower() for e in emails])
        if consent:
            queryset = queryset.with_consent()
        return queryset.order_by("full_name")

    def search(self, queryset=None, query: str = "", department: str = "", company: str = ""):
        queryset = self.published() if queryset is None else queryset
        query = (query or "").strip()
        if query:
            digits = re.sub(r"\D", "", query)
            condition = Q()
            for field in SEARCH_FIELDS:
                condition |= Q(**{f"{field}__icontains": query})
            condition |= Q(sam_account_name__icontains=query)
            if len(digits) >= 3:
                condition |= Q(search_phone__contains=digits)
            queryset = queryset.filter(condition)
        if department:
            queryset = queryset.filter(department__icontains=department)
        if company:
            queryset = queryset.filter(
                Q(company__code__iexact=company) | Q(company__org_id__iexact=company)
            )
        return queryset

    def search_by_phone(self, phone: str, queryset=None):
        queryset = self.published() if queryset is None else queryset
        digits = re.sub(r"\D", "", phone or "")
        if not digits:
            return queryset
        return queryset.filter(search_phone__contains=digits)

    def search_rank(self, words, org_ids=None, country_ids=None, work_statuses=None,
                    consent: bool = False, birthday: bool = False, dirty: bool = False,
                    sort_by_name: bool = False):
        """Ранжирующий поиск: считаем, скольким словам запроса отвечает запись.

        Порт SQL-запроса getUserListByQRank: вместо CROSS JOIN со словами и
        группировки - один проход с суммой попаданий.
        """
        words = [w.strip().lower() for w in words if w and w.strip()]
        queryset = self.published()

        if org_ids:
            queryset = queryset.filter(company__org_id__in=[o.lower() for o in org_ids])
        if country_ids:
            queryset = queryset.filter(company__country_id__in=[c.lower() for c in country_ids])
        if work_statuses:
            queryset = queryset.filter(zup_state__in=work_statuses)
        if consent:
            queryset = queryset.with_consent()
        if birthday:
            today = timezone.localdate()
            until = today + timezone.timedelta(days=10)
            if today.month == until.month:
                queryset = queryset.filter(
                    birthday__month=today.month,
                    birthday__day__gte=today.day,
                    birthday__day__lte=until.day,
                )
            else:
                queryset = queryset.filter(
                    Q(birthday__month=today.month, birthday__day__gte=today.day)
                    | Q(birthday__month=until.month, birthday__day__lte=until.day)
                )

        if not words:
            return queryset.annotate(hits=Value(0, output_field=IntegerField())).order_by("full_name")

        matched = Q()
        hits = None
        for word in words:
            word_condition = Q()
            for field in SEARCH_FIELDS:
                word_condition |= Q(**{f"{field}__icontains": word})
            matched |= word_condition
            expression = Case(
                When(word_condition, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
            hits = expression if hits is None else hits + expression

        queryset = queryset.filter(matched).annotate(hits=hits)
        if not dirty and len(words) > 1:
            queryset = queryset.filter(hits__gte=len(words) - 1)

        order = ("full_name", "-hits", "email") if sort_by_name else ("-hits", "full_name", "email")
        return queryset.order_by(*order)

    def departments(self, company: str = ""):
        queryset = self.published().exclude(department="")
        if company:
            queryset = queryset.filter(company__code__iexact=company)
        return (
            queryset.values("department")
            .annotate(employees=Count("id"))
            .order_by("department")
        )

    def organizations(self):
        return (
            self.published()
            .exclude(company=None)
            .values("company__org_id", "company__name")
            .distinct()
            .order_by("company__name")
        )

    def countries(self):
        return (
            self.published()
            .exclude(company=None)
            .values("company__country_id", "company__country_name")
            .distinct()
            .order_by("company__country_name")
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
