from .env import env, env_bool, env_int, env_list

LDAP = {
    "PROFILE": env("LDAP_PROFILE", "ad"),
    "SERVER_URI": env("LDAP_SERVER_URI", "ldaps://dc01.corp.local"),
    "PORT": env_int("LDAP_PORT", 0) or None,
    "USE_SSL": env_bool("LDAP_USE_SSL", True),
    "START_TLS": env_bool("LDAP_START_TLS", False),
    "TLS_VALIDATE": env_bool("LDAP_TLS_VALIDATE", True),
    "CA_CERTS_FILE": env("LDAP_CA_CERTS_FILE", "") or None,
    "BIND_DN": env("LDAP_BIND_DN", ""),
    "BIND_PASSWORD": env("LDAP_BIND_PASSWORD", ""),
    "AUTHENTICATION": env("LDAP_AUTHENTICATION", "SIMPLE"),
    "BASE_DN": env("LDAP_BASE_DN", "DC=corp,DC=local"),
    "SEARCH_OUS": env_list("LDAP_SEARCH_OUS", ""),
    "USER_FILTER": env("LDAP_USER_FILTER", ""),
    "INCLUDE_DISABLED": env_bool("LDAP_INCLUDE_DISABLED", False),
    "PAGE_SIZE": env_int("LDAP_PAGE_SIZE", 500),
    "TIMEOUT": env_int("LDAP_TIMEOUT", 30),
    "RECEIVE_TIMEOUT": env_int("LDAP_RECEIVE_TIMEOUT", 60),
    "DEACTIVATE_MISSING": env_bool("LDAP_DEACTIVATE_MISSING", True),
    "MIN_ENTRIES_FOR_DEACTIVATION": env_int("LDAP_MIN_ENTRIES_FOR_DEACTIVATION", 1),
}

LDAP_SYNC_INCREMENTAL_MINUTES = env_int("LDAP_SYNC_INCREMENTAL_MINUTES", 15)
LDAP_SYNC_FULL_CRON = env("LDAP_SYNC_FULL_CRON", "20 3 * * *")
LDAP_INCREMENTAL_OVERLAP_MINUTES = env_int("LDAP_INCREMENTAL_OVERLAP_MINUTES", 10)
