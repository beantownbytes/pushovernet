from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from pushovernet.models import MessageResponse, RateLimits
from pushovernet.exceptions import PushoverAPIError, PushoverRateLimitError, PushoverHTTPError


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.send_message.return_value = MessageResponse(status=1, request="req-1")
    client.send_glance.return_value = {"status": 1, "request": "req-2"}
    client.list_sounds.return_value = {"pushover": "Pushover", "cosmic": "Cosmic"}
    client.get_limits.return_value = RateLimits(limit=10000, remaining=9999, reset=1700000000)
    return client


@pytest.fixture
def test_app(mock_client):
    from pushovernet.server import create_app, _server_config
    import pushovernet.server as server_mod

    with patch.object(server_mod, "_server_config", server_mod.ServerConfig()):
        app = create_app.__wrapped__(None) if hasattr(create_app, "__wrapped__") else create_app(None)
        app.state.client = mock_client
        yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def test_app_with_key(mock_client):
    from pushovernet.server import create_app
    from pushovernet.config import ServerConfig

    keyed_config = ServerConfig(api_key="test-secret")
    with patch.object(ServerConfig, "load", return_value=keyed_config):
        app = create_app(None)
    app.state.client = mock_client
    yield TestClient(app, raise_server_exceptions=False)


class TestHealth:
    def test_health(self, test_app):
        resp = test_app.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestSend:
    def test_send_message(self, test_app, mock_client):
        resp = test_app.post("/send", json={"message": "hello"})
        assert resp.status_code == 200
        assert resp.json()["status"] == 1
        mock_client.send_message.assert_called_once_with(message="hello")

    def test_send_with_options(self, test_app, mock_client):
        resp = test_app.post("/send", json={
            "message": "alert",
            "title": "Test",
            "priority": 1,
            "sound": "cosmic",
        })
        assert resp.status_code == 200
        mock_client.send_message.assert_called_once_with(
            message="alert", title="Test", priority=1, sound="cosmic"
        )

    def test_send_missing_message(self, test_app):
        resp = test_app.post("/send", json={})
        assert resp.status_code == 422


class TestGlance:
    def test_send_glance(self, test_app, mock_client):
        resp = test_app.post("/glance", json={"title": "Status", "count": 42})
        assert resp.status_code == 200
        mock_client.send_glance.assert_called_once_with(title="Status", count=42)


class TestSounds:
    def test_list_sounds(self, test_app, mock_client):
        resp = test_app.get("/sounds")
        assert resp.status_code == 200
        assert resp.json()["sounds"]["pushover"] == "Pushover"


class TestLimits:
    def test_get_limits(self, test_app, mock_client):
        resp = test_app.get("/limits")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 10000


class TestApiKey:
    def test_no_key_required_by_default(self, test_app):
        resp = test_app.get("/health")
        assert resp.status_code == 200

    def test_key_required_when_configured(self, test_app_with_key):
        resp = test_app_with_key.post("/send", json={"message": "hello"})
        assert resp.status_code == 401

    def test_correct_key_accepted(self, test_app_with_key):
        resp = test_app_with_key.post(
            "/send",
            json={"message": "hello"},
            headers={"X-API-Key": "test-secret"},
        )
        assert resp.status_code == 200

    def test_wrong_key_rejected(self, test_app_with_key):
        resp = test_app_with_key.post(
            "/send",
            json={"message": "hello"},
            headers={"X-API-Key": "wrong"},
        )
        assert resp.status_code == 401


class TestErrorHandling:
    def test_api_error(self, test_app, mock_client):
        mock_client.send_message.side_effect = PushoverAPIError(0, ["bad token"], "req-err")
        resp = test_app.post("/send", json={"message": "fail"})
        assert resp.status_code == 422
        assert resp.json()["errors"] == ["bad token"]

    def test_rate_limit_error(self, test_app, mock_client):
        mock_client.send_message.side_effect = PushoverRateLimitError(0, ["rate limited"], "req-rl", 1700000000)
        resp = test_app.post("/send", json={"message": "fail"})
        assert resp.status_code == 429
        assert resp.json()["reset_at"] == 1700000000

    def test_http_error(self, test_app, mock_client):
        mock_client.send_message.side_effect = PushoverHTTPError(500, "Internal Server Error")
        resp = test_app.post("/send", json={"message": "fail"})
        assert resp.status_code == 502

    def test_value_error(self, test_app, mock_client):
        mock_client.send_message.side_effect = ValueError("retry >= 30")
        resp = test_app.post("/send", json={"message": "fail"})
        assert resp.status_code == 422
        assert "retry" in resp.json()["error"]
