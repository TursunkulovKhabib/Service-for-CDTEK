import io
import shutil
import tempfile
import uuid

from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from employees.models import Employee
from employees.services import PhotoService
from employees.tests.factories import make_company

PHOTO_DIR = tempfile.mkdtemp(prefix="contacts-photos-")

PHOTO_STORAGE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "photos": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": PHOTO_DIR, "base_url": "/media/photos/"},
    },
}


def jpeg(width: int = 600, height: int = 800, color=(30, 90, 160)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, "JPEG")
    return buffer.getvalue()


@override_settings(STORAGES=PHOTO_STORAGE)
class PhotoStorageTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, PHOTO_DIR, True)

    def setUp(self):
        self.company = make_company(code="cdtek", name="ЦЦ ТЭК")
        self.employee = Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="ivanov", full_name="Иванов Иван",
            email="ivanov@cdtek.ru", zup_uid="zup-0001", company=self.company,
        )
        self.photos = PhotoService()

    def store(self, raw: bytes = None):
        changed = self.photos.store(self.employee, raw if raw is not None else jpeg())
        self.employee.save()
        return changed

    def test_original_goes_to_company_and_uid_folder(self):
        self.store()
        self.assertEqual(self.employee.photo_dir, "cdtek/zup-0001")
        self.assertTrue(self.photos.storage.exists("cdtek/zup-0001/original.jpg"))

    def test_login_is_used_when_there_is_no_uid_from_1c(self):
        self.employee.zup_uid = ""
        self.store()
        self.assertEqual(self.employee.photo_dir, "cdtek/ivanov")

    def test_second_company_keeps_its_own_folder(self):
        engs = make_company(code="engs", name="ЭНГС")
        self.employee.company = engs
        self.store()
        self.assertEqual(self.employee.photo_dir, "engs/zup-0001")

    def test_same_photo_is_not_written_twice(self):
        raw = jpeg()
        self.assertTrue(self.store(raw))
        self.assertFalse(self.store(raw))

    def test_new_photo_replaces_the_old_one(self):
        self.store(jpeg(color=(10, 10, 10)))
        first = self.employee.photo_hash
        self.assertTrue(self.store(jpeg(color=(200, 200, 200))))
        self.assertNotEqual(self.employee.photo_hash, first)

    def test_thumb_is_built_on_first_request(self):
        self.store()
        self.assertFalse(self.photos.storage.exists("cdtek/zup-0001/thumb.jpg"))
        raw = self.photos.read(self.employee, "thumb")
        self.assertTrue(self.photos.storage.exists("cdtek/zup-0001/thumb.jpg"))
        with Image.open(io.BytesIO(raw)) as image:
            self.assertLessEqual(max(image.size), 100)

    def test_card_keeps_proportions_and_fits_the_box(self):
        self.store()
        with Image.open(io.BytesIO(self.photos.read(self.employee, "card"))) as image:
            self.assertLessEqual(image.width, 400)
            self.assertLessEqual(image.height, 650)
            self.assertAlmostEqual(image.width / image.height, 600 / 800, places=2)

    def test_small_photo_is_not_stretched(self):
        self.store(jpeg(60, 80))
        with Image.open(io.BytesIO(self.photos.read(self.employee, "card"))) as image:
            self.assertEqual(image.size, (60, 80))

    def test_changed_uid_moves_the_folder(self):
        self.store()
        self.employee.zup_uid = "zup-0002"
        self.store(jpeg(color=(1, 2, 3)))
        self.assertEqual(self.employee.photo_dir, "cdtek/zup-0002")
        self.assertFalse(self.photos.storage.exists("cdtek/zup-0001/original.jpg"))

    def test_photo_removed_from_ad_is_removed_from_disk(self):
        self.store()
        self.assertTrue(self.photos.store(self.employee, None))
        self.assertFalse(self.photos.storage.exists("cdtek/zup-0001/original.jpg"))
        self.assertEqual(self.employee.photo_hash, "")

    def test_rebuild_recreates_derived_formats(self):
        self.store()
        self.photos.read(self.employee, "thumb")
        self.photos.remove_file("cdtek/zup-0001/thumb.jpg")
        self.assertEqual(self.photos.rebuild(self.employee), 2)

    def test_legacy_fields_take_thumb_and_card(self):
        self.store()
        self.assertTrue(self.employee.photo_base64)
        self.assertNotEqual(self.employee.photo_base64, self.employee.photo_big_base64)

    def test_employee_without_photo_returns_empty_string(self):
        self.assertFalse(self.employee.has_photo)
        self.assertEqual(self.employee.photo_base64, "")


@override_settings(STORAGES=PHOTO_STORAGE, API_V2_REQUIRE_JWT=False)
class PhotoApiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, PHOTO_DIR, True)

    def setUp(self):
        self.company = make_company(code="cdtek", name="ЦЦ ТЭК")
        self.employee = Employee.objects.create(
            object_guid=uuid.uuid4(), sam_account_name="ivanov", full_name="Иванов Иван",
            email="ivanov@cdtek.ru", zup_uid="zup-0100", company=self.company,
        )
        PhotoService().store(self.employee, jpeg())
        self.employee.save()

    def url(self, size: str = "") -> str:
        address = reverse("v2:employee-photo", args=[str(self.employee.object_guid)])
        return f"{address}?size={size}" if size else address

    def test_endpoint_returns_an_image(self):
        response = self.client.get(self.url("card"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        with Image.open(io.BytesIO(response.content)) as image:
            self.assertLessEqual(image.width, 400)

    def test_unknown_size_is_rejected(self):
        self.assertEqual(self.client.get(self.url("huge")).status_code, 400)

    def test_missing_photo_gives_404(self):
        other = Employee.objects.create(
            object_guid=uuid.uuid4(), full_name="Без фото", email="nophoto@cdtek.ru",
            company=self.company,
        )
        url = reverse("v2:employee-photo", args=[str(other.object_guid)])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_detail_lists_photo_addresses(self):
        url = reverse("v2:employee-detail", args=[str(self.employee.object_guid)])
        payload = self.client.get(url).json()
        self.assertEqual(set(payload["photo"]), {"thumb", "card", "original"})
        self.assertIn("size=card", payload["photo"]["card"])
