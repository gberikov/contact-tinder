"""Phone validation / E.164 normalization / type inference (feature 006, research D1).

Stateless wrapper over `phonenumbers` (libphonenumber). Parsing of national-format numbers uses a
caller-supplied region; `+E.164` numbers parse by their own country code regardless. Only a
*confidently mobile* number auto-sets the `mobile` type — FIXED_LINE and the ambiguous
FIXED_LINE_OR_MOBILE are reported as not-mobile so the caller queues them for a human (FR-010).
"""
from __future__ import annotations

from dataclasses import dataclass

import phonenumbers
from phonenumbers import PhoneNumberType


@dataclass(frozen=True)
class PhoneResult:
    valid: bool
    e164: str | None  # normalized E.164 when valid, else None
    is_mobile: bool   # True only when confidently classified as a mobile line


def analyze(raw: str, region: str | None) -> PhoneResult:
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return PhoneResult(valid=False, e164=None, is_mobile=False)

    if not phonenumbers.is_valid_number(num):
        return PhoneResult(valid=False, e164=None, is_mobile=False)

    e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    is_mobile = phonenumbers.number_type(num) == PhoneNumberType.MOBILE
    return PhoneResult(valid=True, e164=e164, is_mobile=is_mobile)
