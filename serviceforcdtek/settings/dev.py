from .base import *  # noqa: F401,F403
from .env import env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = ["*"]
LEGACY_V1_REQUIRE_BASIC_AUTH = env_bool("LEGACY_V1_REQUIRE_BASIC_AUTH", False)
API_V2_REQUIRE_JWT = env_bool("API_V2_REQUIRE_JWT", False)
