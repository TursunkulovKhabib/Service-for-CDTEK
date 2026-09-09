import base64
import hashlib
import io
import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.utils import timezone

logger = logging.getLogger("employees.photos")

ORIGINAL = "original"


class PhotoService:
    """Фотографии сотрудников на диске: оригинал из AD и два уменьшенных формата.

    Файлы лежат в отдельном хранилище, а не в базе: папка на организацию,
    внутри - папка по UID сотрудника из 1С. Хранилище берётся из настроек,
    поэтому переезд на S3 - это смена бэкенда, а не правка кода.
    """

    def __init__(self, storage=None):
        self._storage = storage

    @property
    def storage(self):
        return self._storage if self._storage is not None else storages["photos"]

    def directory(self, employee) -> str:
        company = employee.company.code if employee.company_id else "unknown"
        uid = employee.zup_uid or employee.sam_account_name or str(employee.object_guid)
        return f"{company}/{uid}"

    def path(self, employee, size: str = ORIGINAL) -> str:
        folder = employee.photo_dir or self.directory(employee)
        return f"{folder}/{size}.{settings.PHOTO_EXTENSION}"

    def store(self, employee, raw: bytes) -> bool:
        """Кладёт оригинал на диск. Возвращает True, если файл поменялся."""
        if not raw:
            return self.delete(employee) if employee.photo_hash else False

        digest = hashlib.sha1(raw).hexdigest()
        folder = self.directory(employee)
        if employee.photo_hash == digest and employee.photo_dir == folder:
            return False

        if employee.photo_dir and employee.photo_dir != folder:
            self.remove_files(employee.photo_dir)

        employee.photo_dir = folder
        self.write(self.path(employee, ORIGINAL), raw)
        for size in settings.PHOTO_SIZES:
            if size != ORIGINAL:
                self.remove_file(self.path(employee, size))

        employee.photo_hash = digest
        employee.photo_updated_at = timezone.now()
        return True

    def read(self, employee, size: str = ORIGINAL):
        """Отдаёт файл нужного размера, создавая его при первом обращении."""
        if not employee.photo_hash or not employee.photo_dir:
            return None

        name = self.path(employee, size)
        if self.storage.exists(name):
            with self.storage.open(name, "rb") as stream:
                return stream.read()

        if size == ORIGINAL:
            return None

        original = self.read(employee, ORIGINAL)
        if original is None:
            return None

        resized = self.resize(original, settings.PHOTO_SIZES.get(size))
        if resized is None:
            return original
        self.write(name, resized)
        return resized

    def base64(self, employee, size: str = ORIGINAL) -> str:
        raw = self.read(employee, size)
        return base64.b64encode(raw).decode("ascii") if raw else ""

    def delete(self, employee) -> bool:
        if employee.photo_dir:
            self.remove_files(employee.photo_dir)
        changed = bool(employee.photo_hash or employee.photo_dir)
        employee.photo_hash = ""
        employee.photo_dir = ""
        employee.photo_updated_at = None
        return changed

    def rebuild(self, employee) -> int:
        """Пересоздаёт уменьшенные форматы - например, после смены размеров."""
        count = 0
        for size in settings.PHOTO_SIZES:
            if size == ORIGINAL:
                continue
            self.remove_file(self.path(employee, size))
            if self.read(employee, size):
                count += 1
        return count

    def write(self, name: str, data: bytes) -> None:
        self.remove_file(name)
        self.storage.save(name, ContentFile(data))

    def remove_file(self, name: str) -> None:
        try:
            if self.storage.exists(name):
                self.storage.delete(name)
        except (NotImplementedError, OSError) as exc:
            logger.warning("Не удалось удалить файл %s: %s", name, exc)

    def remove_files(self, folder: str) -> None:
        for size in settings.PHOTO_SIZES:
            self.remove_file(f"{folder}/{size}.{settings.PHOTO_EXTENSION}")

    @staticmethod
    def resize(raw: bytes, box):
        """Вписывает снимок в заданный прямоугольник: не обрезает и не растягивает."""
        if not box:
            return None
        try:
            from PIL import Image
        except ImportError:
            logger.warning("Pillow не установлен - уменьшенные форматы не создаются.")
            return None

        try:
            with Image.open(io.BytesIO(raw)) as image:
                image = image.convert("RGB")
                image.thumbnail(box, Image.LANCZOS)
                buffer = io.BytesIO()
                image.save(buffer, settings.PHOTO_FORMAT, quality=settings.PHOTO_QUALITY)
                return buffer.getvalue()
        except Exception as exc:
            logger.warning("Не удалось обработать фото: %s", exc)
            return None
