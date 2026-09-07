from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone

from django.utils.dateparse import parse_datetime

from .config import TRANSFER_POSITION_TEXT, UAC_ACCOUNTDISABLE, LdapProfile

DN_NAMESPACE = uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")

PHONE_SEPARATOR = "; "

BIRTHDAY_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%y")

MAX_LEN = {
    "sam_account_name": 128,
    "user_principal_name": 255,
    "display_name": 255,
    "first_name": 128,
    "last_name": 128,
    "middle_name": 128,
    "email": 254,
    "phone_mobile": 128,
    "phone_mobile_work": 255,
    "phone_internal": 128,
    "region": 255,
    "department": 255,
    "department_code": 64,
    "title": 255,
    "company_name": 255,
    "office": 255,
    "city": 128,
    "zup_uid": 64,
    "project_name": 255,
    "manager_dn": 512,
    "distinguished_name": 512,
    "search_phone": 128,
    "full_name": 255,
    "description": 255,
}

SPECIAL_FIELDS = {"account_control", "when_created", "when_changed", "usn_changed", "photo"}


def first(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def clean_str(value, max_length: int = 255) -> str:
    value = first(value)
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return str(value).strip()[:max_length]


def guid_to_uuid(raw, dn: str) -> uuid.UUID:
    raw = first(raw)
    if isinstance(raw, bytes) and len(raw) == 16:
        return uuid.UUID(bytes_le=raw)
    if raw:
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        try:
            return uuid.UUID(text.strip("{}"))
        except ValueError:
            pass
    return uuid.uuid5(DN_NAMESPACE, (dn or "").lower())


def parse_ldap_datetime(value):
    value = first(value)
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    text = str(value).strip()
    m = re.match(r"^(\d{14})(?:\.\d+)?Z?$", text)
    if m:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    parsed = parse_datetime(text)
    if parsed and not parsed.tzinfo:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_birthday(value, formats=None):
    """extensionAttribute1: дата рождения приходит в разных форматах.

    Старый сервис брал только строки ровно из 10 символов ("dd.MM.yyyy") и
    терял остальные - в частности записи со временем в конце.
    """
    text = clean_str(value, 64)
    if not text:
        return None

    head = text.replace("T", " ").split(" ")[0]
    for pattern in (formats or BIRTHDAY_FORMATS):
        try:
            return datetime.strptime(head, pattern).date()
        except ValueError:
            continue

    generalized = re.match(r"^(\d{8})", head)
    if generalized:
        try:
            return datetime.strptime(generalized.group(1), "%Y%m%d").date()
        except ValueError:
            pass
    return None


def to_generalized_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S.0Z")


def join_phones(attrs: dict, attribute_names) -> str:
    """Склейка телефонов через '; ' - как corpphone/internalphone в LDAPService."""
    parts = []
    for name in attribute_names:
        value = clean_str(attrs.get(name), 64)
        if value:
            parts.append(value)
    return PHONE_SEPARATOR.join(parts)


def digits_only(*values) -> str:
    out = []
    for value in values:
        if value:
            for chunk in str(value).split(PHONE_SEPARATOR.strip()):
                digits = re.sub(r"\D", "", chunk)
                if digits:
                    out.append(digits)
    return " ".join(out)[: MAX_LEN["search_phone"]]


def build_full_name(payload: dict) -> str:
    """ФИО: 'Фамилия Имя Отчество'; если ФИО не собирается - берём name/displayName."""
    parts = [payload.get("last_name"), payload.get("first_name"), payload.get("middle_name")]
    full = " ".join(p for p in parts if p).strip()
    if not full:
        full = (payload.get("full_name") or payload.get("display_name") or "").strip()
    return (full or payload.get("sam_account_name") or "")[: MAX_LEN["full_name"]]


def flag_is_on(attrs: dict, attribute: str) -> bool:
    return clean_str(attrs.get(attribute), 16) == "1"


def build_payload(entry: dict, profile: LdapProfile, birthday_formats=None) -> dict:
    attrs = entry.get("attributes") or {}
    dn = entry.get("dn") or clean_str(attrs.get("distinguishedName"), MAX_LEN["distinguished_name"])

    payload = {
        "object_guid": guid_to_uuid(attrs.get(profile.guid_attribute), dn),
        "distinguished_name": dn[: MAX_LEN["distinguished_name"]],
    }

    for field_name, ldap_attr in profile.attribute_map.items():
        if field_name in SPECIAL_FIELDS:
            continue
        payload[field_name] = clean_str(attrs.get(ldap_attr), MAX_LEN.get(field_name, 255))

    for field_name, attribute_names in profile.phone_groups.items():
        payload[field_name] = join_phones(attrs, attribute_names)[: MAX_LEN.get(field_name, 255)]

    formats = birthday_formats or profile.birthday_formats or None
    for field_name, attribute in profile.date_attributes.items():
        payload[field_name] = parse_birthday(attrs.get(attribute), formats)

    payload["personal_data_consent"] = flag_is_on(
        attrs, profile.flag_attributes.get("personal_data_consent", "")
    )
    if flag_is_on(attrs, profile.flag_attributes.get("is_transferred", "")):
        payload["title"] = TRANSFER_POSITION_TEXT

    uac = first(attrs.get(profile.attribute_map.get("account_control", "")))
    try:
        uac_int = int(uac) if uac not in (None, "") else None
    except (TypeError, ValueError):
        uac_int = None
    payload["account_control"] = uac_int
    payload["ad_enabled"] = True if uac_int is None else not bool(uac_int & UAC_ACCOUNTDISABLE)

    payload["when_created"] = parse_ldap_datetime(attrs.get("whenCreated") or attrs.get("createTimestamp"))
    payload["when_changed"] = parse_ldap_datetime(attrs.get(profile.changed_attribute))

    usn = first(attrs.get(profile.usn_attribute)) if profile.usn_attribute else None
    try:
        payload["usn_changed"] = int(usn) if usn not in (None, "") else None
    except (TypeError, ValueError):
        payload["usn_changed"] = None

    photo = first(attrs.get(profile.attribute_map.get("photo", "")))
    payload["photo"] = photo if isinstance(photo, bytes) else None

    payload["full_name"] = build_full_name(payload)
    if not payload.get("display_name"):
        payload["display_name"] = payload["full_name"][: MAX_LEN["display_name"]]
    payload["search_phone"] = digits_only(
        payload.get("phone_mobile"), payload.get("phone_mobile_work"), payload.get("phone_internal")
    )
    return payload
