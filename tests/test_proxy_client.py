import re

import pytest
from pytest_httpx import HTTPXMock

from pushovernet.exceptions import PushoverHTTPError
from pushovernet.models import MessageResponse, RateLimits
from pushovernet.proxy_client import ProxyClient


@pytest.fixture
def proxy():
    c = ProxyClient(base_url="https://proxy.test")
    yield c
    c.close()


@pytest.fixture
def proxy_with_key():
    c = ProxyClient(base_url="https://proxy.test", api_key="secret123")
    yield c
    c.close()


STANDARD_RESPONSE = {"status": 1, "request": "req-proxy-1", "receipt": None}


class TestSendMessage:
    def test_basic(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://proxy.test/send",
            json=STANDARD_RESPONSE,
        )
        resp = proxy.send_message("hello")
        assert isinstance(resp, MessageResponse)
        assert resp.status == 1
        request = httpx_mock.get_request()
        assert request.method == "POST"
        body = request.read()
        assert b'"message":"hello"' in body.replace(b" ", b"")

    def test_with_options(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://proxy.test/send",
            json=STANDARD_RESPONSE,
        )
        resp = proxy.send_message("alert", title="Test", priority=1)
        assert resp.status == 1
        body = httpx_mock.get_request().read()
        assert b"Test" in body

    def test_with_receipt(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://proxy.test/send",
            json={"status": 1, "request": "req-2", "receipt": "rcpt-abc"},
        )
        resp = proxy.send_message("emergency")
        assert resp.receipt == "rcpt-abc"


class TestSendGlance:
    def test_glance(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://proxy.test/glance",
            json={"status": 1, "request": "req-g"},
        )
        resp = proxy.send_glance(title="Status", count=5)
        assert resp["status"] == 1


class TestSounds:
    def test_list_sounds(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=re.compile(r"https://proxy\.test/sounds"),
            json={"sounds": {"pushover": "Pushover"}},
        )
        sounds = proxy.list_sounds()
        assert sounds["pushover"] == "Pushover"


class TestLimits:
    def test_get_limits(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=re.compile(r"https://proxy\.test/limits"),
            json={"limit": 10000, "remaining": 9999, "reset": 1700000000},
        )
        limits = proxy.get_limits()
        assert isinstance(limits, RateLimits)
        assert limits.remaining == 9999


class TestHealth:
    def test_healthy(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=re.compile(r"https://proxy\.test/health"),
            json={"status": "ok"},
        )
        assert proxy.health() is True

    def test_unhealthy(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=re.compile(r"https://proxy\.test/health"),
            status_code=500,
            text="down",
        )
        assert proxy.health() is False


class TestApiKey:
    def test_key_sent_in_header(self, proxy_with_key, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://proxy.test/send",
            json=STANDARD_RESPONSE,
        )
        proxy_with_key.send_message("hello")
        request = httpx_mock.get_request()
        assert request.headers["x-api-key"] == "secret123"

    def test_no_key_by_default(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://proxy.test/send",
            json=STANDARD_RESPONSE,
        )
        proxy.send_message("hello")
        request = httpx_mock.get_request()
        assert "x-api-key" not in request.headers


class TestErrorHandling:
    def test_server_error(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://proxy.test/send",
            status_code=502,
            json={"error": "HTTP 500"},
        )
        with pytest.raises(PushoverHTTPError) as exc_info:
            proxy.send_message("fail")
        assert exc_info.value.status_code == 502

    def test_auth_error(self, proxy, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://proxy.test/send",
            status_code=401,
            json={"detail": "Invalid or missing API key"},
        )
        with pytest.raises(PushoverHTTPError) as exc_info:
            proxy.send_message("fail")
        assert exc_info.value.status_code == 401


class TestContextManager:
    def test_context_manager(self):
        with ProxyClient() as p:
            assert p._client is not None
