"""Outbound alert webhook URL validation (SSRF guardrails).

Project and global alert settings accept user-controlled URLs. Before dispatch we
enforce scheme/host rules and require resolved addresses to be public unicast
(except documented development localhost exceptions).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class AlertWebhookUrlError(ValueError):
    """Raised when an alert webhook URL is not allowed."""


def _ips_for_host(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    host = host.strip().lower()
    if not host:
        raise AlertWebhookUrlError("webhook URL is missing a host")
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AlertWebhookUrlError(f"webhook host {host!r} does not resolve ({exc})") from exc
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    seen: set[str] = set()
    for _fam, _type, _proto, _canon, sockaddr in infos:
        if not sockaddr:
            continue
        ip_str = str(sockaddr[0])
        if ip_str in seen:
            continue
        seen.add(ip_str)
        ips.append(ipaddress.ip_address(ip_str))
    if not ips:
        raise AlertWebhookUrlError(f"webhook host {host!r} resolved to no IP addresses")
    return ips


def _ip_allowed_for_scheme(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    lumonox_env: str,
    scheme: str,
    host: str,
) -> bool:
    env = (lumonox_env or "development").strip().lower()
    if scheme == "http":
        if env != "development":
            return False
        if host not in {"localhost", "127.0.0.1"}:
            return False
        return ip.is_loopback

    if scheme != "https":
        return False

    if ip.is_global:
        return True
    return bool(env == "development" and ip.is_loopback)


def validate_alert_outbound_webhook_url(url: str, *, lumonox_env: str) -> None:
    """Raise ``AlertWebhookUrlError`` when *url* must not be used for outbound HTTP."""
    raw = (url or "").strip()
    if not raw:
        raise AlertWebhookUrlError("webhook URL is empty")
    parts = urlsplit(raw)
    scheme = (parts.scheme or "").strip().lower()
    if scheme not in {"http", "https"}:
        raise AlertWebhookUrlError("webhook URL must use http or https")
    if parts.username or parts.password:
        raise AlertWebhookUrlError("webhook URL must not contain embedded credentials")
    host = (parts.hostname or "").strip().lower()
    if not host:
        raise AlertWebhookUrlError("webhook URL is missing a host")

    env = (lumonox_env or "development").strip().lower()
    if scheme == "http" and env != "development":
        raise AlertWebhookUrlError("http webhooks are only allowed in development")

    if scheme == "http" and host not in {"localhost", "127.0.0.1"}:
        raise AlertWebhookUrlError(
            "http webhooks are only allowed for localhost or 127.0.0.1 in development"
        )

    for ip in _ips_for_host(host):
        if not _ip_allowed_for_scheme(ip, lumonox_env=lumonox_env, scheme=scheme, host=host):
            raise AlertWebhookUrlError(
                f"webhook host {host!r} resolves to a disallowed address ({ip}) for scheme {scheme}"
            )


__all__ = ["AlertWebhookUrlError", "validate_alert_outbound_webhook_url"]
