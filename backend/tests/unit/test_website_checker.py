"""T010 — website reachability + http→https + SSRF guard (feature 006, FR-014/015/016/029).

httpx is mocked with respx; DNS resolution is monkeypatched so no real network is touched.
"""
from __future__ import annotations

import ipaddress

import httpx
import pytest
import respx

from src.services import website_checker as wc


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    # Resolve every named host to a public IP; IP literals resolve to themselves (so loopback /
    # metadata literals still trip the SSRF guard). Individual tests may override.
    def _resolve(host):
        try:
            ipaddress.ip_address(host)
            return [host]
        except ValueError:
            return ["93.184.216.34"]

    monkeypatch.setattr(wc, "_resolve_ips", _resolve)


@respx.mock
def test_http_with_working_https_is_upgraded():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200))
    r = wc.check("http://example.com/")
    assert r.status == "upgrade_https"
    assert r.final_url == "https://example.com/"


@respx.mock
def test_https_reachable_is_ok_no_change():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200))
    r = wc.check("https://example.com/")
    assert r.status == "ok"
    assert r.final_url is None


@respx.mock
def test_blocking_403_still_counts_as_reachable():
    # https answers 403 (antibot) → reachable; the http→https upgrade still applies.
    respx.get("https://example.com/").mock(return_value=httpx.Response(403))
    r = wc.check("http://example.com/")
    assert r.status == "upgrade_https"


@respx.mock
def test_timeout_is_unreachable():
    respx.get("https://example.com/").mock(side_effect=httpx.ConnectTimeout("boom"))
    respx.get("http://example.com/").mock(side_effect=httpx.ConnectTimeout("boom"))
    r = wc.check("http://example.com/")
    assert r.status == "unreachable"


@respx.mock
def test_connection_error_is_unreachable():
    respx.get("https://dead.example/").mock(side_effect=httpx.ConnectError("no"))
    respx.get("http://dead.example/").mock(side_effect=httpx.ConnectError("no"))
    r = wc.check("http://dead.example/")
    assert r.status == "unreachable"


def test_loopback_literal_is_unsafe_without_any_request():
    # 127.0.0.1 is an IP literal → no DNS, no httpx call; SSRF guard fires.
    r = wc.check("http://127.0.0.1/")
    assert r.status == "unsafe"
    assert r.final_url is None


def test_private_host_is_unsafe(monkeypatch):
    monkeypatch.setattr(wc, "_resolve_ips", lambda host: ["10.0.0.5"])
    r = wc.check("http://intranet.example/")
    assert r.status == "unsafe"


def test_cloud_metadata_is_unsafe():
    r = wc.check("http://169.254.169.254/latest/meta-data/")
    assert r.status == "unsafe"


@respx.mock
def test_redirect_to_private_is_unsafe(monkeypatch):
    # First hop public, redirect Location points at a private host → guard fires on the hop.
    calls = {"n": 0}

    def _resolve(host):
        calls["n"] += 1
        return ["93.184.216.34"] if host == "example.com" else ["10.1.2.3"]

    monkeypatch.setattr(wc, "_resolve_ips", _resolve)
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(302, headers={"location": "https://intranet.example/"})
    )
    r = wc.check("https://example.com/")
    assert r.status == "unsafe"
