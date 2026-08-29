import uuid

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from employees.models import Employee
from employees.tests.factories import make_company


class ApiFixtureMixin:
    @classmethod
    def create_fixtures(cls):
        cls.cdtek = make_company(code="cdtek", name="ЦЦ ТЭК")
        cls.engs = make_company(code="engs", name="ЭНГС")
        cls.ivanov = Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="ivanov", full_name="Иванов Иван Иванович",
            display_name="Иванов Иван", department="Отдел разработки", title="Инженер",
            email="ivanov@corp.local", phone="+7 (495) 123-45-67",
            search_phone="74951234567 1234", company=cls.cdtek,
        )
        Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="sokolov", full_name="Соколов Олег",
            department="Логистика", title="Логист", search_phone="74957654321", company=cls.engs,
        )
        Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="uvolen", full_name="Уволенный Сотрудник",
            department="Отдел разработки", company=cls.cdtek, is_active=False,
        )


@override_settings(LEGACY_V1_REQUIRE_BASIC_AUTH=False)
class LegacyApiV1Tests(ApiFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_fixtures()

    def test_list_returns_flat_array_without_pagination(self):
        response = self.client.get(reverse("v1:employee-list"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload, list)
        self.assertEqual(len(payload), 2)

    def test_list_item_has_only_legacy_fields(self):
        response = self.client.get(reverse("v1:employee-list"))
        self.assertEqual(
            set(response.json()[0].keys()), {"fio", "position", "department", "phone"}
        )

    def test_inactive_employee_is_hidden(self):
        logins = [row["fio"] for row in self.client.get(reverse("v1:employee-list")).json()]
        self.assertNotIn("Уволенный Сотрудник", logins)

    def test_search_by_query_param(self):
        response = self.client.get(reverse("v1:employee-list"), {"query": "иванов"})
        self.assertEqual(len(response.json()), 1)

    def test_filter_by_company(self):
        response = self.client.get(reverse("v1:employee-list"), {"company": "engs"})
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["fio"], "Соколов Олег")

    def test_detail_by_login(self):
        response = self.client.get(reverse("v1:employee-detail", args=["ivanov"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["login"], "ivanov")
        self.assertEqual(response.json()["email"], "ivanov@corp.local")

    def test_detail_unknown_login_returns_404(self):
        response = self.client.get(reverse("v1:employee-detail", args=["nobody"]))
        self.assertEqual(response.status_code, 404)

    def test_departments(self):
        rows = self.client.get(reverse("v1:department-list")).json()
        self.assertEqual(rows, [
            {"department": "Логистика", "count": 1},
            {"department": "Отдел разработки", "count": 1},
        ])

    @override_settings(LEGACY_V1={
        "FIELDS": {"name": "full_name", "tel": "phone"},
        "DETAIL_FIELDS": {"name": "full_name"},
        "LOOKUP_FIELD": "sam_account_name",
        "ENVELOPE": "employees",
        "EMPTY_VALUE": None,
        "PAGINATED": False,
        "SEARCH_PARAM": "q",
        "DEPARTMENT_PARAM": "dept",
        "COMPANY_PARAM": "org",
        "LIMIT_PARAM": "count",
        "DEFAULT_LIMIT": 10,
    })
    def test_response_shape_is_configurable(self):
        payload = self.client.get(reverse("v1:employee-list")).json()
        self.assertIn("employees", payload)
        self.assertEqual(set(payload["employees"][0].keys()), {"name", "tel"})


@override_settings(LEGACY_V1_REQUIRE_BASIC_AUTH=True)
class LegacyBasicAuthTests(ApiFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_fixtures()
        User.objects.create_user("bot", password="secret")

    def test_request_without_credentials_is_rejected(self):
        response = self.client.get(reverse("v1:employee-list"))
        self.assertEqual(response.status_code, 401)
        self.assertIn("Basic", response.headers.get("WWW-Authenticate", ""))

    def test_basic_auth_is_accepted(self):
        import base64

        token = base64.b64encode(b"bot:secret").decode()
        response = self.client.get(
            reverse("v1:employee-list"), headers={"authorization": f"Basic {token}"}
        )
        self.assertEqual(response.status_code, 200)


@override_settings(API_V2_REQUIRE_JWT=False)
class ApiV2Tests(ApiFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_fixtures()

    def test_list_is_paginated(self):
        payload = self.client.get(reverse("v2:employee-list")).json()
        self.assertEqual(payload["count"], 2)

    def test_list_item_has_compact_field_set(self):
        row = self.client.get(reverse("v2:employee-list")).json()["results"][0]
        self.assertEqual(
            set(row.keys()), {"object_guid", "full_name", "title", "department", "phone", "company"}
        )

    def test_search_by_phone(self):
        payload = self.client.get(reverse("v2:employee-list"), {"phone": "+7 (495) 123-45-67"}).json()
        self.assertEqual(payload["count"], 1)

    def test_filter_by_company_code(self):
        payload = self.client.get(reverse("v2:employee-list"), {"company": "engs"}).json()
        self.assertEqual(payload["count"], 1)

    def test_detail_contains_manager_and_email(self):
        url = reverse("v2:employee-detail", args=[str(self.ivanov.object_guid)])
        payload = self.client.get(url).json()
        self.assertEqual(payload["email"], "ivanov@corp.local")
        self.assertIn("manager", payload)

    def test_companies_endpoint(self):
        payload = self.client.get(reverse("v2:company-list")).json()
        codes = {row["code"] for row in payload["results"]}
        self.assertEqual(codes, {"cdtek", "engs"})

    def test_health(self):
        payload = self.client.get(reverse("v2:health")).json()
        self.assertEqual(payload["employees_active"], 2)


@override_settings(API_V2_REQUIRE_JWT=True)
class JwtTests(ApiFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_fixtures()
        User.objects.create_user("bot", password="secret")

    def test_request_without_token_is_rejected(self):
        self.assertEqual(self.client.get(reverse("v2:employee-list")).status_code, 401)

    def test_token_is_issued_and_accepted(self):
        token_response = self.client.post(
            reverse("v2:token-obtain"), {"username": "bot", "password": "secret"}
        )
        self.assertEqual(token_response.status_code, 200)
        access = token_response.json()["access"]

        response = self.client.get(
            reverse("v2:employee-list"), headers={"authorization": f"Bearer {access}"}
        )
        self.assertEqual(response.status_code, 200)

    def test_refresh_token_works(self):
        refresh = self.client.post(
            reverse("v2:token-obtain"), {"username": "bot", "password": "secret"}
        ).json()["refresh"]
        response = self.client.post(reverse("v2:token-refresh"), {"refresh": refresh})
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())

    def test_v1_stays_open_while_v2_requires_token(self):
        with override_settings(LEGACY_V1_REQUIRE_BASIC_AUTH=False):
            self.assertEqual(self.client.get(reverse("v1:employee-list")).status_code, 200)
