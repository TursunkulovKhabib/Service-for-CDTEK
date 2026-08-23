from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from django.utils.dateparse import parse_datetime

from .config import UAC_ACCOUNTDISABLE, LdapProfile

DN_NAMESPACE = uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")

MAX_LEN = {
    "sam_account_name": 128,
    "user_principal_name": 255,
    "display_name": 255,
    "first_name": 128,
    "last_name": 128,
    "middle_name": 128,
    "email": 254,
    "phone": 64,
    "mobile_phone": 64,
    "internal_phone": 32,
    "department": 255,
    "title": 255,
    "company": 255,
    "office": 255,
    "city": 128,
    "employee_id": 64,
    "manager_dn": 512,
    "distinguished_name": 512,
    "search_phone": 128,
    "full_name": 255,
}

SPECIAL_FIELDS = {"account_control", "when_created", "when_changed", "usn_changed"}


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


def to_generalized_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S.0Z")


def digits_only(*values) -> str:
    out = []
    for value in values:
        if value:
            out.append(re.sub(r"\D", "", str(value)))
    return " ".join(part for part in out if part)[: MAX_LEN["search_phone"]]


def build_full_name(payload: dict) -> str:
    if payload.get("last_name") and payload.get("first_name"):
        parts = [payload.get("last_name"), payload.get("first_name"), payload.get("middle_name")]
        full = " ".join(p for p in parts if p).strip()
    else:
        full = (payload.get("display_name") or payload.get("last_name") or "").strip()
    return (full or payload.get("sam_account_name") or "")[: MAX_LEN["full_name"]]


def build_payload(entry: dict, profile: LdapProfile) -> dict:
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

    if not payload.get("display_name"):
        payload["display_name"] = build_full_name(payload)[: MAX_LEN["display_name"]]
    payload["full_name"] = build_full_name(payload)
    payload["search_phone"] = digits_only(
        payload.get("phone"), payload.get("mobile_phone"), payload.get("internal_phone")
    )
    return payload
