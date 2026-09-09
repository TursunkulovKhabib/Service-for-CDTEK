import base64
import unittest
import uuid
from datetime import date

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from employees.models import ApiClient, Employee
from employees.services import ApiClientService
from employees.tests.factories import make_company

CYRILLIC_SEARCH = unittest.skipIf(
    connection.vendor == "sqlite",
    "SQLite ищет по кириллице с учётом регистра - нужен PostgreSQL",
)

CLIENTS = {
    "rootUser2021": {
        "password": "secret",
        "permissions": {
            "getuserlist", "searchuserlist", "getuserlistbyemailarray", "searchuserlistrank",
            "getcountries", "getorganizations", "getboss", "getdepartments",
            "1", "2", "3", "4", "5", "6", "7", "8",
        },
    },
    "mailer2021": {"password": "mail-secret", "permissions": {"getuserlist", "1"}},
}


def basic(login: str, password: str) -> dict:
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    return {"authorization": f"Basic {token}"}


class ApiFixtureMixin:
    @classmethod
    def create_fixtures(cls):
        cls.cdtek = make_company(code="cdtek", name="ЦЦ ТЭК", org_id="cdtek.ru")
        cls.engs = make_company(code="engs", name="ЭНГС", org_id="engsdrilling.ru")
        cls.ivanov = Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="ivanov", userid="ivanov@root.cdtek.ru",
            full_name="Иванов Иван Иванович", display_name="Иванов Иван Иванович",
            last_name="Иванов", first_name="Иван", middle_name="Иванович",
            department="Отдел разработки", title="Инженер", email="ivanov@cdtek.ru",
            phone_mobile="+7 916 000-11-22", phone_mobile_work="+7 (495) 123-45-67",
            phone_internal="1234", search_phone="79160001122 74951234567 1234",
            birthday=date(1990, 5, 17), personal_data_consent=True,
            zup_uid="zup-0001", zup_state="Отпуск", company=cls.cdtek,
            when_changed=timezone.now(),
        )
        cls.sokolov = Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="sokolov", full_name="Соколов Олег",
            last_name="Соколов", first_name="Олег", department="Логистика", title="Логист",
            email="sokolov@engsdrilling.ru", search_phone="78432001002", company=cls.engs,
            when_changed=timezone.now(),
        )
        Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="uvolen", full_name="Уволенный Сотрудник",
            email="uvolen@cdtek.ru", department="Отдел разработки",
            company=cls.cdtek, is_active=False,
        )
        cls.service_account = Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="sr_toir", full_name="SR Toir",
            company=cls.cdtek,
        )


