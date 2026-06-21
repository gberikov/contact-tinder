"""Email syntax + MX validation (feature 006, research D4).

Two levels, both required by the spec: syntax (offline, via `email-validator`) and whether the
domain can receive mail at all (one DNS MX lookup, via `dnspython`). No SMTP probing (FR-013) — we
never confirm a specific mailbox. `domain_has_mx` is a module-level seam so tests monkeypatch it
without touching the network.
"""
from __future__ import annotations

from dataclasses import dataclass

import dns.resolver
from email_validator import EmailNotValidError, validate_email


@dataclass(frozen=True)
class EmailResult:
    valid_syntax: bool
    has_mx: bool
    normalized: str | None
    issue: str | None  # None (ok) | "invalid_email" | "dead_email_domain"


def domain_has_mx(domain: str) -> bool:
    """True if the domain publishes at least one MX record (or an implicit A/AAAA fallback)."""
    try:
        answers = dns.resolver.resolve(domain, "MX")
        return len(answers) > 0
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        # No MX. RFC 5321 allows falling back to an A/AAAA record as an implicit MX.
        try:
            dns.resolver.resolve(domain, "A")
            return True
        except Exception:
            return False
    except Exception:
        # DNS timeout / lookup failure — treat as "cannot confirm", i.e. no MX.
        return False


def analyze(raw: str) -> EmailResult:
    try:
        info = validate_email(raw, check_deliverability=False)
    except EmailNotValidError:
        return EmailResult(valid_syntax=False, has_mx=False, normalized=None, issue="invalid_email")

    domain = info.domain
    if not domain_has_mx(domain):
        return EmailResult(
            valid_syntax=True, has_mx=False, normalized=info.normalized, issue="dead_email_domain"
        )
    return EmailResult(valid_syntax=True, has_mx=True, normalized=info.normalized, issue=None)
