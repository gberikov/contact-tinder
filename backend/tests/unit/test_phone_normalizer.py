"""T008 — phone parsing/validity/E.164/type (feature 006, FR-008/009/010)."""
from __future__ import annotations

from src.services import phone_normalizer as pn


def test_valid_national_kz_mobile_normalizes_to_e164_and_is_mobile():
    r = pn.analyze("+7 (701) 722-15-02", "KZ")
    assert r.valid is True
    assert r.e164 == "+77017221502"
    assert r.is_mobile is True


def test_national_format_without_plus_uses_region():
    r = pn.analyze("8 701 722 1502", "KZ")
    assert r.valid is True
    assert r.e164 == "+77017221502"


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
