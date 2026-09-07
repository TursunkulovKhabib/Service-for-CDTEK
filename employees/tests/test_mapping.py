import uuid
from datetime import date, datetime, timezone

from django.test import TestCase, override_settings

from employees.tests.factories import ad_entry
from ldapsync.config import TRANSFER_POSITION_TEXT, get_profile, load_settings
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

    def test_full_name_is_built_from_sn_given_middle(self):
        payload = build_payload(ad_entry(), AD)
        self.assertEqual(payload["full_name"], "Иванов Иван Иванович")

    def test_work_phones_are_joined_like_in_java(self):
        payload = build_payload(ad_entry(), AD)
        self.assertEqual(payload["phone_mobile"], "+7 916 000-11-22")
        self.assertEqual(payload["phone_mobile_work"], "+7 (495) 123-45-67; +7 916 555-44-33")
        self.assertEqual(payload["phone_internal"], "1234; 5678")

    def test_search_phone_collects_digits_of_every_number(self):
        payload = build_payload(ad_entry(), AD)
        for expected in ("79160001122", "74951234567", "79165554433", "1234", "5678"):
            self.assertIn(expected, payload["search_phone"])

    def test_extension_attributes_are_mapped(self):
        payload = build_payload(ad_entry(), AD)
        self.assertEqual(payload["department_code"], "ОР-01")
        self.assertEqual(payload["project_name"], "Проект Север")
        self.assertEqual(payload["birthday"], date(1990, 5, 17))
        self.assertTrue(payload["personal_data_consent"])

    def test_birthday_of_wrong_length_is_ignored(self):
        self.assertIsNone(build_payload(ad_entry(extensionAttribute1="1990"), AD)["birthday"])

    def test_transfer_flag_replaces_position(self):
        payload = build_payload(ad_entry(extensionAttribute6="1"), AD)
        self.assertEqual(payload["title"], TRANSFER_POSITION_TEXT)

    def test_employee_number_goes_to_zup_uid(self):
        self.assertEqual(build_payload(ad_entry(), AD)["zup_uid"], "zup-0001")

    def test_region_and_office(self):
        payload = build_payload(ad_entry(), AD)
        self.assertEqual(payload["region"], "Москва")
        self.assertEqual(payload["office"], "Главный офис")

    def test_disabled_account_detected_by_uac_bit(self):
        self.assertFalse(build_payload(ad_entry(userAccountControl=514), AD)["ad_enabled"])

    def test_generalized_time_parsed(self):
        parsed = parse_ldap_datetime("20260801100000.0Z")
        self.assertEqual(parsed, datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc))

    def test_digits_only_splits_joined_phones(self):
        self.assertEqual(digits_only("+7 (495) 123-45-67; 1234"), "74951234567 1234")


class FilterTests(TestCase):
    @override_settings(LDAP={"PROFILE": "ad", "SERVER_URI": "ldaps://dc", "BASE_DN": "DC=corp,DC=local"})
    def test_base_filter_matches_legacy_service(self):
        config = load_settings()
        self.assertIn("(objectCategory=person)", config.build_filter())
        self.assertIn("(sAMAccountName=*)", config.build_filter())

    @override_settings(
        LDAP={"PROFILE": "ad", "SERVER_URI": "ldaps://dc", "BASE_DN": "DC=corp,DC=local",
              "INCLUDE_DISABLED": True}
    )
    def test_disabled_accounts_are_fetched_when_allowed(self):
        config = load_settings()
        built = config.build_filter("20260801100000.0Z")
        self.assertIn("(whenChanged>=20260801100000.0Z)", built)
        self.assertNotIn("1.2.840.113556.1.4.803", built)

    @override_settings(LDAP={"PROFILE": "ad", "SERVER_URI": "ldaps://dc", "BASE_DN": "DC=corp,DC=local"})
    def test_requested_attributes_cover_the_mapping(self):
        config = load_settings()
        attributes = config.profile.attributes()
        for attribute in ("sAMAccountName", "employeeNumber", "homePhone", "otherTelephone",
                          "ipPhone", "extensionAttribute1", "extensionAttribute2",
                          "extensionAttribute4", "extensionAttribute7", "thumbnailPhoto"):
            self.assertIn(attribute, attributes)
