"""Deterministic Latin→Cyrillic transliteration for contact NAME fields only (feature 003, D5).

Pure functions, no I/O — so contact PII never leaves the process (Principle I) and the mapping is
table-unit-testable. The result is always a *suggestion* the operator reviews (FR-015); names already
in Cyrillic or empty are returned unchanged (FR-017).
"""
from __future__ import annotations

# Longest-match-first digraphs (lowercase keys).
_DIGRAPHS: list[tuple[str, str]] = [
    ("shch", "щ"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("yo", "ё"),
    ("yu", "ю"),
    ("ya", "я"),
    ("ye", "е"),
]

_SINGLE: dict[str, str] = {
    "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "х",
    "i": "и", "j": "дж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п",
    "q": "к", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", "w": "в", "x": "кс",
    "y": "ы", "z": "з",
}

# Name subfields we transliterate (Person.names[*]).
NAME_FIELDS = ("displayName", "givenName", "familyName", "middleName")


def has_cyrillic(s: str | None) -> bool:
    return bool(s) and any("Ѐ" <= ch <= "ӿ" for ch in s)


def _apply_case(source: str, target: str) -> str:
    if source.isupper() and len(source) > 1:
        return target.upper()
    if source[:1].isupper():
        return target[:1].upper() + target[1:]
    return target


def transliterate(s: str | None) -> str:
    """Transliterate a Latin string to Cyrillic, preserving case and non-letters."""
    if not s:
        return s or ""
    low = s.lower()
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        matched = None
        for digraph, cyr in _DIGRAPHS:
            if low.startswith(digraph, i):
                matched = (cyr, len(digraph))
                break
        if matched is None:
            ch = low[i]
            matched = (_SINGLE.get(ch, s[i]), 1)
        cyr, length = matched
        src = s[i : i + length]
        out.append(_apply_case(src, cyr))
        i += length
    return "".join(out)


def _primary_name(payload: dict) -> dict | None:
    names = payload.get("names") or []
    if not names:
        return None
    return next((n for n in names if (n.get("metadata") or {}).get("primary")), names[0])


def suggest_for_payload(payload: dict) -> dict:
    """Suggest Cyrillic renderings of the primary name's Latin subfields.

    Returns {"hasSuggestion": bool, "fields": {subfield: suggested_value}}. Subfields that are empty
    or already Cyrillic are skipped (FR-017).
    """
    primary = _primary_name(payload)
    fields: dict[str, str] = {}
    if primary is not None:
        for key in NAME_FIELDS:
            val = primary.get(key)
            if val and not has_cyrillic(val):
                suggested = transliterate(val)
                if suggested and suggested != val:
                    fields[key] = suggested
    return {"hasSuggestion": bool(fields), "fields": fields}


def apply_to_payload(payload: dict, fields: dict[str, str]) -> dict:
    """Return a deep-ish copy of payload with the given Cyrillic name subfields applied to the
    primary name entry only (no other field is touched)."""
    new_payload = dict(payload)
    names = [dict(n) for n in (payload.get("names") or [])]
    if not names:
        names = [{}]
    idx = 0
    for j, n in enumerate(names):
        if (n.get("metadata") or {}).get("primary"):
            idx = j
            break
    for key, value in fields.items():
        names[idx][key] = value
    new_payload["names"] = names
    return new_payload
