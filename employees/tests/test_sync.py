from unittest import mock

from django.test import TestCase, override_settings

from employees.models import Employee, SyncRun
from employees.services import LdapSyncService
from employees.tests.factories import FakeClient, ad_entry, make_company, make_server

LDAP_SETTINGS = {
    "PROFILE": "ad",
    "SERVER_URI": "ldap://fake",
    "BASE_DN": "DC=corp,DC=local",
    "DEACTIVATE_MISSING": True,
    "MIN_ENTRIES_FOR_DEACTIVATION": 1,
}


@override_settings(LDAP=LDAP_SETTINGS)
class SyncServiceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.server = make_server(self.company)
        self.service = LdapSyncService()

    def run_sync_with(self, entries, **kwargs):
        from employees.services import sync as sync_module

        FakeClient.entries = entries
        FakeClient.entries_by_uri = {}
        kwargs.setdefault("ldap_server", self.server)
        with mock.patch.object(sync_module, "LdapClient", FakeClient):
            return self.service.run(**kwargs)

    def test_full_sync_creates_then_updates_without_duplicates(self):
        run = self.run_sync_with([ad_entry()])
        self.assertEqual(run.status, SyncRun.Status.SUCCESS)
        self.assertEqual((run.created, run.updated), (1, 0))

        run = self.run_sync_with([ad_entry(title="Ведущий инженер")])
        self.assertEqual((run.created, run.updated), (0, 1))
        self.assertEqual(Employee.objects.count(), 1)
        self.assertEqual(Employee.objects.get().title, "Ведущий инженер")

    def test_employee_is_linked_to_company_and_server(self):
        self.run_sync_with([ad_entry()])
        employee = Employee.objects.get()
        self.assertEqual(employee.company, self.company)
        self.assertEqual(employee.ldap_server, self.server)

    def test_rename_keeps_single_record(self):
        self.run_sync_with([ad_entry()])
        self.run_sync_with([ad_entry(sAMAccountName="ivanov2", sn="Петров", displayName="Петров Иван")])
        self.assertEqual(Employee.objects.count(), 1)
        self.assertEqual(Employee.objects.get().sam_account_name, "ivanov2")

    def test_missing_employee_is_deactivated_not_deleted(self):
        self.run_sync_with([
            ad_entry(),
            ad_entry(objectGUID="{aaaaaaaa-0000-4000-8000-000000000001}",
                     sAMAccountName="petrov", sn="Петров"),
        ])
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
            dn="CN=Sidorov,OU=Users,DC=corp,DC=local",
        )
        subordinate = ad_entry(manager="CN=Sidorov,OU=Users,DC=corp,DC=local")
        self.run_sync_with([boss, subordinate])
        self.assertEqual(Employee.objects.get(sam_account_name="ivanov").manager.sam_account_name, "boss")

    def test_dry_run_writes_nothing(self):
        run = self.run_sync_with([ad_entry()], dry_run=True)
        self.assertEqual(Employee.objects.count(), 0)
        self.assertEqual(run.skipped, 1)

    def test_run_is_linked_to_company(self):
        run = self.run_sync_with([ad_entry()])
        self.assertEqual(run.company, self.company)
        self.assertEqual(run.ldap_server, self.server)


