"""Unit: Latin→Cyrillic transliteration of name fields (US2 / FR-014/017, D5)."""
from __future__ import annotations

import pytest

from src.services import transliteration as t


@pytest.mark.parametrize(
    "latin,cyrillic",
    [
        ("Boris", "Борис"),
        ("Anna", "Анна"),
        ("Sasha", "Саша"),  # 'sh' digraph
        ("Yuri", "Юри"),    # 'yu' digraph
        ("Zhanna", "Жанна"),  # 'zh' digraph
    ],
)
def test_transliterate_basic(latin, cyrillic):
    assert t.transliterate(latin) == cyrillic


def test_already_cyrillic_passthrough():
    assert t.has_cyrillic("Борис") is True
    assert t.transliterate("Борис") == "Борис"


def test_empty_is_noop():
    assert t.transliterate("") == ""
    assert t.has_cyrillic("") is False


def test_suggest_for_payload_name_fields_only():
    payload = {
        "names": [{"givenName": "Boris", "familyName": "Petrov",
                   "displayName": "Boris Petrov", "metadata": {"primary": True}}],
        "phoneNumbers": [{"value": "+1"}],
    }
    out = t.suggest_for_payload(payload)
    assert out["hasSuggestion"] is True
    assert out["fields"]["givenName"] == "Борис"
    assert out["fields"]["familyName"] == "Петров"
    assert "phoneNumbers" not in out["fields"]


def test_suggest_skips_cyrillic_name():
    payload = {"names": [{"givenName": "Борис", "metadata": {"primary": True}}]}
    assert t.suggest_for_payload(payload)["hasSuggestion"] is False


def test_apply_to_payload_changes_only_names():
    payload = {
        "names": [{"givenName": "Boris", "metadata": {"primary": True}}],
        "phoneNumbers": [{"value": "+1"}],
    }
    new = t.apply_to_payload(payload, {"givenName": "Борис"})
    assert new["names"][0]["givenName"] == "Борис"
    assert new["phoneNumbers"] == [{"value": "+1"}]  # untouched
    assert payload["names"][0]["givenName"] == "Boris"  # original not mutated