@override_settings(LEGACY_V1_REQUIRE_BASIC_AUTH=False)
class LegacyContractTests(ApiFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_fixtures()

    def call(self, act: str, params: dict = None):
        query = {"act": act}
        query.update(params or {})
        return self.client.get(reverse("v1:userservice"), query).json()

    def test_envelope_matches_old_service(self):
        payload = self.call("getuserlist", {"dtfrom": "01.01.2020"})
        self.assertEqual(payload["code"], "ok")
        self.assertIn("users selected", payload["message"])
        self.assertIsInstance(payload["object"], list)

    def test_getuserlist_returns_base_fields(self):
        row = self.call("getuserlist", {"dtfrom": "01.01.2020"})["object"][0]
        self.assertEqual(
            set(row.keys()),
            {"full_name", "first_name", "surename", "patronymic", "email", "updated", "state", "photo"},
        )

    def test_getuserlist_fulldata_adds_department_and_phones(self):
        row = self.call("getuserlist", {"dtfrom": "01.01.2020", "fulldata": "true"})["object"][0]
        self.assertIn("department", row)
        self.assertIn("phone_mobile_work", row)
        self.assertEqual(row["phone_internal"], "1234")

    def test_getuserlist_requires_dtfrom(self):
        payload = self.call("getuserlist")
        self.assertEqual(payload["code"], "error")
        self.assertIn("dtfrom", payload["message"])

    def test_numeric_alias_works_like_name(self):
        by_name = self.call("getuserlist", {"dtfrom": "01.01.2020"})
        by_number = self.call("1", {"dtfrom": "01.01.2020"})
        self.assertEqual(by_name["object"], by_number["object"])

    def test_state_is_numeric(self):
        row = self.call("getuserlist", {"dtfrom": "01.01.2020"})["object"][0]
        self.assertEqual(row["state"], 1)

    @CYRILLIC_SEARCH
    def test_searchuserlist_paginates(self):
        payload = self.call("searchuserlist", {"q": "иванов", "limit": 1, "page": 1})
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["current_page"], 1)
        self.assertEqual(payload["pages"], 1)

    def test_searchuserlist_finds_by_phone_digits(self):
        payload = self.call("searchuserlist", {"q": "74951234567"})
        self.assertEqual(payload["count"], 1)

    def test_getuserlistbyemailarray(self):
        payload = self.call("getuserlistbyemailarray",
                            {"email": "ivanov@cdtek.ru,sokolov@engsdrilling.ru"})
        self.assertEqual(payload["count"], 2)

    def test_email_array_with_empty_flag_returns_extended_fields(self):
        row = self.call("getuserlistbyemailarray",
                        {"email": "ivanov@cdtek.ru", "empty": "1"})["object"][0]
        self.assertEqual(row["org_id"], "cdtek.ru")
        self.assertEqual(row["org_name"], "ЦЦ ТЭК")
        self.assertEqual(row["country_name"], "Россия")
        self.assertEqual(row["zup_uid"], "zup-0001")
        self.assertEqual(row["birthday"], "17.05")

    def test_email_array_can_filter_by_consent(self):
        payload = self.call("getuserlistbyemailarray",
                            {"email": "ivanov@cdtek.ru,sokolov@engsdrilling.ru",
                             "personal_data_consent": "1"})
        self.assertEqual(payload["count"], 1)

    @CYRILLIC_SEARCH
    def test_searchuserlistrank_ranks_by_word_hits(self):
        payload = self.call("searchuserlistrank", {"q": "иванов инженер"})
        self.assertEqual(payload["object"][0]["full_name"], "Иванов Иван Иванович")

    def test_searchuserlistrank_filters_by_orgid(self):
        payload = self.call("searchuserlistrank", {"q": "о", "orgid": "engsdrilling.ru"})
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["object"][0]["full_name"], "Соколов Олег")

    @CYRILLIC_SEARCH
    def test_searchuserlistrank_filters_by_work_status(self):
        payload = self.call("searchuserlistrank", {"q": "иванов", "work_status": "v"})
        self.assertEqual(payload["count"], 1)

    def test_getcountries(self):
        payload = self.call("getcountries")
        self.assertEqual(payload["object"], [{"code": "ru", "label": "Россия"}])

    def test_getorganizations(self):
        codes = {row["code"] for row in self.call("getorganizations")["object"]}
        self.assertEqual(codes, {"cdtek.ru", "engsdrilling.ru"})

    def test_unknown_action(self):
        payload = self.call("nosuchmethod")
        self.assertEqual(payload["code"], "error")
        self.assertEqual(payload["message"], "No action found!")

    def test_service_account_without_email_is_not_published(self):
        names = [row["full_name"] for row in self.call("getuserlist", {"dtfrom": "01.01.2020"})["object"]]
        self.assertNotIn("SR Toir", names)
        self.assertTrue(Employee.objects.filter(sam_account_name="sr_toir").exists())

    def test_inactive_employee_is_never_returned(self):
        names = [row["full_name"] for row in self.call("searchuserlist", {"q": "уволен"})["object"]]
        self.assertEqual(names, [])

    def test_dedicated_url_per_action(self):
        response = self.client.get(reverse("v1:getcountries"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], "ok")


