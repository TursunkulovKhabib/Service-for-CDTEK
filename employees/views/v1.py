import math

from django.conf import settings
from django.utils.dateparse import parse_date
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.dto import LegacyEmployeeDTO, LegacyRefDataDTO, LegacyResponse
from employees.services import ApiClientService, EmployeeService


class Params:
    """Разбор query-параметров одним местом вместо try/catch на каждый параметр."""

    def __init__(self, request):
        self.data = request.query_params

    def text(self, name: str, default: str = "") -> str:
        return (self.data.get(name) or default).strip()

    def flag(self, name: str, default: bool = False) -> bool:
        raw = self.data.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def number(self, name: str, default: int, minimum: int = None) -> int:
        try:
            value = int(self.data.get(name))
        except (TypeError, ValueError):
            return default
        if minimum is not None and value < minimum:
            return minimum
        return value

    def csv(self, name: str) -> list:
        return [item.strip() for item in self.text(name).split(",") if item.strip()]

    def date(self, name: str):
        raw = self.text(name)
        if not raw:
            return None
        for pattern in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                from datetime import datetime

                return datetime.strptime(raw, pattern).date()
            except ValueError:
                continue
        return parse_date(raw)


class LegacyError(Exception):
    pass


def paginate(queryset, limit: int, page: int):
    total = queryset.count()
    pages = math.ceil(total / limit) if limit else 0
    start = max(page - 1, 0) * limit
    return queryset[start:start + limit], total, pages


