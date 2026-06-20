import pytest

from src.core import backoff
from src.integrations.people_client import (
    ContactNotFoundError,
    RateLimitedError,
    TransientError,
)


def test_retry_call_retries_then_succeeds():
    calls = {"n": 0}
    sleeps: list[float] = []

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError()
        return "ok"

    out = backoff.retry_call(
        fn, max_attempts=5, retry_on=(TransientError,), sleep=sleeps.append
    )
    assert out == "ok"
    assert calls["n"] == 3 and len(sleeps) == 2  # slept between the 3 attempts


def test_retry_call_raises_after_ceiling():
    def fn():
        raise RateLimitedError()

    with pytest.raises(RateLimitedError):
        backoff.retry_call(fn, max_attempts=3, retry_on=(RateLimitedError,), sleep=lambda _: None)


def test_retry_call_passes_non_retryable_through_immediately():
    def fn():
        raise ContactNotFoundError()

    with pytest.raises(ContactNotFoundError):
        backoff.retry_call(fn, max_attempts=5, retry_on=(RateLimitedError,), sleep=lambda _: None)


def test_next_delay_respects_retry_after():
    assert backoff.next_delay(1, retry_after=5, jitter=False) == 5


def test_next_delay_exponential_capped():
    assert backoff.next_delay(1, base=1, cap=100, jitter=False) == 1
    assert backoff.next_delay(3, base=1, cap=100, jitter=False) == 4
    assert backoff.next_delay(50, base=1, cap=10, jitter=False) == 10


def test_next_delay_jitter_within_bounds():
    d = backoff.next_delay(4, base=1, cap=100, jitter=True)
    assert 0 <= d <= 8


def test_should_retry_ceiling():
    assert backoff.should_retry(1, 5) is True
    assert backoff.should_retry(5, 5) is False
