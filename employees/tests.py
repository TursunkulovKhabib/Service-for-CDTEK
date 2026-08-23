import uuid
from datetime import datetime, timezone
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from employees.models import Employee, SyncRun
from ldapsync.config import get_profile, load_settings
from ldapsync.mapping import build_payload, digits_only, guid_to_uuid, parse_ldap_datetime

AD = get_profile("ad")


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
        "company": "ЦДТ",
        "userAccountControl": 512,
        "whenChanged": datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        "uSNChanged": 100500,
    }
    attrs.update(overrides)
    return {"dn": "CN=Ivanov,OU=Users,DC=corp,DC=local", "attributes": attrs}


class MappingTests(TestCase):
    def test_guid_from_ad_bytes_is_mixed_endian(self):
        raw = uuid.UUID("c9b1e2d4-1111-4222-8333-444455556666").bytes_le
        self.assertEqual(str(guid_to_uuid(raw, "dn")), "c9b1e2d4-1111-4222-8333-444455556666")

    def test_guid_falls_back_to_uuid5_of_dn(self):
        first = guid_to_uuid(None, "CN=x,DC=corp,DC=local")
        second = guid_to_uuid(None, "cn=X,dc=corp,dc=local")
        self.assertEqual(first, second, "GUID из DN должен быть стабильным и регистронезависимым")

    def test_payload_fills_names_phones_and_flags(self):
        payload = build_payload(ad_entry(), AD)
        self.assertEqual(payload["full_name"], "Иванов Иван Иванович")
        self.assertEqual(payload["department"], "Отдел разработки")
        self.assertTrue(payload["ad_enabled"])
        self.assertIn("74951234567", payload["search_phone"])
        self.assertIn("1234", payload["search_phone"])

    def test_disabled_account_detected_by_uac_bit(self):
        payload = build_payload(ad_entry(userAccountControl=514), AD)
        self.assertFalse(payload["ad_enabled"])

    def test_generalized_time_parsed(self):
        parsed = parse_ldap_datetime("20260801100000.0Z")
        self.assertEqual(parsed, datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc))

    def test_digits_only_strips_formatting(self):
        self.assertEqual(digits_only("+7 (495) 123-45-67", None, "1234"), "74951234567 1234")


class FilterTests(TestCase):
    @override_settings(LDAP={**{"PROFILE": "ad", "SERVER_URI": "ldaps://dc", "BASE_DN": "DC=corp,DC=local"}})
    def test_filter_excludes_disabled_accounts(self):
        settings_obj = load_settings()
        self.assertIn("userAccountControl:1.2.840.113556.1.4.803:=2", settings_obj.build_filter())

    @override_settings(
        LDAP={"PROFILE": "ad", "SERVER_URI": "ldaps://dc", "BASE_DN": "DC=corp,DC=local", "INCLUDE_DISABLED": True}
    )
    def test_incremental_filter_adds_when_changed(self):
        settings_obj = load_settings()
        built = settings_obj.build_filter("20260801100000.0Z")
        self.assertIn("(whenChanged>=20260801100000.0Z)", built)
        self.assertNotIn("1.2.840.113556.1.4.803", built)


class FakeClient:

    entries: list = []

    def __init__(self, settings_obj):
        self.settings = settings_obj

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def server_info(self):
        return {"host": "fake", "port": 389}

    def iter_users(self, changed_since=None, limit=None):
        yield from self.entries[:limit] if limit else self.entries


