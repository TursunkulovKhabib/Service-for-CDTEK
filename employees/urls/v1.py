from django.urls import path

from employees.views import healthcheck
from employees.views.v1 import LegacyApiView, action_view

app_name = "v1"

ACTIONS = (
    "getuserlist",
    "getboss",
    "getdepartments",
    "searchuserlist",
    "getuserlistbyemailarray",
    "searchuserlistrank",
    "getcountries",
    "getorganizations",
)

urlpatterns = [
    path("UserService", LegacyApiView.as_view(), name="userservice"),
    path("health/", healthcheck, name="health"),
] + [
    path(f"{name}/", action_view(name), name=name) for name in ACTIONS
]
