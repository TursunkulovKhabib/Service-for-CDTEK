from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from employees.models import ApiClient


class ApiClientAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "admin-secret")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_add_page_opens(self):
        response = self.client.get(reverse("admin:employees_apiclient_add"))
        self.assertEqual(response.status_code, 200)

    def test_client_is_created_with_hashed_password(self):
        response = self.client.post(reverse("admin:employees_apiclient_add"), {
            "login": "portal", "description": "Портал", "is_active": "on",
            "new_password": "portal-secret", "permissions": ["getuserlist"],
        })
        self.assertEqual(response.status_code, 302)
        client = ApiClient.objects.get(login="portal")
        self.assertNotIn("portal-secret", client.password_hash)
        self.assertTrue(client.check_password("portal-secret"))
        self.assertEqual(client.permissions, ["getuserlist"])

    def test_new_client_without_password_is_rejected(self):
        response = self.client.post(reverse("admin:employees_apiclient_add"), {
            "login": "empty", "is_active": "on", "permissions": ["getuserlist"],
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ApiClient.objects.filter(login="empty").exists())

    def test_editing_without_password_keeps_the_old_one(self):
        client = ApiClient.objects.create(login="portal", permissions=["getuserlist"])
        client.set_password("portal-secret", save=True)
        url = reverse("admin:employees_apiclient_change", args=[client.pk])
        response = self.client.post(url, {
            "login": "portal", "description": "Портал корпоративный", "is_active": "on",
            "new_password": "", "permissions": ["getuserlist", "getcountries"],
        })
        self.assertEqual(response.status_code, 302)
        client.refresh_from_db()
        self.assertTrue(client.check_password("portal-secret"))
        self.assertEqual(client.permissions, ["getuserlist", "getcountries"])