@override_settings(LDAP=LDAP_SETTINGS)
class TwoCompaniesTests(TestCase):
    def setUp(self):
        self.cdtek = make_company(code="cdtek", name="ЦЦ ТЭК")
        self.engs = make_company(code="engs", name="ЭНГС")
        self.server_cdtek = make_server(self.cdtek, name="AD ЦЦ ТЭК", server_uri="ldap://dc1")
        self.server_engs = make_server(self.engs, name="AD ЭНГС", server_uri="ldap://dc2")
        self.service = LdapSyncService()

        self.entry_cdtek = ad_entry()
        self.entry_engs = ad_entry(
            objectGUID="{dddddddd-0000-4000-8000-000000000004}",
            sAMAccountName="sokolov", sn="Соколов", givenName="Олег", middleName="",
            displayName="Соколов Олег", department="Логистика", company="ЭНГС",
            dn="CN=Sokolov,OU=Users,DC=branch,DC=local",
        )

    def sync_both(self):
        from employees.services import sync as sync_module

        FakeClient.entries_by_uri = {
            "ldap://dc1": [self.entry_cdtek],
            "ldap://dc2": [self.entry_engs],
        }
        with mock.patch.object(sync_module, "LdapClient", FakeClient):
            return [
                self.service.run(ldap_server=self.server_cdtek),
                self.service.run(ldap_server=self.server_engs),
            ]

    def test_each_company_gets_its_own_employees(self):
        self.sync_both()
        self.assertEqual(Employee.objects.filter(company=self.cdtek).count(), 1)
        self.assertEqual(Employee.objects.filter(company=self.engs).count(), 1)
        self.assertEqual(Employee.objects.get(company=self.engs).sam_account_name, "sokolov")

    def test_full_sync_of_one_company_does_not_touch_another(self):
        self.sync_both()

        from employees.services import sync as sync_module

        replacement = ad_entry(
            objectGUID="{eeeeeeee-0000-4000-8000-000000000005}",
            sAMAccountName="novikov", sn="Новиков", givenName="Пётр", middleName="",
            displayName="Новиков Пётр", dn="CN=Novikov,OU=Users,DC=corp,DC=local",
        )
        FakeClient.entries_by_uri = {"ldap://dc1": [replacement], "ldap://dc2": [self.entry_engs]}
        with mock.patch.object(sync_module, "LdapClient", FakeClient):
            run = self.service.run(ldap_server=self.server_cdtek)

        self.assertEqual(run.deactivated, 1)
        self.assertFalse(Employee.objects.get(sam_account_name="ivanov").is_active)
        self.assertTrue(Employee.objects.get(company=self.engs).is_active)

    def test_deactivation_is_skipped_when_directory_returns_too_few_entries(self):
        self.sync_both()

        from employees.services import sync as sync_module

        FakeClient.entries_by_uri = {"ldap://dc1": [], "ldap://dc2": [self.entry_engs]}
        with mock.patch.object(sync_module, "LdapClient", FakeClient):
            run = self.service.run(ldap_server=self.server_cdtek)

        self.assertEqual(run.deactivated, 0)
        self.assertTrue(Employee.objects.get(company=self.cdtek).is_active)

    def test_sync_all_walks_every_active_server(self):
        from employees.services import sync as sync_module

        FakeClient.entries_by_uri = {
            "ldap://dc1": [self.entry_cdtek],
            "ldap://dc2": [self.entry_engs],
        }
        with mock.patch.object(sync_module, "LdapClient", FakeClient):
            runs = self.service.sync_all()

        self.assertEqual(len(runs), 2)
        self.assertEqual(Employee.objects.count(), 2)

    def test_inactive_company_is_skipped(self):
        self.engs.deactivate()

        from employees.services import sync as sync_module

        FakeClient.entries_by_uri = {"ldap://dc1": [self.entry_cdtek], "ldap://dc2": [self.entry_engs]}
        with mock.patch.object(sync_module, "LdapClient", FakeClient):
            runs = self.service.sync_all()

        self.assertEqual(len(runs), 1)
        self.assertEqual(Employee.objects.count(), 1)


class CompanyServiceTests(TestCase):
    @override_settings(COMPANIES=[
        {"code": "one", "name": "Первая", "is_default": True, "is_active": True,
         "ldap": {"name": "AD Первая", "server_uri": "ldaps://dc1", "base_dn": "DC=one,DC=local",
                  "bind_password_env": "PWD_ONE", "search_ous": ["OU=Users,DC=one,DC=local"]}},
        {"code": "two", "name": "Вторая", "is_active": True,
         "ldap": {"name": "AD Вторая", "server_uri": "ldaps://dc2", "base_dn": "DC=two,DC=local"}},
    ])
    def test_companies_and_servers_are_loaded_from_settings(self):
        from employees.models import Company, LdapServer
        from employees.services import CompanyService

        stats = CompanyService().load_from_settings()
        self.assertEqual(stats, {"companies": 2, "servers": 2})
        self.assertEqual(Company.objects.count(), 2)
        self.assertEqual(LdapServer.objects.count(), 2)
        server = LdapServer.objects.get(name="AD Первая")
        self.assertEqual(server.company.code, "one")
        self.assertEqual(server.search_ous, ["OU=Users,DC=one,DC=local"])

    @override_settings(COMPANIES=[{"code": "one", "name": "Первая", "is_active": True,
                                   "ldap": {"name": "AD Первая", "server_uri": "ldaps://dc1",
                                            "base_dn": "DC=one,DC=local"}}])
    def test_load_is_idempotent(self):
        from employees.models import Company
        from employees.services import CompanyService

        CompanyService().load_from_settings()
        CompanyService().load_from_settings()
        self.assertEqual(Company.objects.count(), 1)


class LdapServerSecurityTests(TestCase):
    def test_password_is_taken_from_environment_when_configured(self):
        import os

        company = make_company()
        server = make_server(company, bind_password="из-базы", bind_password_env="TEST_LDAP_PWD")
        os.environ["TEST_LDAP_PWD"] = "из-окружения"
        try:
            self.assertEqual(server.resolve_password(), "из-окружения")
            self.assertIn("TEST_LDAP_PWD", server.password_source)
        finally:
            del os.environ["TEST_LDAP_PWD"]

    def test_password_never_leaks_into_str(self):
        company = make_company()
        server = make_server(company, bind_password="секрет")
        self.assertNotIn("секрет", str(server))
