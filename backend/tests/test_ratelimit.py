import pytest

from core.ratelimit import RateLimitExceeded, check_rate_limit


def test_allows_up_to_the_limit():
    key = "test:allows-up-to-limit"
    for _ in range(5):
        check_rate_limit(key, max_requests=5, window_seconds=60)


def test_blocks_after_limit_exceeded():
    key = "test:blocks-after-limit"
    for _ in range(3):
        check_rate_limit(key, max_requests=3, window_seconds=60)
    with pytest.raises(RateLimitExceeded):
        check_rate_limit(key, max_requests=3, window_seconds=60)


def test_different_keys_are_independent():
    check_rate_limit("test:key-a", max_requests=1, window_seconds=60)
    check_rate_limit("test:key-b", max_requests=1, window_seconds=60)  # must not raise


def test_retry_after_is_positive():
    key = "test:retry-after"
    check_rate_limit(key, max_requests=1, window_seconds=60)
    with pytest.raises(RateLimitExceeded) as exc_info:
        check_rate_limit(key, max_requests=1, window_seconds=60)
    assert exc_info.value.retry_after > 0
