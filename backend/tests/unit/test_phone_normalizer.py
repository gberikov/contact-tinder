"""T008 — phone parsing/validity/E.164/type (feature 006, FR-008/009/010)."""
from __future__ import annotations

from src.services import phone_normalizer as pn


def test_valid_national_kz_mobile_normalizes_to_human_readable_and_is_mobile():
    r = pn.analyze("+7 (701) 722-15-02", "KZ")
    assert r.valid is True
    assert r.formatted == "+7 701 722 1502"  # human-readable INTERNATIONAL form
    assert r.e164 == "+77017221502"
    assert r.is_mobile is True


def test_national_format_without_plus_uses_region():
    r = pn.analyze("8 701 722 1502", "KZ")
    assert r.valid is True
    assert r.formatted == "+7 701 722 1502"


def test_trailing_internal_number_parsed_as_extension():
    # "+7 727 262 32 73 3230" — the 3230 has no "ext" marker but is an internal/extension number.
    r = pn.analyze("+7 727 262 32 73 3230", "KZ")
    assert r.valid is True
    assert "ext. 3230" in (r.formatted or "")


def test_explicit_extension_marker_is_preserved():
    r = pn.analyze("+7 727 262 32 73 ext 3230", "KZ")
    assert r.valid is True
    assert "ext. 3230" in (r.formatted or "")


def test_e164_input_ignores_region():
    # A US number parses by its own country code even with a KZ default region.
    r = pn.analyze("+1 212 555 0123", "KZ")
    assert r.valid is True
    assert r.e164 == "+12125550123"


def test_unparseable_is_invalid():
    r = pn.analyze("+7 70", "KZ")
    assert r.valid is False
    assert r.e164 is None
    assert r.is_mobile is False


def test_garbage_is_invalid():
    r = pn.analyze("not-a-number", "KZ")
    assert r.valid is False


def test_fixed_line_is_valid_but_not_confidently_mobile():
    # Almaty landline (+7 727 ...) is FIXED_LINE → valid, but unclear type.
    r = pn.analyze("+7 727 250 1234", "KZ")
    assert r.valid is True
    assert r.is_mobile is False
