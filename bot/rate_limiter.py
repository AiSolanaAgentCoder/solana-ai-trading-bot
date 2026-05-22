"""
Anti-spam rate limiter for Telegram commands.

Uses a sliding window counter per user_id with an in-memory
dictionary. No external dependencies required.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Per-user sliding window rate limiter.

    Args:
        max_requests: Maximum requests allowed in the window.
        window_seconds: Length of the sliding window in seconds.
    """

    def __init__(self, max_requests: Optional[int] = None,
                 window_seconds: Optional[int] = None) -> None:
        settings = get_settings()
        self._max = max_requests or settings.rate_limit_requests
        self._window = window_seconds or settings.rate_limit_window
        self._hits: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        """Check if a request from *user_id* is within the limit.

        Args:
            user_id: Telegram user ID.

        Returns:
            True if allowed, False if rate-limited.
        """
        now = time.time()
        cutoff = now - self._window

        # Prune old entries
        self._hits[user_id] = [t for t in self._hits[user_id] if t > cutoff]

        if len(self._hits[user_id]) >= self._max:
            logger.warning("rate_limiter.blocked", user_id=user_id,
                          count=len(self._hits[user_id]))
            return False

        self._hits[user_id].append(now)
        return True

    def remaining(self, user_id: int) -> int:
        """Return remaining requests for *user_id*."""
        now = time.time()
        cutoff = now - self._window
        recent = [t for t in self._hits.get(user_id, []) if t > cutoff]
        return max(0, self._max - len(recent))

    def reset(self, user_id: int) -> None:
        """Reset rate limit for a specific user."""
        self._hits.pop(user_id, None)
