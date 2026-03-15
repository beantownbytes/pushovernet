from pathlib import Path
from typing import Any

import httpx

from pushovernet.config import PushoverConfig
from pushovernet.exceptions import (
    PushoverAPIError,
    PushoverHTTPError,
    PushoverRateLimitError,
)
from pushovernet.models import (
    GroupCreated,
    GroupInfo,
    GroupListEntry,
    GroupUser,
    LicenseInfo,
    MessageResponse,
    RateLimits,
    ReceiptStatus,
    SubscriptionResponse,
    ValidateResponse,
)

BASE_URL = "https://api.pushover.net"


class PushoverClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        user_key: str | None = None,
        config: PushoverConfig | None = None,
        config_path: Path | str | None = None,
    ):
        if token and user_key:
            self._token = token
            self._user_key = user_key
            self._config = PushoverConfig(token=token, user_key=user_key)
        elif config:
            self._config = config
            self._token = config.token
            self._user_key = config.user_key
        else:
            self._config = PushoverConfig.from_toml(config_path)
            self._token = self._config.token
            self._user_key = self._config.user_key

        self._client = httpx.Client(base_url=BASE_URL)
        self.rate_limits: RateLimits | None = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._client.close()

    def _update_rate_limits(self, response: httpx.Response) -> None:
        limit = response.headers.get("X-Limit-App-Limit")
        remaining = response.headers.get("X-Limit-App-Remaining")
        reset = response.headers.get("X-Limit-App-Reset")
        if limit is not None and remaining is not None and reset is not None:
            self.rate_limits = RateLimits(
                limit=int(limit),
                remaining=int(remaining),
                reset=int(reset),
            )

    def _handle_response(self, response: httpx.Response) -> dict:
        self._update_rate_limits(response)

        if response.status_code == 429:
            body = response.json()
            reset_at = int(response.headers.get("X-Limit-App-Reset", 0))
            raise PushoverRateLimitError(
                status=body.get("status", 0),
                errors=body.get("errors", ["Rate limit exceeded"]),
                request_id=body.get("request", ""),
                reset_at=reset_at,
            )

        if response.status_code >= 400:
            try:
                body = response.json()
                if body.get("status") == 0:
                    raise PushoverAPIError(
                        status=body["status"],
                        errors=body.get("errors", []),
                        request_id=body.get("request", ""),
                    )
            except (ValueError, KeyError):
                pass
            raise PushoverHTTPError(response.status_code, response.text)

        body = response.json()
        if body.get("status") == 0:
            raise PushoverAPIError(
                status=body["status"],
                errors=body.get("errors", []),
                request_id=body.get("request", ""),
            )
        return body

    def _post(self, path: str, data: dict[str, Any], **kwargs) -> dict:
        data["token"] = self._token
        response = self._client.post(path, data=data, **kwargs)
        return self._handle_response(response)

    def _post_multipart(
        self, path: str, data: dict[str, Any], files: dict[str, Any]
    ) -> dict:
        data["token"] = self._token
        response = self._client.post(path, data=data, files=files)
        return self._handle_response(response)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        params = params or {}
        params["token"] = self._token
        response = self._client.get(path, params=params)
        return self._handle_response(response)

    def send_message(
        self,
        message: str,
        *,
        user: str | None = None,
        title: str | None = None,
        device: str | None = None,
        priority: int | None = None,
        sound: str | None = None,
        timestamp: int | None = None,
        ttl: int | None = None,
        url: str | None = None,
        url_title: str | None = None,
        html: bool | None = None,
        monospace: bool | None = None,
        attachment: str | Path | bytes | None = None,
        attachment_base64: str | None = None,
        attachment_type: str | None = None,
        retry: int | None = None,
        expire: int | None = None,
        callback: str | None = None,
        tags: str | None = None,
    ) -> MessageResponse:
        resolved_priority = priority if priority is not None else self._config.default_priority

        if resolved_priority == 2:
            if retry is None or retry < 30:
                raise ValueError("Emergency priority requires retry >= 30 seconds")
            if expire is None or expire > 10800:
                raise ValueError("Emergency priority requires expire <= 10800 seconds")

        data: dict[str, Any] = {
            "user": user or self._user_key,
            "message": message,
        }

        resolved_device = device if device is not None else self._config.default_device
        if resolved_device:
            data["device"] = resolved_device

        if resolved_priority != 0:
            data["priority"] = resolved_priority

        resolved_sound = sound if sound is not None else self._config.default_sound
        if resolved_sound:
            data["sound"] = resolved_sound

        for key, val in [
            ("title", title),
            ("timestamp", timestamp),
            ("ttl", ttl),
            ("url", url),
            ("url_title", url_title),
            ("retry", retry),
            ("expire", expire),
            ("callback", callback),
            ("tags", tags),
            ("attachment_base64", attachment_base64),
            ("attachment_type", attachment_type),
        ]:
            if val is not None:
                data[key] = val

        if html:
            data["html"] = 1
        if monospace:
            data["monospace"] = 1

        if attachment is not None and not isinstance(attachment, bytes):
            attachment = Path(attachment)
            with open(attachment, "rb") as f:
                body = self._post_multipart(
                    "/1/messages.json",
                    data,
                    files={"attachment": (attachment.name, f, attachment_type or "application/octet-stream")},
                )
        elif isinstance(attachment, bytes):
            body = self._post_multipart(
                "/1/messages.json",
                data,
                files={"attachment": ("attachment", attachment, attachment_type or "application/octet-stream")},
            )
        else:
            body = self._post("/1/messages.json", data)

        return MessageResponse(
            status=body["status"],
            request=body["request"],
            receipt=body.get("receipt"),
        )

    def validate_user(
        self, user: str | None = None, device: str | None = None
    ) -> ValidateResponse:
        data: dict[str, Any] = {"user": user or self._user_key}
        if device:
            data["device"] = device
        body = self._post("/1/users/validate.json", data)
        return ValidateResponse(
            status=body["status"],
            request=body["request"],
            devices=body.get("devices", []),
        )

    def get_receipt(self, receipt: str) -> ReceiptStatus:
        body = self._get(f"/1/receipts/{receipt}.json")
        return ReceiptStatus(
            status=body["status"],
            request=body["request"],
            acknowledged=body.get("acknowledged", 0),
            acknowledged_at=body.get("acknowledged_at", 0),
            acknowledged_by=body.get("acknowledged_by", ""),
            acknowledged_by_device=body.get("acknowledged_by_device", ""),
            last_delivered_at=body.get("last_delivered_at", 0),
            expired=body.get("expired", 0),
            expires_at=body.get("expires_at", 0),
            called_back=body.get("called_back", 0),
            called_back_at=body.get("called_back_at", 0),
        )

    def cancel_receipt(self, receipt: str) -> dict:
        return self._post(f"/1/receipts/{receipt}/cancel.json", {})

    def cancel_receipt_by_tag(self, tag: str) -> dict:
        return self._post(f"/1/receipts/cancel_by_tag/{tag}.json", {})

    def list_sounds(self) -> dict[str, str]:
        body = self._get("/1/sounds.json")
        return body.get("sounds", {})

    def get_limits(self) -> RateLimits:
        body = self._get("/1/apps/limits.json")
        return RateLimits(
            limit=body.get("app_limit", body.get("limit")),
            remaining=body.get("app_remaining", body.get("remaining")),
            reset=body.get("app_reset", body.get("reset")),
        )

    def create_group(self, name: str) -> GroupCreated:
        body = self._post("/1/groups.json", {"name": name})
        return GroupCreated(
            status=body["status"],
            request=body["request"],
            group=body["group"],
        )

    def list_groups(self) -> list[GroupListEntry]:
        body = self._get("/1/groups.json")
        return [
            GroupListEntry(group=g["group"], name=g["name"])
            for g in body.get("groups", [])
        ]

    def get_group(self, group_key: str) -> GroupInfo:
        body = self._get(f"/1/groups/{group_key}.json")
        users = [
            GroupUser(
                user=u["user"],
                device=u.get("device", ""),
                memo=u.get("memo", ""),
                disabled=u.get("disabled", False),
            )
            for u in body.get("users", [])
        ]
        return GroupInfo(name=body["name"], users=users)

    def add_user_to_group(
        self, group_key: str, user: str, *, device: str | None = None, memo: str | None = None
    ) -> dict:
        data: dict[str, Any] = {"user": user}
        if device:
            data["device"] = device
        if memo:
            data["memo"] = memo
        return self._post(f"/1/groups/{group_key}/add_user.json", data)

    def remove_user_from_group(
        self, group_key: str, user: str, *, device: str | None = None
    ) -> dict:
        data: dict[str, Any] = {"user": user}
        if device:
            data["device"] = device
        return self._post(f"/1/groups/{group_key}/remove_user.json", data)

    def disable_user_in_group(
        self, group_key: str, user: str, *, device: str | None = None
    ) -> dict:
        data: dict[str, Any] = {"user": user}
        if device:
            data["device"] = device
        return self._post(f"/1/groups/{group_key}/disable_user.json", data)

    def enable_user_in_group(
        self, group_key: str, user: str, *, device: str | None = None
    ) -> dict:
        data: dict[str, Any] = {"user": user}
        if device:
            data["device"] = device
        return self._post(f"/1/groups/{group_key}/enable_user.json", data)

    def rename_group(self, group_key: str, name: str) -> dict:
        return self._post(f"/1/groups/{group_key}/rename.json", {"name": name})

    def send_glance(
        self,
        *,
        user: str | None = None,
        device: str | None = None,
        title: str | None = None,
        text: str | None = None,
        subtext: str | None = None,
        count: int | None = None,
        percent: int | None = None,
    ) -> dict:
        fields = {
            "title": title,
            "text": text,
            "subtext": subtext,
            "count": count,
            "percent": percent,
        }
        if not any(v is not None for v in fields.values()):
            raise ValueError("At least one glance data field must be provided")

        data: dict[str, Any] = {"user": user or self._user_key}
        if device:
            data["device"] = device
        for key, val in fields.items():
            if val is not None:
                data[key] = val
        return self._post("/1/glances.json", data)

    def migrate_subscription(
        self,
        subscription: str,
        user: str,
        *,
        device_name: str | None = None,
        sound: str | None = None,
    ) -> SubscriptionResponse:
        data: dict[str, Any] = {"subscription": subscription, "user": user}
        if device_name:
            data["device_name"] = device_name
        if sound:
            data["sound"] = sound
        body = self._post("/1/subscriptions/migrate.json", data)
        return SubscriptionResponse(
            status=body["status"],
            request=body["request"],
            subscribed_user_key=body["subscribed_user_key"],
        )

    def assign_license(
        self,
        *,
        user: str | None = None,
        email: str | None = None,
        os: str | None = None,
    ) -> dict:
        if (user is None) == (email is None):
            raise ValueError("Exactly one of 'user' or 'email' must be provided")
        data: dict[str, Any] = {}
        if user:
            data["user"] = user
        if email:
            data["email"] = email
        if os:
            data["os"] = os
        return self._post("/1/licenses/assign.json", data)

    def get_license_credits(self) -> LicenseInfo:
        body = self._get("/1/licenses.json")
        return LicenseInfo(
            status=body["status"],
            request=body["request"],
            credits=body["credits"],
        )
