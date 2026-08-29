from django.conf import settings

from employees.repositories import CompanyRepository, LdapServerRepository

from .base import BaseService


class CompanyService(BaseService):
    repository_class = CompanyRepository

    def __init__(self, repository=None, ldap_repository=None):
        super().__init__(repository)
        self.ldap_repository = ldap_repository or LdapServerRepository()

    def get_by_code(self, code: str):
        return self.repository.get_by_code(code)

    def default(self):
        return self.repository.default()

    def load_from_settings(self, definitions=None) -> dict:
        definitions = definitions if definitions is not None else settings.COMPANIES
        stats = {"companies": 0, "servers": 0}

        for item in definitions:
            company, _ = self.repository.update_or_create(
                item["code"],
                name=item.get("name", item["code"]),
                short_name=item.get("short_name", ""),
                description=item.get("description", ""),
                is_default=item.get("is_default", False),
                is_active=item.get("is_active", True),
            )
            stats["companies"] += 1

            ldap = item.get("ldap")
            if not ldap:
                continue
            self.ldap_repository.update_or_create(
                ldap.get("name", f"AD {company.code}"),
                company=company,
                profile=ldap.get("profile", "ad"),
                server_uri=ldap.get("server_uri", ""),
                port=ldap.get("port"),
                use_ssl=ldap.get("use_ssl", True),
                start_tls=ldap.get("start_tls", False),
                tls_validate=ldap.get("tls_validate", True),
                ca_certs_file=ldap.get("ca_certs_file", ""),
                authentication=ldap.get("authentication", "SIMPLE"),
                bind_dn=ldap.get("bind_dn", ""),
                bind_password_env=ldap.get("bind_password_env", ""),
                base_dn=ldap.get("base_dn", ""),
                search_ous=ldap.get("search_ous", []),
                user_filter=ldap.get("user_filter", ""),
                is_active=item.get("is_active", True),
            )
            stats["servers"] += 1

        return stats
