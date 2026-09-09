from pathlib import Path

from .env import BASE_DIR, env, env_int

PHOTO_ROOT = Path(env("PHOTO_ROOT", str(BASE_DIR / "media" / "photos")))
PHOTO_URL = env("PHOTO_URL", "/media/photos/")

PHOTO_SIZES = {
    "thumb": (100, 100),
    "card": (400, 650),
    "original": None,
}

PHOTO_FORMAT = env("PHOTO_FORMAT", "JPEG")
PHOTO_EXTENSION = env("PHOTO_EXTENSION", "jpg")
PHOTO_QUALITY = env_int("PHOTO_QUALITY", 85)
