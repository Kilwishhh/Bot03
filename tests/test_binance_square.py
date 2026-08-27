"""Tests for the Binance Square poster, queue, and admin endpoints."""

import tempfile
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.server import app
from app.config import Settings
from app.notifications import (
    BinanceSquarePoster,
    CompositePublisher,
    FlushingPublisher,
    SignalPublisher,
)
from app.signals.models import Signal, SignalSide


def _admin_headers() -> dict:
    token = Settings().admin_api_token
    if not token:
        raise RuntimeError("conftest should have set ADMIN_API_TOKEN")
    return {"Authorization": f"Bearer {token}"}


# ----------------------------------------------------------------------
# Poster unit tests
# ----------------------------------------------------------------------

@pytest.fixture
def tmp_state_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def poster_no_key(tmp_state_dir):
    """A poster with no API key — must queue but never call HTTP."""
    return BinanceSquarePoster(api_key="", state_dir=tmp_state_dir)


def test_poster_is_off_by_default(poster_no_key):
    assert poster_no_key.api_available is False
    assert poster_no_key.is_posting_enabled() is False
    assert poster_no_key.can_post() is False


def test_poster_enqueues_when_disabled(poster_no_key):
    """Even with no API key + toggle off, enqueue must succeed."""
    poster_no_key.enqueue("hello", priority=1, category="test")
    status = poster_no_key.get_status()
    assert status["queued"]["total"] == 1
    assert status["queued"]["by_category"].get("test") == 1


def test_poster_flush_returns_skipped_when_no_api(poster_no_key):
    poster_no_key.enqueue("hello")
    result = poster_no_key.flush_queue(count=1)
    assert result["posted"] == 0
    assert result["skipped_reason"] == "no_api_key"
    # item stays in the queue
    assert poster_no_key.get_status()["queued"]["total"] == 1


def test_poster_publish_never_raises(poster_no_key):
    """Signal publishing must never raise, even with no API key."""
    signal = Signal("BTCUSDT", SignalSide.BUY, 0.85, datetime.now(UTC), ["test"], "x")
    poster_no_key.publish(signal)  # should not raise
    assert poster_no_key.get_status()["queued"]["total"] == 1


def test_poster_toggle_persists(tmp_state_dir):
    p1 = BinanceSquarePoster(api_key="k", state_dir=tmp_state_dir)
    p1._state.toggle(True)
    p2 = BinanceSquarePoster(api_key="k", state_dir=tmp_state_dir)
    assert p2.is_posting_enabled() is True
    p2._state.toggle(False)
    p3 = BinanceSquarePoster(api_key="k", state_dir=tmp_state_dir)
    assert p3.is_posting_enabled() is False


def test_poster_daily_limit_blocks_extra_posts(tmp_state_dir):
    p = BinanceSquarePoster(api_key="k", state_dir=tmp_state_dir, daily_limit=2)
    p._state.toggle(True)
    p._state.log_post("one")
    p._state.log_post("two")
    p.enqueue("three")
    result = p.flush_queue(count=1)
    assert result["posted"] == 0
    assert result["skipped_reason"] == "daily_limit"


