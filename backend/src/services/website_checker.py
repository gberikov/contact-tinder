"""Website reachability + http→https + SSRF guard (feature 006, research D5/D6).

Stateless, synchronous (the worker fans out via threads under a semaphore). "Reachable" = the server
returns ANY HTTP response (2xx/3xx/4xx/5xx); only transport-level failures (DNS/connect/TLS/timeout)
are "unreachable" (FR-014). Redirects are followed MANUALLY so the SSRF guard runs on every hop: a
host resolving to a non-public address is never fetched and reported "unsafe" (FR-029). `_resolve_ips`
is a module-level seam so tests monkeypatch DNS without touching the network.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from src.core.config import get_settings

# probe outcomes
_REACHABLE = "reachable"
_UNREACHABLE = "unreachable"
_UNSAFE = "unsafe"


@dataclass(frozen=True)
class WebsiteResult:
    # "reachable" | "unreachable" | "unsafe"
    status: str
    # When reachable: the canonical URL to store — scheme added if it was missing, https preferred
    # when it works. The caller stages an edit only when this differs from the stored value.
    final_url: str | None = None


def _resolve_ips(host: str) -> list[str]:
    """Resolve a host to IP strings. IP literals skip DNS. Returns [] on resolution failure."""
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return []
    return [info[4][0] for info in infos]


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    # Blocks loopback, RFC1918 private, link-local (incl. 169.254.169.254 metadata), reserved,
    # unspecified, multicast, and IPv6 unique-local (fc00::/7 → is_private).
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_multicast
    )


def _is_safe_host(host: str | None) -> bool:
    if not host:
        return False
    ips = _resolve_ips(host)
    return bool(ips) and all(_is_public_ip(ip) for ip in ips)


def _normalize(url: str) -> str:
    parts = urlsplit(url.strip())
    if not parts.scheme:  # bare "example.com/..." → assume http
        parts = urlsplit("http://" + url.strip())
    return urlunsplit(parts)


def _swap_scheme(url: str, scheme: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(scheme=scheme))


def _probe(url: str, *, timeout: float, max_redirects: int) -> str:
    """Follow redirects manually, SSRF-guarding each hop. Returns one of the probe outcomes."""
    current = url
    with httpx.Client(follow_redirects=False, timeout=timeout) as client:
        for _ in range(max_redirects + 1):
            host = urlsplit(current).hostname
            if not _is_safe_host(host):
                return _UNSAFE
            try:
                resp = client.get(current)
            except httpx.HTTPError:
                return _UNREACHABLE
            if resp.is_redirect:
                location = resp.headers.get("location")
                if not location:
                    return _REACHABLE  # a redirect with no target still means the server answered
                current = urljoin(current, location)
                continue
            return _REACHABLE  # any non-redirect HTTP response = reachable
    return _REACHABLE  # too many redirects, but the server is clearly answering


def check(
    url: str, *, timeout: float | None = None, max_redirects: int | None = None
) -> WebsiteResult:
    settings = get_settings()
    timeout = settings.website_check_timeout_seconds if timeout is None else timeout
    max_redirects = (
        settings.website_check_max_redirects if max_redirects is None else max_redirects
    )

    # _normalize adds a default http:// scheme when the stored value has none (e.g. "www.site.kz").
    normalized = _normalize(url)
    parts = urlsplit(normalized)
    if not _is_safe_host(parts.hostname):
        return WebsiteResult(status="unsafe")

    # Always prefer https: probe the https variant first; the canonical URL we return adds the
    # scheme (if it was missing) and upgrades to https when https works — one mechanism covers both
    # "no scheme" and "http→https".
    https_url = _swap_scheme(normalized, "https")
    outcome = _probe(https_url, timeout=timeout, max_redirects=max_redirects)
    if outcome == _UNSAFE:
        return WebsiteResult(status="unsafe")
    if outcome == _REACHABLE:
        return WebsiteResult(status="reachable", final_url=https_url)

    # https failed. If the operator explicitly stored an https URL, never downgrade to http.
    if parts.scheme == "https":
        return WebsiteResult(status="unreachable")

    # Stored value was http or scheme-less → fall back to the http URL (still scheme-normalized).
    outcome = _probe(normalized, timeout=timeout, max_redirects=max_redirects)
    if outcome == _UNSAFE:
        return WebsiteResult(status="unsafe")
    if outcome == _REACHABLE:
        return WebsiteResult(status="reachable", final_url=normalized)
    return WebsiteResult(status="unreachable")
