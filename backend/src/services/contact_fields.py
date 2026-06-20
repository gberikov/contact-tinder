"""Extract display/search columns from a raw Google People `Person` payload.

The raw payload remains the source of truth (data-model fidelity rule, FR-004); these are
convenience columns only.
"""
from __future__ import annotations


def _primary(items: list[dict] | None, key: str) -> str | None:
    if not items:
        return None
    for item in items:
        if (item.get("metadata") or {}).get("primary"):
            return item.get(key)
    return items[0].get(key)


def display_name(person: dict) -> str | None:
    names = person.get("names")
    if names:
        primary = _primary(names, "displayName")
        if primary:
            return primary
    return _primary(person.get("emailAddresses"), "value")


def primary_email(person: dict) -> str | None:
    return _primary(person.get("emailAddresses"), "value")


def primary_phone(person: dict) -> str | None:
    return _primary(person.get("phoneNumbers"), "value")