class LegacyApiView(APIView):
    """Контроллер старого API. Действия разложены в словарь, а не в switch."""

    # Клиенты старого API - это не пользователи системы, а записи из админки,
    # поэтому заголовок разбираем сами и не отдаём его аутентификации DRF.
    authentication_classes = []
    permission_classes = [AllowAny]
    action = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = EmployeeService()
        self.clients = ApiClientService()
        self.dto = LegacyEmployeeDTO()

    @property
    def actions(self) -> dict:
        return {
            "1": self.get_user_list,
            "getuserlist": self.get_user_list,
            "2": self.get_boss,
            "getboss": self.get_boss,
            "3": self.get_departments,
            "getdepartments": self.get_departments,
            "4": self.search_user_list,
            "searchuserlist": self.search_user_list,
            "5": self.get_user_list_by_email_array,
            "getuserlistbyemailarray": self.get_user_list_by_email_array,
            "6": self.search_user_list_rank,
            "searchuserlistrank": self.search_user_list_rank,
            "7": self.get_countries,
            "getcountries": self.get_countries,
            "8": self.get_organizations,
            "getorganizations": self.get_organizations,
        }

    def get(self, request):
        act = (self.action or request.query_params.get("act") or "").strip().lower()
        try:
            self.authorize(request, act)
            handler = self.actions.get(act)
            if handler is None:
                raise LegacyError("No action found!")
            payload = handler(Params(request))
        except LegacyError as exc:
            return Response(LegacyResponse.error(str(exc)))
        except Exception as exc:
            return Response(LegacyResponse.error(f"{type(exc).__name__}: {exc}"))
        return Response(payload)

    def post(self, request):
        return self.get(request)

    def authorize(self, request, act: str) -> None:
        if not getattr(settings, "LEGACY_V1_REQUIRE_BASIC_AUTH", True):
            return
        client, error = self.clients.authorize(request.META.get("HTTP_AUTHORIZATION", ""), act)
        if client is None:
            raise LegacyError(error)

    # ------------------------------------------------------------------ 1
    def get_user_list(self, params: Params) -> dict:
        selected_from = params.date("dtfrom")
        if selected_from is None:
            raise LegacyError("Bad Request - Parameter dtfrom is empty!")
        full = params.flag("fulldata")

        employees = self.service.updated_since(selected_from)
        rows = self.dto.to_list(employees, full=full)
        return LegacyResponse.ok(f"There are {len(rows)} users selected.", rows)

    # ------------------------------------------------------------------ 2
    def get_boss(self, params: Params) -> dict:
        uid_zup = params.text("uid_zup")
        if not uid_zup:
            raise LegacyError("Bad Request - Parameter uid_zup is empty!")
        manager = self.service.get_manager_by_zup_uid(uid_zup)
        if manager is None:
            return LegacyResponse.ok("No boss found!", "")
        return LegacyResponse.ok(f"{uid_zup} => {manager.zup_uid}", manager.zup_uid)

    # ------------------------------------------------------------------ 3
    def get_departments(self, params: Params) -> dict:
        rows = self.service.departments(company=params.text("company"))
        return LegacyResponse.ok(f"There are {len(rows)} departments selected.", rows)

    # ------------------------------------------------------------------ 4
    def search_user_list(self, params: Params) -> dict:
        config = settings.LEGACY_V1
        limit = params.number("limit", config["DEFAULT_LIMIT"], minimum=1)
        page = params.number("page", 1, minimum=1)
        min_digit = params.number("min_digit", config["DEFAULT_MIN_DIGIT"])
        full = params.flag("empty")
        query = params.text("q")

        if len(query) < min_digit and not params.flag("default_search", True):
            return LegacyResponse.ok("There are 0 users selected.", [],
                                     current_page=page, pages=0, count=0)

        queryset = self.service.search(query=query)
        rows, total, pages = paginate(queryset, limit, page)
        return LegacyResponse.ok(
            f"There are {len(rows)} users selected.",
            self.dto.to_list(rows, full=full),
            current_page=page, pages=pages, count=total,
        )

    # ------------------------------------------------------------------ 5
    def get_user_list_by_email_array(self, params: Params) -> dict:
        config = settings.LEGACY_V1
        limit = params.number("limit", config["DEFAULT_LIMIT"], minimum=1)
        page = params.number("page", 1, minimum=1)
        emails = params.csv("email")
        consent = params.flag("personal_data_consent")
        full = params.flag("empty")
        photo_big = params.flag("bigphoto")

        if not emails:
            return LegacyResponse.ok("There are 0 users selected.", [],
                                     current_page=page, pages=0, count=0)

        queryset = self.service.by_emails(emails, consent=consent)
        rows, total, pages = paginate(queryset, limit, page)
        return LegacyResponse.ok(
            f"There are {len(rows)} users selected.",
            self.dto.to_list(rows, full=full, extended=True, photo_big=photo_big, consent=True),
            current_page=page, pages=pages, count=total,
        )

    # ------------------------------------------------------------------ 6
    def search_user_list_rank(self, params: Params) -> dict:
        config = settings.LEGACY_V1
        limit = params.number("limit", config["DEFAULT_LIMIT"], minimum=1)
        page = params.number("page", 1, minimum=1)
        min_digit = params.number("min_digit", config["DEFAULT_MIN_DIGIT"])
        query = params.text("q")
        full = params.flag("empty")
        photo_big = params.flag("bigphoto")

        words = query.split()
        dirty = params.flag("dirty_search")
        sort_by_name = False
        if len(query) < min_digit:
            if not params.flag("default_search", True):
                return LegacyResponse.ok("There are 0 users selected.", [],
                                         current_page=page, pages=0, count=0)
            words, dirty, sort_by_name = [], True, True

        org_ids = params.csv("orgid") or ([params.text("defaultorgid")]
                                          if params.text("defaultorgid") else [])
        statuses = [settings.LEGACY_WORK_STATUSES[key]
                    for key in params.csv("work_status")
                    if key in settings.LEGACY_WORK_STATUSES]

        queryset = self.service.search_rank(
            words=words,
            org_ids=org_ids,
            country_ids=params.csv("countryid"),
            work_statuses=statuses,
            consent=params.flag("personal_data_consent"),
            birthday=params.flag("birthday"),
            dirty=dirty,
            sort_by_name=sort_by_name,
        )
        rows, total, pages = paginate(queryset, limit, page)
        return LegacyResponse.ok(
            f"There are {len(rows)} users selected.",
            self.dto.to_list(rows, full=full, extended=True, photo_big=photo_big, consent=True),
            current_page=page, pages=pages, count=total,
        )

    # ------------------------------------------------------------------ 7
    def get_countries(self, params: Params) -> dict:
        rows = LegacyRefDataDTO().to_list(
            self.service.countries(), "company__country_id", "company__country_name"
        )
        return LegacyResponse.ok(f"There are {len(rows)} countries selected.", rows)

    # ------------------------------------------------------------------ 8
    def get_organizations(self, params: Params) -> dict:
        rows = LegacyRefDataDTO().to_list(
            self.service.organizations(), "company__org_id", "company__name"
        )
        return LegacyResponse.ok(f"There are {len(rows)} organizations selected.", rows)


def action_view(name: str):
    """Отдельный URL под каждое действие: /api/v1/getuserlist/ и т.д."""
    return type(f"Legacy{name.title()}View", (LegacyApiView,), {"action": name}).as_view()
