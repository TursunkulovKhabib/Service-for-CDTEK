from .env import env, env_bool, env_int, env_list

LEGACY_V1 = {
    "BASE_FIELDS": {
        "full_name": "full_name",
        "first_name": "first_name",
        "surename": "last_name",
        "patronymic": "middle_name",
        "email": "email",
        "updated": "updated",
        "state": "state",
        "photo": "photo_base64",
    },
    "FULL_FIELDS": {
        "department": "department",
        "position": "title",
        "phone_mobile": "phone_mobile",
        "phone_internal": "phone_internal",
        "phone_mobile_work": "phone_mobile_work",
    },
    "EXTENDED_FIELDS": {
        "zup_uid": "zup_uid",
        "zup_state": "zup_state",
        "zup_state_dateto": "zup_state_dateto",
        "birthday": "birthday_str",
        "org_id": "org_id",
        "org_name": "org_name",
        "country_id": "country_id",
        "country_name": "country_name",
        "do_user_uid": "do_user_uid",
        "do_user_state": "do_user_state",
        "do_user_role": "do_user_role",
        "vocation_days": "vacation_days",
    },
    "CONSENT_FIELD": {"personal_data_consent": "personal_data_consent"},
    "BIG_PHOTO_FIELD": {"photo_big": "photo_big_base64"},
    "DATE_FORMAT": "%d.%m.%Y",
    "DEFAULT_LIMIT": 20,
    "DEFAULT_MIN_DIGIT": 3,
    "NULL_TO_EMPTY": True,
}

LEGACY_V1_ACTIONS = (
    ("getuserlist", "1 - getuserlist: сотрудники, изменённые с даты"),
    ("getboss", "2 - getboss: руководитель по UID 1С"),
    ("getdepartments", "3 - getdepartments: подразделения"),
    ("searchuserlist", "4 - searchuserlist: поиск по строке"),
    ("getuserlistbyemailarray", "5 - getuserlistbyemailarray: выборка по списку почт"),
    ("searchuserlistrank", "6 - searchuserlistrank: поиск с ранжированием"),
    ("getcountries", "7 - getcountries: страны"),
    ("getorganizations", "8 - getorganizations: организации"),
)

LEGACY_V1_ACTION_ALIASES = {
    str(number): name for number, (name, _) in enumerate(LEGACY_V1_ACTIONS, start=1)
}

LEGACY_V1_REQUIRE_BASIC_AUTH = env_bool("LEGACY_V1_REQUIRE_BASIC_AUTH", True)

LEGACY_V1_DEFAULT_ORG_ID = env("LEGACY_V1_DEFAULT_ORG_ID", "engsdrilling.ru")

LEGACY_WORK_STATUSES = {
    "w": "Работа",
    "work": "Работа",
    "работа": "Работа",
    "bt": "Командировка",
    "business_trip": "Командировка",
    "командировка": "Командировка",
    "v": "Отпуск",
    "vocation": "Отпуск",
    "отпуск": "Отпуск",
    "av": "ДополнительныеВыходныеДниНеОплачиваемые",
    "additional_vocation": "ДополнительныеВыходныеДниНеОплачиваемые",
    "доп.отпуск": "ДополнительныеВыходныеДниНеОплачиваемые",
    "v_av": "Отпуск|ДополнительныeВыходныеДниНеОплачиваемые",
    "vocation_and_additional_vocation": "Отпуск|ДополнительныеВыходныеДниНеОплачиваемые",
    "sl": "Больничный",
    "sick_leave": "Больничный",
    "больничный": "Больничный",
}


def _parse_clients(raw: str) -> dict:
    """LEGACY_V1_CLIENTS='логин:пароль:право1,право2;логин2:пароль2:право3'."""
    clients = {}
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(":")
        if len(parts) < 3:
            continue
        login, password, permissions = parts[0], parts[1], ":".join(parts[2:])
        clients[login.strip()] = {
            "password": password.strip(),
            "permissions": {p.strip().lower() for p in permissions.split(",") if p.strip()},
        }
    return clients


LEGACY_V1_CLIENTS = _parse_clients(env("LEGACY_V1_CLIENTS", ""))
