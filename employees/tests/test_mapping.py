import uuid
from datetime import datetime, timezone

from django.test import TestCase, override_settings

from employees.tests.factories import ad_entry
from ldapsync.config import get_profile, load_settings
from ldapsync.mapping import build_payload, digits_only, guid_to_uuid, parse_ldap_datetime

AD = get_profile("ad")


class MappingTests(TestCase):
    def test_guid_from_ad_bytes_is_mixed_endian(self):
        raw = uuid.UUID("c9b1e2d4-1111-4222-8333-444455556666").bytes_le
        self.assertEqual(str(guid_to_uuid(raw, "dn")), "c9b1e2d4-1111-4222-8333-444455556666")

    def test_guid_falls_back_to_uuid5_of_dn(self):
        first = guid_to_uuid(None, "CN=x,DC=corp,DC=local")
        second = guid_to_uuid(None, "cn=X,dc=corp,dc=local")
        self.assertEqual(first, second)

    def test_payload_fills_names_phones_and_flags(self):
        payload = build_payload(ad_entry(), AD)
        self.assertEqual(payload["full_name"], "Иванов Иван Иванович")
        self.assertEqual(payload["department"], "Отдел разработки")
        self.assertTrue(payload["ad_enabled"])
        self.assertIn("74951234567", payload["search_phone"])
        self.assertIn("1234", payload["search_phone"])

    def test_ad_company_goes_to_company_name(self):
        payload = build_payload(ad_entry(), AD)
        self.assertEqual(payload["company_name"], "ЦЦ ТЭК")

    def test_disabled_account_detected_by_uac_bit(self):
        payload = build_payload(ad_entry(userAccountControl=514), AD)
        self.assertFalse(payload["ad_enabled"])

    def test_generalized_time_parsed(self):
        parsed = parse_ldap_datetime("20260801100000.0Z")
        self.assertEqual(parsed, datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc))

    def test_digits_only_strips_formatting(self):
        self.assertEqual(digits_only("+7 (495) 123-45-67", None, "1234"), "74951234567 1234")


class FilterTests(TestCase):
    @override_settings(LDAP={"PROFILE": "ad", "SERVER_URI": "ldaps://dc", "BASE_DN": "DC=corp,DC=local"})
    def test_filter_excludes_disabled_accounts(self):
        config = load_settings()
        self.assertIn("userAccountControl:1.2.840.113556.1.4.803:=2", config.build_filter())

    @override_settings(
        LDAP={"PROFILE": "ad", "SERVER_URI": "ldaps://dc", "BASE_DN": "DC=corp,DC=local",
              "INCLUDE_DISABLED": True}
    )
    def test_incremental_filter_adds_when_changed(self):
        config = load_settings()
        built = config.build_filter("20260801100000.0Z")
        self.assertIn("(whenChanged>=20260801100000.0Z)", built)
        self.assertNotIn("1.2.840.113556.1.4.803", built)
