import os

_environment = os.environ.get("DJANGO_ENV", "dev").strip().lower()

if _environment in {"prod", "production"}:
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