@override_settings(LEGACY_V1_REQUIRE_BASIC_AUTH=True, LEGACY_V1_CLIENTS=CLIENTS)
class LegacyAccessControlTests(ApiFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_fixtures()

    def test_request_without_credentials_is_rejected(self):
        payload = self.client.get(reverse("v1:userservice"), {"act": "getuserlist"}).json()
        self.assertEqual(payload["message"], "Unauthorized")

    def test_wrong_password_is_rejected(self):
        payload = self.client.get(
            reverse("v1:userservice"), {"act": "getuserlist", "dtfrom": "01.01.2020"},
            headers=basic("rootUser2021", "wrong"),
        ).json()
        self.assertEqual(payload["message"], "Unauthorized")

    def test_client_without_permission_gets_forbidden(self):
        payload = self.client.get(
            reverse("v1:userservice"), {"act": "getorganizations"},
            headers=basic("mailer2021", "mail-secret"),
        ).json()
        self.assertEqual(payload["message"], "Forbidden")

    def test_client_with_permission_passes(self):
        payload = self.client.get(
            reverse("v1:userservice"), {"act": "getuserlist", "dtfrom": "01.01.2020"},
            headers=basic("mailer2021", "mail-secret"),
        ).json()
        self.assertEqual(payload["code"], "ok")


@override_settings(LEGACY_V1_REQUIRE_BASIC_AUTH=True, LEGACY_V1_CLIENTS=CLIENTS)
class ApiClientFromAdminTests(ApiFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_fixtures()
        cls.bot = ApiClient.objects.create(
            login="contacts-bot", description="Бот Контакты",
            permissions=["getuserlist", "getcountries"],
        )
        cls.bot.set_password("bot-secret", save=True)

    def call(self, act: str, login: str, password: str, **query):
        return self.client.get(
            reverse("v1:userservice"), {"act": act, **query}, headers=basic(login, password),
        ).json()

    def test_password_is_stored_only_as_hash(self):
        self.bot.refresh_from_db()
        self.assertNotIn("bot-secret", self.bot.password_hash)
        self.assertTrue(self.bot.check_password("bot-secret"))

    def test_client_from_database_passes(self):
        payload = self.call("getuserlist", "contacts-bot", "bot-secret", dtfrom="01.01.2020")
        self.assertEqual(payload["code"], "ok")

    def test_numeric_alias_uses_the_same_permission(self):
        payload = self.call("1", "contacts-bot", "bot-secret", dtfrom="01.01.2020")
        self.assertEqual(payload["code"], "ok")

    def test_method_outside_the_list_is_forbidden(self):
        self.assertEqual(
            self.call("getorganizations", "contacts-bot", "bot-secret")["message"], "Forbidden"
        )

    def test_wrong_password_is_rejected(self):
        self.assertEqual(
            self.call("getuserlist", "contacts-bot", "wrong")["message"], "Unauthorized"
        )

    def test_deactivated_client_loses_access(self):
        self.bot.deactivate()
        self.assertEqual(
            self.call("getuserlist", "contacts-bot", "bot-secret")["message"], "Unauthorized"
        )
        self.bot.activate()

    def test_clients_from_env_still_work(self):
        payload = self.call("getuserlist", "mailer2021", "mail-secret", dtfrom="01.01.2020")
        self.assertEqual(payload["code"], "ok")

    def test_import_moves_env_clients_into_database(self):
        stats = ApiClientService().import_from_settings()
        self.assertEqual(stats["created"], 2)
        imported = ApiClient.objects.get(login="mailer2021")
        self.assertTrue(imported.check_password("mail-secret"))
        self.assertEqual(imported.permissions, ["getuserlist"])

    def test_last_used_is_written_after_call(self):
        self.call("getcountries", "contacts-bot", "bot-secret")
        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.last_used_at)


@override_settings(API_V2_REQUIRE_JWT=False)
class ApiV2Tests(ApiFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_fixtures()

    def test_list_is_paginated(self):
        self.assertEqual(self.client.get(reverse("v2:employee-list")).json()["count"], 2)

    def test_list_item_field_set(self):
        row = self.client.get(reverse("v2:employee-list")).json()["results"][0]
        self.assertEqual(
            set(row.keys()),
            {"object_guid", "full_name", "title", "department", "phone_mobile", "company"},
        )

    def test_filter_by_company_code(self):
        payload = self.client.get(reverse("v2:employee-list"), {"company": "engs"}).json()
        self.assertEqual(payload["count"], 1)

    def test_detail_contains_contacts(self):
        url = reverse("v2:employee-detail", args=[str(self.ivanov.object_guid)])
        payload = self.client.get(url).json()
        self.assertEqual(payload["email"], "ivanov@cdtek.ru")
        self.assertEqual(payload["phone_internal"], "1234")

    def test_detail_hides_birth_year(self):
        url = reverse("v2:employee-detail", args=[str(self.ivanov.object_guid)])
        payload = self.client.get(url).json()
        self.assertEqual(payload["birthday"], "17.05")
        self.assertNotIn("1990", str(payload))

    def test_companies_endpoint(self):
        codes = {row["code"] for row in self.client.get(reverse("v2:company-list")).json()["results"]}
        self.assertEqual(codes, {"cdtek", "engs"})

    def test_health(self):
        self.assertEqual(self.client.get(reverse("v2:health")).json()["employees_active"], 2)


@override_settings(API_V2_REQUIRE_JWT=True)
class JwtTests(ApiFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_fixtures()
        User.objects.create_user("bot", password="secret")

    def test_request_without_token_is_rejected(self):
        self.assertEqual(self.client.get(reverse("v2:employee-list")).status_code, 401)

    def test_token_is_issued_and_accepted(self):
        access = self.client.post(
            reverse("v2:token-obtain"), {"username": "bot", "password": "secret"}
        ).json()["access"]
        response = self.client.get(
            reverse("v2:employee-list"), headers={"authorization": f"Bearer {access}"}
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(LEGACY_V1_REQUIRE_BASIC_AUTH=False)
    def test_v1_is_independent_from_jwt(self):
        payload = self.client.get(reverse("v1:userservice"), {"act": "getcountries"}).json()
        self.assertEqual(payload["code"], "ok")
