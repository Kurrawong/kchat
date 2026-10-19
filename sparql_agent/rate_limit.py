"""In-memory sliding-window rate limiting for agent questions."""

from __future__ import annotations

from collections import defaultdict, deque
import time


class QuestionRateLimiter:
    """Allow at most `max_questions` questions per user per `window_seconds`."""

    def __init__(self, max_questions: int, window_seconds: float, clock=time.monotonic) -> None:
        self.max_questions = max_questions
        self.window_seconds = window_seconds
        self.clock = clock
        self._question_times: dict[str, deque[float]] = defaultdict(deque)

    def _record(self, user: str, now: float) -> deque[float]:
        times = self._question_times[user]
        while times and now - times[0] >= self.window_seconds:
            times.popleft()
        return times

    def check(self, user: str) -> float | None:
        """Record one question for `user`.

        Return None when the question is allowed, or the number of seconds
        until the window frees up when the limit has been reached.
        """
        now = self.clock()
        times = self._record(user, now)
        if len(times) >= self.max_questions:
            return self.window_seconds - (now - times[0])
        times.append(now)
        return None

    def retry_after(self, user: str) -> float:
        """Seconds until the oldest counted question leaves the window."""
        now = self.clock()
        times = self._record(user, now)
        return max(0.0, self.window_seconds - (now - times[0])) if times else 0.0
