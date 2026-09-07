from .env import env, env_bool, env_int, env_list

COMPANY_CODES = env_list("COMPANY_CODES", "cdtek;engs")
COMPANY_DEFAULT_CODE = env("COMPANY_DEFAULT_CODE", COMPANY_CODES[0] if COMPANY_CODES else "")

ONEC_SYSTEMS = ("ZUP", "DO", "VACATION")


def _ldap_block(code: str, prefix: str) -> dict:
    host = env(f"{prefix}_HOST", "")
    uri = env(f"{prefix}_SERVER_URI", "")
    use_ssl = env_bool(f"{prefix}_USE_SSL", False)
    if not uri and host:
        uri = f"{'ldaps' if use_ssl else 'ldap'}://{host}"

    domain = env(f"{prefix}_DOMAIN", "")
    bind_user = env(f"{prefix}_BIND_USER", "")
    bind_dn = env(f"{prefix}_BIND_DN", "")
    if not bind_dn and bind_user:
        bind_dn = f"{bind_user}@{domain}" if domain else bind_user

    return {
        "name": env(f"{prefix}_NAME", f"AD {code}"),
        "profile": env(f"{prefix}_PROFILE", "ad"),
        "server_uri": uri,
        "port": env_int(f"{prefix}_PORT", 0) or None,
        "use_ssl": use_ssl,
        "start_tls": env_bool(f"{prefix}_START_TLS", False),
        "tls_validate": env_bool(f"{prefix}_TLS_VALIDATE", True),
        "ca_certs_file": env(f"{prefix}_CA_CERTS_FILE", ""),
        "authentication": env(f"{prefix}_AUTHENTICATION", "SIMPLE"),
        "domain": domain,
        "bind_dn": bind_dn,
        "bind_password_env": f"{prefix}_BIND_PASSWORD",
        "base_dn": env(f"{prefix}_BASE_DN", ""),
        "search_ous": env_list(f"{prefix}_SEARCH_OUS", ""),
        "user_filter": env(f"{prefix}_USER_FILTER", ""),
        "include_disabled": env_bool(f"{prefix}_INCLUDE_DISABLED", True),
        "page_size": env_int(f"{prefix}_PAGE_SIZE", 500),
    }


def _onec_block(code: str) -> dict:
    up = code.upper()
    systems = {}
    for system in ONEC_SYSTEMS:
        url = env(f"ONEC_{up}_{system}_URL", "")
        if not url:
            continue
        systems[system.lower()] = {
            "url": url,
            "user": env(f"ONEC_{up}_{system}_USER", ""),
            "password_env": f"ONEC_{up}_{system}_PASSWORD",
            "inn": env(f"ONEC_{up}_{system}_INN", ""),
        }
    return systems


def build_company(code: str) -> dict:
    up = code.upper()
    name = env(f"COMPANY_{up}_NAME", code)
    return {
        "code": code,
        "name": name,
        "short_name": env(f"COMPANY_{up}_SHORT_NAME", name),
        "description": env(f"COMPANY_{up}_DESCRIPTION", ""),
        "is_active": env_bool(f"COMPANY_{up}_ENABLED", True),
        "is_default": env_bool(f"COMPANY_{up}_DEFAULT", code == COMPANY_DEFAULT_CODE),
        "org_id": env(f"COMPANY_{up}_ORG_ID", ""),
        "domain": env(f"LDAP_{up}_DOMAIN", ""),
        "country_id": env(f"COMPANY_{up}_COUNTRY_ID", "ru"),
        "country_name": env(f"COMPANY_{up}_COUNTRY_NAME", "Россия"),
        "ldap": _ldap_block(code, f"LDAP_{up}"),
        "integrations": _onec_block(code),
    }


COMPANIES = [build_company(code) for code in COMPANY_CODES]
