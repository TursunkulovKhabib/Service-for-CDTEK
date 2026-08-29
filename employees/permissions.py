from django.conf import settings
from rest_framework.permissions import BasePermission, IsAuthenticated


class LegacyV1Permission(BasePermission):
    message = "Требуется basic-авторизация."

    def has_permission(self, request, view) -> bool:
        if not getattr(settings, "LEGACY_V1_REQUIRE_BASIC_AUTH", False):
            return True
        return bool(request.user and request.user.is_authenticated)


class JwtRequiredPermission(IsAuthenticated):
    message = "Требуется JWT-токен: заголовок Authorization: Bearer <token>."

    def has_permission(self, request, view) -> bool:
        if not getattr(settings, "API_V2_REQUIRE_JWT", True):
            return True
        return super().has_permission(request, view)
