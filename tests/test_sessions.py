from datetime import datetime, timedelta

from chordsai.sessions import RateLimiter, SessionStore

NOW = datetime(2026, 10, 19, 12, 0)


def test_sessions_are_separate_and_expire():
    store = SessionStore(ttl=timedelta(minutes=60))
    a = store.get_or_create(None, NOW)
    b = store.get_or_create(None, NOW)
    assert a.id != b.id
    assert store.get_or_create(a.id, NOW + timedelta(minutes=10)) is a
    # After the TTL the old id gives a fresh session.
    assert store.get_or_create(a.id, NOW + timedelta(hours=3)).id != a.id


def test_reset_starts_a_new_conversation_thread():
    session = SessionStore(ttl=timedelta(hours=1)).get_or_create(None, NOW)
    first_thread = session.thread_id
    session.reset()
    assert session.thread_id != first_thread


def test_store_never_grows_beyond_its_limit():
    store = SessionStore(ttl=timedelta(hours=1), max_sessions=3)
    for minute in range(10):
        store.get_or_create(None, NOW + timedelta(minutes=minute))
    assert len(store) == 3


def test_rate_limit_per_visitor_per_hour():
    store, limiter = SessionStore(ttl=timedelta(hours=2)), RateLimiter(per_session_per_hour=3, per_day=100)
    visitor = store.get_or_create(None, NOW)
    assert all(limiter.check(visitor, NOW + timedelta(minutes=i)) is None for i in range(3))
    refusal = limiter.check(visitor, NOW + timedelta(minutes=5))
    assert refusal and "per hour" in refusal
    # Other visitors are not affected, and the limit clears after an hour.
    assert limiter.check(store.get_or_create(None, NOW), NOW + timedelta(minutes=5)) is None
    assert limiter.check(visitor, NOW + timedelta(minutes=61)) is None


def test_daily_limit_is_shared_and_resets_next_day():
    store, limiter = SessionStore(ttl=timedelta(days=2)), RateLimiter(per_session_per_hour=100, per_day=2)
    assert limiter.check(store.get_or_create(None, NOW), NOW) is None
    assert limiter.check(store.get_or_create(None, NOW), NOW) is None
    assert "today" in limiter.check(store.get_or_create(None, NOW), NOW)
    assert limiter.check(store.get_or_create(None, NOW), NOW + timedelta(days=1)) is None
