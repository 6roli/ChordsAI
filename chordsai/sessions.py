"""Per-visitor conversation state and usage limits for the public demo.

Everything lives in memory: the demo runs as a single small server process, and
losing state on restart is acceptable. No message content is stored here
(LangGraph keeps the recent conversation in memory, per visitor thread).
"""

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass
class Session:
    id: str
    last_seen: datetime
    # Incremented on reset so LangGraph starts a fresh conversation thread.
    conversation: int = 0
    message_times: deque = field(default_factory=deque)

    @property
    def thread_id(self) -> str:
        return f"{self.id}:{self.conversation}"

    def reset(self) -> None:
        self.conversation += 1


class SessionStore:
    def __init__(self, ttl: timedelta, max_sessions: int = 1000):
        self._sessions: dict[str, Session] = {}
        self._ttl = ttl
        self._max_sessions = max_sessions
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str | None, now: datetime) -> Session:
        with self._lock:
            self._expire(now)
            session = self._sessions.get(session_id or "")
            if session is None:
                if len(self._sessions) >= self._max_sessions:
                    oldest = min(self._sessions.values(), key=lambda s: s.last_seen)
                    del self._sessions[oldest.id]
                session = Session(id=uuid.uuid4().hex, last_seen=now)
                self._sessions[session.id] = session
            session.last_seen = now
            return session

    def __len__(self) -> int:
        return len(self._sessions)

    def _expire(self, now: datetime) -> None:
        for session_id in [s.id for s in self._sessions.values() if now - s.last_seen > self._ttl]:
            del self._sessions[session_id]


class RateLimiter:
    """Two limits: messages per visitor per hour, and messages per day for the whole demo.

    The daily limit protects the shared Groq free quota so one visitor cannot use it all.
    """

    def __init__(self, per_session_per_hour: int, per_day: int):
        self._per_session = per_session_per_hour
        self._per_day = per_day
        self._day: date | None = None
        self._day_count = 0
        self._lock = threading.Lock()

    def check(self, session: Session, now: datetime) -> str | None:
        """Records the message and returns None, or returns why it is refused."""
        with self._lock:
            if self._day != now.date():
                self._day, self._day_count = now.date(), 0
            if self._day_count >= self._per_day:
                return "The demo has reached its message limit for today. Please try again tomorrow (the piano still works)."
            hour_ago = now - timedelta(hours=1)
            while session.message_times and session.message_times[0] < hour_ago:
                session.message_times.popleft()
            if len(session.message_times) >= self._per_session:
                wait = int((session.message_times[0] + timedelta(hours=1) - now).total_seconds() // 60) + 1
                return f"You have reached the limit of {self._per_session} messages per hour. Try again in about {wait} min."
            session.message_times.append(now)
            self._day_count += 1
            return None
