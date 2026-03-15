import re
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from pushovernet.client import PushoverClient
from pushovernet.exceptions import (
    PushoverAPIError,
    PushoverHTTPError,
    PushoverRateLimitError,
)
from pushovernet.models import (
    GroupCreated,
    GroupInfo,
    LicenseInfo,
    MessageResponse,
    RateLimits,
    ReceiptStatus,
    SubscriptionResponse,
    ValidateResponse,
)
from tests.conftest import STANDARD_RESPONSE


class TestSendMessage:
    def test_basic_message(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            json={"status": 1, "request": "req-1"},
        )
        resp = client.send_message("hello")
        assert isinstance(resp, MessageResponse)
        assert resp.status == 1
        assert resp.request == "req-1"
        assert resp.receipt is None

    def test_message_with_receipt(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            json={"status": 1, "request": "req-2", "receipt": "rcpt-abc"},
        )
        resp = client.send_message(
            "emergency", priority=2, retry=30, expire=3600
        )
        assert resp.receipt == "rcpt-abc"

    def test_emergency_missing_retry(self, client):
        with pytest.raises(ValueError, match="retry >= 30"):
            client.send_message("urgent", priority=2, expire=3600)

    def test_emergency_retry_too_low(self, client):
        with pytest.raises(ValueError, match="retry >= 30"):
            client.send_message("urgent", priority=2, retry=10, expire=3600)

    def test_emergency_expire_too_high(self, client):
        with pytest.raises(ValueError, match="expire <= 10800"):
            client.send_message("urgent", priority=2, retry=30, expire=20000)

    def test_message_with_all_options(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.send_message(
            "test",
            title="Title",
            device="phone",
            priority=1,
            sound="cosmic",
            timestamp=1234567890,
            ttl=300,
            url="https://example.com",
            url_title="Example",
            html=True,
            tags="tag1",
        )
        assert resp.status == 1

    def test_message_with_bytes_attachment(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.send_message("with image", attachment=b"\x89PNG\r\n")
        assert resp.status == 1

    def test_message_with_file_attachment(self, client, httpx_mock: HTTPXMock, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n")
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.send_message("with file", attachment=str(img))
        assert resp.status == 1

    def test_config_defaults_applied(self, httpx_mock: HTTPXMock):
        from pushovernet.config import PushoverConfig

        config = PushoverConfig(
            token="tok",
            user_key="usr",
            default_device="myphone",
            default_priority=-1,
            default_sound="cosmic",
        )
        c = PushoverClient(config=config)
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            json=STANDARD_RESPONSE,
        )
        c.send_message("test")
        request = httpx_mock.get_request()
        body = request.content.decode()
        assert "myphone" in body
        assert "cosmic" in body
        c.close()


class TestValidateUser:
    def test_validate(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/users/validate.json",
            json={"status": 1, "request": "req-v", "devices": ["iphone", "desktop"]},
        )
        resp = client.validate_user()
        assert isinstance(resp, ValidateResponse)
        assert resp.devices == ["iphone", "desktop"]


class TestReceipts:
    def test_get_receipt(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=re.compile(r"https://api\.pushover\.net/1/receipts/rcpt123\.json"),
            json={
                "status": 1, "request": "req-r",
                "acknowledged": 1, "acknowledged_at": 1000,
                "acknowledged_by": "user1", "acknowledged_by_device": "phone",
                "last_delivered_at": 900, "expired": 0, "expires_at": 2000,
                "called_back": 0, "called_back_at": 0,
            },
        )
        resp = client.get_receipt("rcpt123")
        assert isinstance(resp, ReceiptStatus)
        assert resp.acknowledged == 1

    def test_cancel_receipt(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/receipts/rcpt123/cancel.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.cancel_receipt("rcpt123")
        assert resp["status"] == 1

    def test_cancel_by_tag(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/receipts/cancel_by_tag/mytag.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.cancel_receipt_by_tag("mytag")
        assert resp["status"] == 1


class TestSounds:
    def test_list_sounds(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=re.compile(r"https://api\.pushover\.net/1/sounds\.json"),
            json={"status": 1, "request": "req-s", "sounds": {"pushover": "Pushover", "cosmic": "Cosmic"}},
        )
        sounds = client.list_sounds()
        assert sounds["pushover"] == "Pushover"


class TestLimits:
    def test_get_limits(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=re.compile(r"https://api\.pushover\.net/1/apps/limits\.json"),
            json={"status": 1, "request": "req-l", "limit": 10000, "remaining": 9500, "reset": 1700000000},
        )
        limits = client.get_limits()
        assert isinstance(limits, RateLimits)
        assert limits.limit == 10000
        assert limits.remaining == 9500


class TestGroups:
    def test_create_group(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/groups.json",
            method="POST",
            json={"status": 1, "request": "req-g", "group": "grp-key-1"},
        )
        resp = client.create_group("Test Group")
        assert isinstance(resp, GroupCreated)
        assert resp.group == "grp-key-1"

    def test_list_groups(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=re.compile(r"https://api\.pushover\.net/1/groups\.json"),
            method="GET",
            json={"status": 1, "request": "req-g", "groups": [
                {"group": "g1", "name": "Group 1"},
                {"group": "g2", "name": "Group 2"},
            ]},
        )
        groups = client.list_groups()
        assert len(groups) == 2
        assert groups[0].name == "Group 1"

    def test_get_group(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=re.compile(r"https://api\.pushover\.net/1/groups/grp1\.json"),
            json={"status": 1, "request": "req-g", "name": "My Group", "users": [
                {"user": "u1", "device": "phone", "memo": "admin", "disabled": False},
            ]},
        )
        info = client.get_group("grp1")
        assert isinstance(info, GroupInfo)
        assert info.name == "My Group"
        assert len(info.users) == 1

    def test_add_user_to_group(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/groups/grp1/add_user.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.add_user_to_group("grp1", "user1", memo="new member")
        assert resp["status"] == 1

    def test_remove_user_from_group(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/groups/grp1/remove_user.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.remove_user_from_group("grp1", "user1")
        assert resp["status"] == 1

    def test_rename_group(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/groups/grp1/rename.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.rename_group("grp1", "New Name")
        assert resp["status"] == 1

    def test_disable_user(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/groups/grp1/disable_user.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.disable_user_in_group("grp1", "user1")
        assert resp["status"] == 1

    def test_enable_user(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/groups/grp1/enable_user.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.enable_user_in_group("grp1", "user1")
        assert resp["status"] == 1


class TestGlance:
    def test_send_glance(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/glances.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.send_glance(title="Status", count=42)
        assert resp["status"] == 1

    def test_glance_no_fields(self, client):
        with pytest.raises(ValueError, match="At least one"):
            client.send_glance()


class TestSubscription:
    def test_migrate(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/subscriptions/migrate.json",
            json={"status": 1, "request": "req-sub", "subscribed_user_key": "sub-usr-1"},
        )
        resp = client.migrate_subscription("sub-code", "user1")
        assert isinstance(resp, SubscriptionResponse)
        assert resp.subscribed_user_key == "sub-usr-1"


class TestLicense:
    def test_assign_license(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/licenses/assign.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.assign_license(user="user1")
        assert resp["status"] == 1

    def test_assign_license_by_email(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/licenses/assign.json",
            json=STANDARD_RESPONSE,
        )
        resp = client.assign_license(email="user@example.com")
        assert resp["status"] == 1

    def test_assign_license_both_fails(self, client):
        with pytest.raises(ValueError, match="Exactly one"):
            client.assign_license(user="u", email="e@e.com")

    def test_assign_license_neither_fails(self, client):
        with pytest.raises(ValueError, match="Exactly one"):
            client.assign_license()

    def test_get_credits(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=re.compile(r"https://api\.pushover\.net/1/licenses\.json"),
            json={"status": 1, "request": "req-lic", "credits": 50},
        )
        resp = client.get_license_credits()
        assert isinstance(resp, LicenseInfo)
        assert resp.credits == 50


class TestErrorHandling:
    def test_api_error(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            status_code=400,
            json={"status": 0, "request": "req-err", "errors": ["invalid token"]},
        )
        with pytest.raises(PushoverAPIError) as exc_info:
            client.send_message("fail")
        assert exc_info.value.errors == ["invalid token"]
        assert exc_info.value.request_id == "req-err"

    def test_rate_limit_error(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            status_code=429,
            headers={
                "X-Limit-App-Limit": "10000",
                "X-Limit-App-Remaining": "0",
                "X-Limit-App-Reset": "1700000000",
            },
            json={"status": 0, "request": "req-rl", "errors": ["rate limited"]},
        )
        with pytest.raises(PushoverRateLimitError) as exc_info:
            client.send_message("fail")
        assert exc_info.value.reset_at == 1700000000

    def test_http_error(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            status_code=500,
            text="Internal Server Error",
        )
        with pytest.raises(PushoverHTTPError) as exc_info:
            client.send_message("fail")
        assert exc_info.value.status_code == 500

    def test_rate_limits_parsed_from_headers(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            headers={
                "X-Limit-App-Limit": "10000",
                "X-Limit-App-Remaining": "9999",
                "X-Limit-App-Reset": "1700000000",
            },
            json=STANDARD_RESPONSE,
        )
        client.send_message("test")
        assert client.rate_limits is not None
        assert client.rate_limits.limit == 10000
        assert client.rate_limits.remaining == 9999


class TestContextManager:
    def test_context_manager(self):
        from pushovernet.config import PushoverConfig

        config = PushoverConfig(token="t", user_key="u")
        with PushoverClient(config=config) as c:
            assert c._token == "t"
