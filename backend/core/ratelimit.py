"""
In-memory per-workspace rate limiter.

Single always-on process on the free tier (Fly.io/Render/HF Spaces per
DataGenWeb.md §8) — an in-memory sliding window is enough for the MVP and
mirrors the pattern DataGen's telegram_bot.py already uses per chat_id.
Swap for a shared store (Redis) only if the backend is ever scaled to
multiple instances.
"""
import time
from collections import defaultdict, deque

_windows: dict[str, deque] = defaultdict(deque)


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded, retry after {retry_after:.0f}s")


def check_rate_limit(key: str, max_requests: int, window_seconds: float) -> None:
    """Raise RateLimitExceeded if `key` has made >= max_requests in the last window."""
    now = time.monotonic()
    window = _windows[key]

    while window and now - window[0] > window_seconds:
        window.popleft()

    if len(window) >= max_requests:
        retry_after = window_seconds - (now - window[0])
        raise RateLimitExceeded(max(retry_after, 1.0))

    window.append(now)
