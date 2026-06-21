"""T011 — initial region detection from a public client IP (feature 006, FR-028, research D3)."""
from __future__ import annotations

from src.services import region_service as rs


def test_public_ip_with_geoip_returns_region(monkeypatch):
    monkeypatch.setattr(rs, "_lookup_country", lambda ip: "KZ")
    region, source = rs.detect_region("8.8.8.8")
    assert region == "KZ"
    assert source == "geoip"


def test_private_ip_returns_none(monkeypatch):
    # geoip would resolve, but a private client IP (local deploy) must not be geolocated.
    monkeypatch.setattr(rs, "_lookup_country", lambda ip: "ZZ")
    region, source = rs.detect_region("192.168.1.10")
    assert region is None
    assert source == "none"


def test_loopback_returns_none():
    region, source = rs.detect_region("127.0.0.1")
    assert region is None
    assert source == "none"


def test_none_ip_returns_none():
    region, source = rs.detect_region(None)
    assert region is None
    assert source == "none"


def test_public_ip_without_geoip_db_returns_none(monkeypatch):
    monkeypatch.setattr(rs, "_lookup_country", lambda ip: None)  # DB not configured
    region, source = rs.detect_region("8.8.8.8")
    assert region is None
    assert source == "none"
