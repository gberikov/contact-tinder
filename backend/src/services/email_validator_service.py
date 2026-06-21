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
    detail: str | None = None  # specific human-readable reason


def domain_status(domain: str) -> str:
    """Classify a domain's mail-receiving ability: 'ok' | 'no_domain' | 'no_mx'."""
    try:
        answers = dns.resolver.resolve(domain, "MX")
        if len(answers) > 0:
            return "ok"
        return "no_mx"
    except dns.resolver.NXDOMAIN:
        return "no_domain"  # the domain itself does not exist
    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        # No MX record. RFC 5321 allows an implicit A/AAAA fallback as the mail exchanger.
        try:
            dns.resolver.resolve(domain, "A")
            return "ok"
        except dns.resolver.NXDOMAIN:
            return "no_domain"
        except Exception:
            return "no_mx"
    except Exception:
        # DNS timeout / lookup failure — cannot confirm; treat as no MX.
        return "no_mx"


def analyze(raw: str) -> EmailResult:
    try:
        info = validate_email(raw, check_deliverability=False)
    except EmailNotValidError as exc:
        return EmailResult(
            valid_syntax=False, has_mx=False, normalized=None, issue="invalid_email",
            detail=str(exc) or "Invalid email format",
        )

    status = domain_status(info.domain)
    if status == "no_domain":
        return EmailResult(
            valid_syntax=True, has_mx=False, normalized=info.normalized, issue="dead_email_domain",
            detail=f"Domain '{info.domain}' does not exist",
        )
    if status == "no_mx":
        return EmailResult(
            valid_syntax=True, has_mx=False, normalized=info.normalized, issue="dead_email_domain",
            detail=f"Domain '{info.domain}' has no valid mail exchanger (MX) record",
        )
    return EmailResult(valid_syntax=True, has_mx=True, normalized=info.normalized, issue=None)
