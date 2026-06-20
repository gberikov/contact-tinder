"""Structured logging with token/PII redaction (Constitution Principle V)."""
from __future__ import annotations

import logging
import re

# Patterns that must never reach logs: token-ish key/values and bearer tokens.
_REDACT_PATTERNS = [
    re.compile(r"(?i)(refresh_token|access_token|token_encryption_key|client_secret)"
               r"\s*[=:]\s*[^\s,&]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._\-]+"),  # Google access tokens
]

_REDACTED = "[REDACTED]"


def redact(message: str) -> str:
    out = message
    for pattern in _REDACT_PATTERNS:
        out = pattern.sub(_REDACTED, out)
    return out


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            record.args = tuple(
                redact(a) if isinstance(a, str) else a for a in record.args
            )
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactionFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
