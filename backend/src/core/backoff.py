"""Exponential backoff + jitter with a retry ceiling (research D9, A1)."""
from __future__ import annotations

import random


def next_delay(
    attempt: int,
    *,
    base: float = 0.5,
    cap: float = 60.0,
    retry_after: float | None = None,
    jitter: bool = True,
) -> float:
    """Delay (seconds) before the given retry `attempt` (1-based).

    Honors an explicit ``retry_after`` (e.g. from a 429 ``Retry-After`` header) when present,
    otherwise exponential backoff capped at ``cap``. Jitter is full-jitter in [0, delay].
    """
    if retry_after is not None:
        base_delay = min(float(retry_after), cap)
    else:
        base_delay = min(cap, base * (2 ** max(0, attempt - 1)))
    if jitter:
        return random.uniform(0, base_delay)
    return base_delay


def should_retry(attempt: int, max_attempts: int) -> bool:
    """True while another retry is permitted (ceiling enforces transient -> failed, A1)."""
    return attempt < max_attempts
