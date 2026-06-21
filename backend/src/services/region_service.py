"""Initial default-region detection from the client IP (feature 006, research D3).

Returns a country only when the client IP is PUBLIC and a local GeoLite2-Country DB is configured
(`geoip_db_path`). For the common self-hosted case (private/LAN client IP) or no DB, returns
`(None, "none")` and the frontend falls back to the browser locale/timezone. Uses a LOCAL DB only —
the operator's IP is never sent to a third-party geo service (Principle I). `_lookup_country` is a
seam so tests monkeypatch it without a DB.
"""
from __future__ import annotations

import ipaddress

from src.core.config import get_settings


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified
    )


def _lookup_country(ip: str) -> str | None:
    """ISO-3166 alpha-2 from a local GeoLite2-Country DB, or None when unavailable."""
    path = get_settings().geoip_db_path
    if not path:
        return None
    try:
        import geoip2.database  # imported lazily — optional dependency

        with geoip2.database.Reader(path) as reader:
            return reader.country(ip).country.iso_code
    except Exception:
        return None


def detect_region(client_ip: str | None) -> tuple[str | None, str]:
    """Return (region, source). region is non-null only for a public IP with a working GeoLite2 DB."""
    if not client_ip or not _is_public_ip(client_ip):
        return None, "none"
    region = _lookup_country(client_ip)
    if region:
        return region, "geoip"
    return None, "none"
