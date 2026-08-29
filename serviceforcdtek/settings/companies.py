from .env import env, env_bool, env_int, env_list

COMPANIES = [
    {
        "code": "cdtek",
        "name": "ЦЦ ТЭК",
        "short_name": "ЦЦ ТЭК",
        "is_default": True,
        "is_active": True,
        "ldap": {
            "name": "AD ЦЦ ТЭК",
            "profile": "ad",
            "server_uri": env("LDAP_CDTEK_SERVER_URI", "ldaps://dc01.corp.local"),
            "port": env_int("LDAP_CDTEK_PORT", 0) or None,
            "use_ssl": env_bool("LDAP_CDTEK_USE_SSL", True),
            "start_tls": env_bool("LDAP_CDTEK_START_TLS", False),
            "tls_validate": env_bool("LDAP_CDTEK_TLS_VALIDATE", True),
            "ca_certs_file": env("LDAP_CDTEK_CA_CERTS_FILE", ""),
            "bind_dn": env("LDAP_CDTEK_BIND_DN", ""),
            "bind_password_env": "LDAP_CDTEK_BIND_PASSWORD",
            "base_dn": env("LDAP_CDTEK_BASE_DN", "DC=corp,DC=local"),
            "search_ous": env_list("LDAP_CDTEK_SEARCH_OUS", ""),
        },
    },
    {
        "code": "engs",
        "name": "ЭНГС",
        "short_name": "ЭНГС",
        "is_default": False,
        "is_active": env_bool("COMPANY_ENGS_ENABLED", False),
        "ldap": {
            "name": "AD ЭНГС",
            "profile": "ad",
            "server_uri": env("LDAP_ENGS_SERVER_URI", "ldaps://dc02.engs.local"),
            "port": env_int("LDAP_ENGS_PORT", 0) or None,
            "use_ssl": env_bool("LDAP_ENGS_USE_SSL", True),
            "start_tls": env_bool("LDAP_ENGS_START_TLS", False),
            "tls_validate": env_bool("LDAP_ENGS_TLS_VALIDATE", True),
            "ca_certs_file": env("LDAP_ENGS_CA_CERTS_FILE", ""),
            "bind_dn": env("LDAP_ENGS_BIND_DN", ""),
            "bind_password_env": "LDAP_ENGS_BIND_PASSWORD",
            "base_dn": env("LDAP_ENGS_BASE_DN", "DC=branch,DC=local"),
            "search_ous": env_list("LDAP_ENGS_SEARCH_OUS", ""),
        },
    },
]

COMPANY_DEFAULT_CODE = env("COMPANY_DEFAULT_CODE", "cdtek")
