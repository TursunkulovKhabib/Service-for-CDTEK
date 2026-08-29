from .env import env, env_bool

LEGACY_V1 = {
    "FIELDS": {
        "fio": "full_name",
        "position": "title",
        "department": "department",
        "phone": "phone",
    },
    "DETAIL_FIELDS": {
        "fio": "full_name",
        "position": "title",
        "department": "department",
        "phone": "phone",
        "email": "email",
        "login": "sam_account_name",
    },
    "LOOKUP_FIELD": "sam_account_name",
    "ENVELOPE": env("LEGACY_V1_ENVELOPE", ""),
    "EMPTY_VALUE": env("LEGACY_V1_EMPTY_VALUE", ""),
    "PAGINATED": env_bool("LEGACY_V1_PAGINATED", False),
    "SEARCH_PARAM": env("LEGACY_V1_SEARCH_PARAM", "query"),
    "DEPARTMENT_PARAM": env("LEGACY_V1_DEPARTMENT_PARAM", "department"),
    "COMPANY_PARAM": env("LEGACY_V1_COMPANY_PARAM", "company"),
    "LIMIT_PARAM": env("LEGACY_V1_LIMIT_PARAM", "limit"),
    "DEFAULT_LIMIT": 500,
}

LEGACY_V1_REQUIRE_BASIC_AUTH = env_bool("LEGACY_V1_REQUIRE_BASIC_AUTH", False)
