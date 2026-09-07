from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

UAC_ACCOUNTDISABLE = 0x2

AD_ENABLED_ONLY = "(!(userAccountControl:1.2.840.113556.1.4.803:=2))"

TRANSFER_POSITION_TEXT = "Перевод сотрудника. Данные обновляются..."


@dataclass(frozen=True)
class LdapProfile:

    name: str
    attribute_map: dict
    guid_attribute: str
    changed_attribute: str
    base_filter: str
    enabled_only_filter: str = ""
    usn_attribute: str = ""
    operational_attributes: tuple = ()
    phone_groups: dict = field(default_factory=dict)
    flag_attributes: dict = field(default_factory=dict)
    date_attributes: dict = field(default_factory=dict)

    def attributes(self) -> list:
        attrs = {self.guid_attribute, self.changed_attribute, "distinguishedName"}
        attrs.update(a for a in self.attribute_map.values() if a)
        for group in self.phone_groups.values():
            attrs.update(group)
        attrs.update(self.flag_attributes.values())
        attrs.update(self.date_attributes.values())
        if self.usn_attribute:
            attrs.add(self.usn_attribute)
        attrs.update(self.operational_attributes)
        return sorted(attrs)


AD_PROFILE = LdapProfile(
    name="ad",
    attribute_map={
        "sam_account_name": "sAMAccountName",
        "user_principal_name": "userPrincipalName",
        "display_name": "displayName",
        "full_name": "name",
        "first_name": "givenName",
        "last_name": "sn",
        "middle_name": "middleName",
        "region": "l",
        "office": "physicalDeliveryOfficeName",
        "department_code": "extensionAttribute4",
        "department": "department",
        "title": "title",
        "email": "mail",
        "zup_uid": "employeeNumber",
        "manager_dn": "manager",
        "project_name": "extensionAttribute2",
        "company_name": "company",
        "description": "description",
        "account_control": "userAccountControl",
        "when_created": "whenCreated",
        "when_changed": "whenChanged",
        "usn_changed": "uSNChanged",
        "photo": "thumbnailPhoto",
    },
    phone_groups={
        "phone_mobile": ("homePhone",),
        "phone_mobile_work": ("telephoneNumber", "mobile", "facsimileTelephoneNumber", "pager"),
        "phone_internal": ("otherTelephone", "ipPhone"),
    },
    flag_attributes={
        "personal_data_consent": "extensionAttribute7",
        "is_transferred": "extensionAttribute6",
    },
    date_attributes={"birthday": "extensionAttribute1"},
    guid_attribute="objectGUID",
    changed_attribute="whenChanged",
    usn_attribute="uSNChanged",
    base_filter="(&(objectCategory=person)(objectClass=user)(sAMAccountName=*))",
    enabled_only_filter=AD_ENABLED_ONLY,
)

OPENLDAP_PROFILE = LdapProfile(
    name="openldap",
    attribute_map={
        "sam_account_name": "uid",
        "display_name": "cn",
        "last_name": "sn",
        "email": "mail",
        "department": "ou",
        "title": "title",
        "description": "description",
        "when_changed": "modifyTimestamp",
    },
    phone_groups={"phone_mobile_work": ("telephoneNumber",)},
    guid_attribute="entryUUID",
    changed_attribute="modifyTimestamp",
    base_filter="(objectClass=inetOrgPerson)",
    operational_attributes=("entryUUID", "modifyTimestamp", "createTimestamp"),
)

PROFILES = {p.name: p for p in (AD_PROFILE, OPENLDAP_PROFILE)}


def get_profile(name: str) -> LdapProfile:
    try:
        return PROFILES[(name or "ad").lower()]
    except KeyError:
        raise ValueError(
            f"Неизвестный профиль LDAP '{name}'. Доступны: {', '.join(sorted(PROFILES))}"
        ) from None


@dataclass
class LdapSettings:

    server_uri: str
    base_dn: str
    profile: LdapProfile
    port: Optional[int] = None
    use_ssl: bool = True
    start_tls: bool = False
    tls_validate: bool = True
    ca_certs_file: Optional[str] = None
    bind_dn: str = ""
    bind_password: str = ""
    authentication: str = "SIMPLE"
    search_ous: list = field(default_factory=list)
    user_filter: str = ""
    include_disabled: bool = False
    page_size: int = 500
    timeout: int = 30
    receive_timeout: int = 60
    deactivate_missing: bool = True
    min_entries_for_deactivation: int = 1

    @property
    def _parsed(self):
        from urllib.parse import urlparse

        uri = self.server_uri if "://" in self.server_uri else f"ldap://{self.server_uri}"
        return urlparse(uri)

    @property
    def host(self) -> str:
        return self._parsed.hostname or self.server_uri

    @property
    def effective_use_ssl(self) -> bool:
        return self._parsed.scheme == "ldaps" or self.use_ssl

    @property
    def effective_port(self) -> int:
        return self._parsed.port or self.port or (636 if self.effective_use_ssl else 389)

    @property
    def search_bases(self) -> list:
        return list(self.search_ous) if self.search_ous else [self.base_dn]

    def build_filter(self, changed_since: Optional[str] = None) -> str:
        parts = [self.user_filter or self.profile.base_filter]
        if not self.include_disabled and self.profile.enabled_only_filter:
            parts.append(self.profile.enabled_only_filter)
        if changed_since:
            parts.append(f"({self.profile.changed_attribute}>={changed_since})")
        if len(parts) == 1:
            return parts[0]
        return "(&" + "".join(parts) + ")"


def load_settings(overrides: Optional[dict] = None) -> LdapSettings:
    from django.conf import settings as django_settings

    raw = dict(django_settings.LDAP)
    raw.update({k: v for k, v in (overrides or {}).items() if v is not None})

    return LdapSettings(
        server_uri=raw["SERVER_URI"],
        base_dn=raw["BASE_DN"],
        profile=get_profile(raw.get("PROFILE", "ad")),
        port=raw.get("PORT"),
        use_ssl=bool(raw.get("USE_SSL", True)),
        start_tls=bool(raw.get("START_TLS", False)),
        tls_validate=bool(raw.get("TLS_VALIDATE", True)),
        ca_certs_file=raw.get("CA_CERTS_FILE"),
        bind_dn=raw.get("BIND_DN", ""),
        bind_password=raw.get("BIND_PASSWORD", ""),
        authentication=raw.get("AUTHENTICATION", "SIMPLE"),
        search_ous=list(raw.get("SEARCH_OUS") or []),
        user_filter=raw.get("USER_FILTER", ""),
        include_disabled=bool(raw.get("INCLUDE_DISABLED", False)),
        page_size=int(raw.get("PAGE_SIZE", 500)),
        timeout=int(raw.get("TIMEOUT", 30)),
        receive_timeout=int(raw.get("RECEIVE_TIMEOUT", 60)),
        deactivate_missing=bool(raw.get("DEACTIVATE_MISSING", True)),
        min_entries_for_deactivation=int(raw.get("MIN_ENTRIES_FOR_DEACTIVATION", 1)),
    )
