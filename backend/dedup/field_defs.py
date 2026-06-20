"""Zingg field definitions for contact matching (research D4).

The schema mirrors `contact_flatten.flatten_contact` output. `wcc_id` is identity-only
(DONT_USE); names/email/phone/org drive matching. Imported only inside the dedup container.
"""
from __future__ import annotations


def contact_field_definitions():  # pragma: no cover - requires the zingg package (container only)
    from zingg.client import FieldDefinition, MatchType

    return [
        FieldDefinition("wcc_id", "string", MatchType.DONT_USE),
        FieldDefinition("first_name", "string", MatchType.FUZZY),
        FieldDefinition("last_name", "string", MatchType.FUZZY),
        FieldDefinition("full_name", "string", MatchType.FUZZY),
        FieldDefinition("email", "string", MatchType.EMAIL),
        FieldDefinition("phone", "string", MatchType.FUZZY),
        FieldDefinition("organization", "string", MatchType.FUZZY),
    ]


INPUT_SCHEMA = (
    "wcc_id string, first_name string, last_name string, full_name string, "
    "email string, phone string, organization string"
)
