import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = env(name, "").strip()
    return int(raw) if raw else default


def env_list(name: str, default: str = "", sep: str = ";") -> list:
    raw = env(name, default)
    return [item.strip() for item in raw.split(sep) if item.strip()]


def secret(name: str, default: str = "") -> str:
    return env(name, default)
