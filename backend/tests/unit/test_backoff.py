from src.core import backoff


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
