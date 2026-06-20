"""Flatten a raw Google `Person` payload into the typed columns Zingg matches on (research D4).

The raw payload remains the source of truth; these are derived match/display fields only. Reuses
`contact_fields` for the primary name/email/phone extraction.
"""
from __future__ import annotations

import uuid

from src.services import contact_fields


def _first_last(person: dict) -> tuple[str | None, str | None]:
    names = person.get("names") or []
    if not names:
        return None, None
    primary = next((n for n in names if (n.get("metadata") or {}).get("primary")), names[0])
    return primary.get("givenName"), primary.get("familyName")


def organization(person: dict) -> str | None:
    orgs = person.get("organizations") or []
    if not orgs:
        return None
    primary = next((o for o in orgs if (o.get("metadata") or {}).get("primary")), orgs[0])
    return primary.get("name") or primary.get("title")


def flatten_contact(wcc_id: uuid.UUID, payload: dict) -> dict:
    """Project one working-copy contact into Zingg input columns."""
    first, last = _first_last(payload)
    return {
        "wcc_id": str(wcc_id),
        "first_name": first,
        "last_name": last,
        "full_name": contact_fields.display_name(payload),
        "email": contact_fields.primary_email(payload),
        "phone": contact_fields.primary_phone(payload),
        "organization": organization(payload),
    }
