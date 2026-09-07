from __future__ import annotations

import logging
import ssl
from typing import Iterator, Optional


from ldap3 import (
    ALL,
    ANONYMOUS,
    AUTO_BIND_NO_TLS,
    AUTO_BIND_TLS_BEFORE_BIND,
    NTLM,
    SIMPLE,
    SUBTREE,
    Connection,
    Server,
    Tls,
)
from ldap3.core.exceptions import LDAPException

from .config import LdapSettings

logger = logging.getLogger("ldapsync")

AUTH_METHODS = {"SIMPLE": SIMPLE, "NTLM": NTLM, "ANONYMOUS": ANONYMOUS}


class LdapSyncError(RuntimeError):
    pass


class LdapClient:

    def __init__(self, settings: LdapSettings):
        self.settings = settings
        self.connection: Optional[Connection] = None

    def _build_server(self) -> Server:
        s = self.settings
        host = s.host
        use_ssl = s.effective_use_ssl
        port = s.effective_port

        tls = None
        if use_ssl or s.start_tls:
            tls = Tls(
                validate=ssl.CERT_REQUIRED if s.tls_validate else ssl.CERT_NONE,
                ca_certs_file=s.ca_certs_file,
                version=ssl.PROTOCOL_TLS_CLIENT if s.tls_validate else ssl.PROTOCOL_TLS,
            )
        return Server(
            host,
            port=port,
            use_ssl=use_ssl,
            tls=tls,
            get_info=ALL,
            connect_timeout=s.timeout,
        )

    def connect(self) -> Connection:
        s = self.settings
        server = self._build_server()
        auth = AUTH_METHODS.get((s.authentication or "SIMPLE").upper(), SIMPLE)
        if not s.bind_dn:
            auth = ANONYMOUS

        auto_bind = AUTO_BIND_TLS_BEFORE_BIND if s.start_tls else AUTO_BIND_NO_TLS
        logger.info(
            "Подключение к каталогу %s:%s (ssl=%s, starttls=%s, авторизация=%s, учётка=%s)",
            server.host, server.port, server.ssl, s.start_tls, auth, s.bind_dn or "анонимно",
        )
        try:
            self.connection = Connection(
                server,
                user=s.bind_dn or None,
                password=s.bind_password or None,
                authentication=auth,
                auto_bind=auto_bind,
                receive_timeout=s.receive_timeout,
                raise_exceptions=True,
            )
        except LDAPException as exc:
            raise LdapSyncError(f"Не удалось подключиться к {server.host}:{server.port}: {exc}") from exc
        return self.connection

    def close(self) -> None:
        if self.connection is not None and self.connection.bound:
            self.connection.unbind()
        self.connection = None

    def __enter__(self) -> "LdapClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def iter_users(
        self,
        changed_since: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[dict]:
        if self.connection is None:
            self.connect()

        s = self.settings
        search_filter = s.build_filter(changed_since)
        attributes = self.supported_attributes(s.profile.attributes())
        yielded = 0

        for base in s.search_bases:
            logger.info("Поиск в каталоге: ветка=%s, фильтр=%s", base, search_filter)
            try:
                entries = self.connection.extend.standard.paged_search(
                    search_base=base,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=attributes,
                    paged_size=s.page_size,
                    generator=True,
                )
                for entry in entries:
                    if entry.get("type") != "searchResEntry":
                        continue
                    yield {
                        "dn": entry.get("dn", ""),
                        "attributes": dict(entry.get("attributes") or {}),
                    }
                    yielded += 1
                    if limit and yielded >= limit:
                        return
            except LDAPException as exc:
                raise LdapSyncError(f"Ошибка поиска в '{base}': {exc}") from exc

    def supported_attributes(self, requested: list) -> list:
        """Отсеивает атрибуты, которых нет в схеме сервера.

        extensionAttribute1..15 приходят в AD вместе со схемой Exchange - на
        каталоге без неё строгий сервер отвечает 'invalid attribute type' и
        роняет весь поиск.
        """
        schema = getattr(self.connection.server, "schema", None)
        known = getattr(schema, "attribute_types", None)
        if not known:
            return requested

        available = {str(name).lower() for name in known}
        supported = [name for name in requested if name.lower() in available]
        skipped = sorted(set(requested) - set(supported))
        if skipped:
            logger.warning("Каталог не знает атрибуты, пропускаю: %s", ", ".join(skipped))
        return supported or requested

    def server_info(self) -> dict:
        if self.connection is None:
            self.connect()
        info = self.connection.server.info
        try:
            bound_as = self.connection.extend.standard.who_am_i()
        except LDAPException:
            bound_as = None
        return {
            "сервер": self.connection.server.host,
            "порт": self.connection.server.port,
            "ssl": self.connection.server.ssl,
            "авторизован как": bound_as or self.settings.bind_dn or "анонимно",
            "ветки каталога": list(getattr(info, "naming_contexts", []) or []),
            "производитель": getattr(info, "vendor_name", None),
        }
