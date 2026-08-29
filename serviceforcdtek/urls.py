from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path("", lambda request: redirect("admin:index"), name="root"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("employees.urls.v1", namespace="v1")),
    path("api/v2/", include("employees.urls.v2", namespace="v2")),
    path("api-auth/", include("rest_framework.urls")),
]