@override_settings(
    LDAP={
        "PROFILE": "ad",
        "SERVER_URI": "ldap://fake",
        "BASE_DN": "DC=corp,DC=local",
        "DEACTIVATE_MISSING": True,
        "MIN_ENTRIES_FOR_DEACTIVATION": 1,
    }
)
class SyncTests(TestCase):
    def run_sync_with(self, entries, **kwargs):
        from ldapsync import sync as sync_module

        FakeClient.entries = entries
        with mock.patch.object(sync_module, "LdapClient", FakeClient):
            return sync_module.run_sync(**kwargs)

    def test_full_sync_creates_then_updates_without_duplicates(self):
        run = self.run_sync_with([ad_entry()])
        self.assertEqual(run.status, SyncRun.Status.SUCCESS)
        self.assertEqual((run.created, run.updated), (1, 0))

        run = self.run_sync_with([ad_entry(title="Ведущий инженер")])
        self.assertEqual((run.created, run.updated), (0, 1))
        self.assertEqual(Employee.objects.count(), 1)
        self.assertEqual(Employee.objects.get().title, "Ведущий инженер")

    def test_rename_keeps_single_record(self):
        self.run_sync_with([ad_entry()])
        self.run_sync_with([ad_entry(sAMAccountName="ivanov2", sn="Петров", displayName="Петров Иван")])
        self.assertEqual(Employee.objects.count(), 1)
        self.assertEqual(Employee.objects.get().sam_account_name, "ivanov2")

    def test_missing_employee_is_deactivated_not_deleted(self):
        self.run_sync_with([ad_entry(), ad_entry(objectGUID="{aaaaaaaa-0000-4000-8000-000000000001}",
                                                 sAMAccountName="petrov", sn="Петров")])
        run = self.run_sync_with([ad_entry()])
        self.assertEqual(run.deactivated, 1)
        self.assertEqual(Employee.objects.count(), 2)
        self.assertFalse(Employee.objects.get(sam_account_name="petrov").is_active)

    def test_disabled_in_ad_becomes_inactive(self):
        self.run_sync_with([ad_entry()])
        self.run_sync_with([ad_entry(userAccountControl=514)])
        self.assertFalse(Employee.objects.get().is_active)

    def test_locked_fields_survive_sync(self):
        self.run_sync_with([ad_entry()])
        Employee.objects.update(locked_fields=["phone"], phone="+7 495 000-00-00")
        self.run_sync_with([ad_entry(telephoneNumber="+7 495 999-99-99")])
        self.assertEqual(Employee.objects.get().phone, "+7 495 000-00-00")

    def test_manager_link_is_resolved(self):
        boss = ad_entry(
            objectGUID="{bbbbbbbb-0000-4000-8000-000000000002}",
            sAMAccountName="boss", sn="Сидоров", displayName="Сидоров Сидор",
        )
        boss["dn"] = "CN=Sidorov,OU=Users,DC=corp,DC=local"
        subordinate = ad_entry(manager="CN=Sidorov,OU=Users,DC=corp,DC=local")
        self.run_sync_with([boss, subordinate])
        self.assertEqual(Employee.objects.get(sam_account_name="ivanov").manager.sam_account_name, "boss")

    def test_dry_run_writes_nothing(self):
        run = self.run_sync_with([ad_entry()], dry_run=True)
        self.assertEqual(Employee.objects.count(), 0)
        self.assertEqual(run.skipped, 1)


@override_settings(API_REQUIRE_KEY=False)
class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="ivanov", full_name="Иванов Иван Иванович",
            display_name="Иванов Иван", department="Отдел разработки", title="Инженер",
            email="ivanov@corp.local", phone="+7 (495) 123-45-67", search_phone="74951234567 1234",
        )
        Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="petrov", full_name="Петров Пётр",
            department="Бухгалтерия", title="Бухгалтер", search_phone="74957654321",
        )
        Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="uvolen", full_name="Уволенный Сотрудник",
            department="Бухгалтерия", is_active=False,
        )

    def test_list_hides_inactive(self):
        response = self.client.get(reverse("employee-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

    def test_search_by_name(self):
        response = self.client.get(reverse("employee-list"), {"q": "иванов"})
        self.assertEqual(response.json()["count"], 1)

    def test_search_by_phone_in_any_format(self):
        response = self.client.get(reverse("employee-list"), {"phone": "+7 (495) 123-45-67"})
        self.assertEqual(response.json()["count"], 1)

    def test_filter_by_department(self):
        response = self.client.get(reverse("employee-list"), {"department": "Бухгалтерия"})
        self.assertEqual(response.json()["count"], 1)

    def test_departments_endpoint(self):
        response = self.client.get(reverse("department-list"))
        self.assertEqual(
            response.json(),
            [{"department": "Бухгалтерия", "employees": 1}, {"department": "Отдел разработки", "employees": 1}],
        )

    def test_health(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.json()["employees_active"], 2)


@override_settings(API_REQUIRE_KEY=True, API_KEY="secret-key")
class ApiKeyTests(TestCase):
    def test_request_without_key_is_rejected(self):
        self.assertEqual(self.client.get(reverse("employee-list")).status_code, 403)

    def test_request_with_key_is_allowed(self):
        response = self.client.get(reverse("employee-list"), headers={"x-api-key": "secret-key"})
        self.assertEqual(response.status_code, 200)
