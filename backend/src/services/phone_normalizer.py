"""Phone validation / human-readable normalization / type inference (feature 006, research D1).

Stateless wrapper over `phonenumbers` (libphonenumber). The stored value is the **human-readable
INTERNATIONAL** form (e.g. `+7 701 722 1502`), not raw E.164 — Google Contacts keeps the display
value as free text. Extensions are supported: an explicit marker (`ext`, `доб`, `#`, …) is parsed by
libphonenumber directly; a trailing internal/extension group with no marker (e.g.
`+7 727 262 32 73 3230`) is detected heuristically and re-parsed as an extension.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import phonenumbers
from phonenumbers import PhoneNumberFormat, PhoneNumberType


@dataclass(frozen=True)
class PhoneResult:
    valid: bool
    formatted: str | None  # human-readable INTERNATIONAL form (the value we store)
    e164: str | None       # canonical E.164 (for comparison/dedup)
    is_mobile: bool        # True only when confidently classified as a mobile line


# A trailing extension with no explicit marker: a separate group of 2–6 digits after the number.
_EXT_TAIL = re.compile(r"^(.*\d)[\s.,;/]+(\d{2,6})\s*$")


def _parse_valid(raw: str, region: str | None) -> phonenumbers.PhoneNumber | None:
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None
    return num if phonenumbers.is_valid_number(num) else None


def analyze(raw: str, region: str | None) -> PhoneResult:
    num = _parse_valid(raw, region)
    if num is None:
        # The base number is invalid as-is — maybe a trailing internal/extension number without an
        # "ext" marker. Retry treating the last digit group as an extension.
        match = _EXT_TAIL.match(raw.strip())
        if match:
            num = _parse_valid(f"{match.group(1)} ext {match.group(2)}", region)
    if num is None:
        return PhoneResult(valid=False, formatted=None, e164=None, is_mobile=False)

    formatted = phonenumbers.format_number(num, PhoneNumberFormat.INTERNATIONAL)
    e164 = phonenumbers.format_number(num, PhoneNumberFormat.E164)
    is_mobile = phonenumbers.number_type(num) == PhoneNumberType.MOBILE
    return PhoneResult(valid=True, formatted=formatted, e164=e164, is_mobile=is_mobile)
