import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission

API_KEY_HEADER = "HTTP_X_API_KEY"


class HasAPIKeyOrIsAuthenticated(BasePermission):

    message = "Требуется корректный заголовок X-API-Key."

    def has_permission(self, request, view) -> bool:
        if not getattr(settings, "API_REQUIRE_KEY", False):
            return True
        if request.user and request.user.is_authenticated:
            return True
        expected = getattr(settings, "API_KEY", "")
        provided = request.META.get(API_KEY_HEADER, "")
        return bool(expected) and hmac.compare_digest(provided, expected)