def test_poster_post_now_2xx_succeeds(tmp_state_dir):
    p = BinanceSquarePoster(
        api_key="secret",
        endpoint="http://example.test/post",
        state_dir=tmp_state_dir,
    )
    p._state.toggle(True)
    p.enqueue("hi")
    with patch("app.notifications.binance_square.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.status = 200
        result = p.flush_queue(count=1)
    assert result["posted"] == 1
    assert result["queue_left"] == 0


def test_poster_post_now_non_2xx_keeps_in_queue(tmp_state_dir):
    p = BinanceSquarePoster(
        api_key="secret",
        endpoint="http://example.test/post",
        state_dir=tmp_state_dir,
    )
    p._state.toggle(True)
    p.enqueue("hi")
    with patch("app.notifications.binance_square.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.status = 500
        result = p.flush_queue(count=1)
    assert result["posted"] == 0
    assert result["queue_left"] == 1  # item stayed


def test_poster_post_now_network_error_keeps_in_queue(tmp_state_dir):
    from urllib.error import URLError
    p = BinanceSquarePoster(
        api_key="secret",
        endpoint="http://example.test/post",
        state_dir=tmp_state_dir,
    )
    p._state.toggle(True)
    p.enqueue("hi")
    with patch("app.notifications.binance_square.urlopen", side_effect=URLError("boom")):
        result = p.flush_queue(count=1)
    assert result["posted"] == 0
    assert result["queue_left"] == 1


def test_composite_publisher_isolates_failures():
    class _Boom(SignalPublisher):
        def publish(self, signal):
            raise RuntimeError("kapow")

    class _Good(SignalPublisher):
        def __init__(self):
            self.received = []
        def publish(self, signal):
            self.received.append(signal)

    good = _Good()
    composite = CompositePublisher([_Boom(), good])
    signal = Signal("BTCUSDT", SignalSide.BUY, 0.8, datetime.now(UTC), ["x"], "y")
    composite.publish(signal)  # must not raise
    assert good.received == [signal]


def test_flushing_publisher_flushes_after_publish(tmp_state_dir):
    p = BinanceSquarePoster(api_key="k", state_dir=tmp_state_dir)
    p._state.toggle(True)
    flusher = FlushingPublisher(p, count=1)
    signal = Signal("BTCUSDT", SignalSide.BUY, 0.8, datetime.now(UTC), ["x"], "y")
    with patch("app.notifications.binance_square.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.status = 200
        flusher.publish(signal)
    assert p.get_status()["queued"]["total"] == 0


# ----------------------------------------------------------------------
# Admin API tests
# ----------------------------------------------------------------------

def test_admin_square_status_requires_auth():
    client = TestClient(app)
    assert client.get("/admin/square/status").status_code == 401


def test_admin_square_status_reports_unchecked_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("BINANCE_SQUARE_STATE_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.get("/admin/square/status", headers=_admin_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is False
    assert data["enabled"] is False
    assert data["status"]["today_count"] == 0


def test_admin_square_toggle_persists_state(monkeypatch, tmp_path):
    monkeypatch.setenv("BINANCE_SQUARE_STATE_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.post("/admin/square/toggle", json={"enabled": True}, headers=_admin_headers())
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    # verify it persists across a fresh client
    client2 = TestClient(app)
    status = client2.get("/admin/square/status", headers=_admin_headers()).json()
    assert status["enabled"] is True


def test_admin_square_toggle_requires_enabled_field():
    client = TestClient(app)
    response = client.post("/admin/square/toggle", json={}, headers=_admin_headers())
    assert response.status_code == 400


def test_admin_square_enqueue_adds_to_queue(monkeypatch, tmp_path):
    monkeypatch.setenv("BINANCE_SQUARE_STATE_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.post(
        "/admin/square/enqueue",
        json={"message": "manual test post", "priority": 3, "category": "manual"},
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    assert response.json()["status"]["queued"]["total"] == 1


def test_admin_square_enqueue_rejects_empty_message():
    client = TestClient(app)
    response = client.post("/admin/square/enqueue", json={"message": ""}, headers=_admin_headers())
    assert response.status_code == 400


def test_admin_square_flush_returns_summary(monkeypatch, tmp_path):
    monkeypatch.setenv("BINANCE_SQUARE_STATE_DIR", str(tmp_path))
    client = TestClient(app)
    client.post("/admin/square/enqueue", json={"message": "x"}, headers=_admin_headers())
    response = client.post("/admin/square/flush", json={"count": 1}, headers=_admin_headers())
    assert response.status_code == 200
    body = response.json()
    # no API key, so flushed = 0 and reason is no_api_key
    assert body["posted"] == 0
    assert body["skipped_reason"] == "no_api_key"
    # queued item is still there
    assert body["queue_left"] == 1


def test_admin_data_includes_square_payload():
    client = TestClient(app)
    response = client.get("/admin/data", headers=_admin_headers())
    assert response.status_code == 200
    payload = response.json()
    assert "square" in payload
    assert "api_available" in payload["square"]
    assert "posting_enabled" in payload["square"]
    assert "queued" in payload["square"]


# ----------------------------------------------------------------------
# Settings validation
# ----------------------------------------------------------------------

def test_enable_binance_square_requires_api_key():
    with pytest.raises(Exception, match="BINANCE_SQUARE_API_KEY"):
        Settings(_env_file=None, enable_binance_square=True)
