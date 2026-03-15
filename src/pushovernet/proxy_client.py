from typing import Any

import httpx

from pushovernet.exceptions import PushoverHTTPError
from pushovernet.models import MessageResponse, RateLimits


class ProxyClient:
    """Client for the pushovernet local proxy server."""

    def __init__(
        self,
        base_url: str = "http://localhost:9505",
        api_key: str | None = None,
    ):
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.Client(base_url=base_url, headers=headers)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._client.close()

    def _handle_response(self, response: httpx.Response) -> dict:
        if response.status_code >= 400:
            try:
                body = response.json()
                detail = body.get("errors") or body.get("error") or body.get("detail", "")
            except (ValueError, KeyError):
                detail = response.text
            raise PushoverHTTPError(response.status_code, str(detail))
        return response.json()

    def send_message(
        self,
        message: str,
        *,
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
        retry: int | None = None,
        expire: int | None = None,
        callback: str | None = None,
        tags: str | None = None,
        attachment_base64: str | None = None,
        attachment_type: str | None = None,
    ) -> MessageResponse:
        data: dict[str, Any] = {"message": message}
        for key, val in [
            ("title", title),
            ("device", device),
            ("priority", priority),
            ("sound", sound),
            ("timestamp", timestamp),
            ("ttl", ttl),
            ("url", url),
            ("url_title", url_title),
            ("html", html),
            ("monospace", monospace),
            ("retry", retry),
            ("expire", expire),
            ("callback", callback),
            ("tags", tags),
            ("attachment_base64", attachment_base64),
            ("attachment_type", attachment_type),
        ]:
            if val is not None:
                data[key] = val

        body = self._handle_response(self._client.post("/send", json=data))
        return MessageResponse(
            status=body["status"],
            request=body["request"],
            receipt=body.get("receipt"),
        )

    def send_glance(
        self,
        *,
        title: str | None = None,
        text: str | None = None,
        subtext: str | None = None,
        count: int | None = None,
        percent: int | None = None,
        device: str | None = None,
    ) -> dict:
        data: dict[str, Any] = {}
        for key, val in [
            ("title", title),
            ("text", text),
            ("subtext", subtext),
            ("count", count),
            ("percent", percent),
            ("device", device),
        ]:
            if val is not None:
                data[key] = val
        return self._handle_response(self._client.post("/glance", json=data))

    def list_sounds(self) -> dict[str, str]:
        body = self._handle_response(self._client.get("/sounds"))
        return body.get("sounds", {})

    def get_limits(self) -> RateLimits:
        body = self._handle_response(self._client.get("/limits"))
        return RateLimits(
            limit=body["limit"],
            remaining=body["remaining"],
            reset=body["reset"],
        )

    def health(self) -> bool:
        try:
            body = self._handle_response(self._client.get("/health"))
            return body.get("status") == "ok"
        except Exception:
            return False
