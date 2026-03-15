from pathlib import Path
from types import TracebackType
from typing import Any

import httpx

from pushovernet.config import ProxyConfig
from pushovernet.exceptions import PushoverHTTPError
from pushovernet.models import MessageResponse, RateLimits

JSONDict = dict[str, Any]  # type alias for parsed JSON from response.json()


class ProxyClient:

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        config_path: Path | str | None = None,
    ) -> None:
        if base_url is None and api_key is None:
            config = ProxyConfig.load(config_path)
            base_url = config.url
            api_key = api_key or config.api_key or None

        headers: dict[str, str] = {}
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.Client(base_url=base_url or "http://localhost:9505", headers=headers)

    def __enter__(self) -> "ProxyClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _handle_response(self, response: httpx.Response) -> JSONDict:
        if response.status_code >= 400:
            try:
                body: JSONDict = response.json()
                detail = body.get("errors") or body.get("error") or body.get("detail", "")
            except (ValueError, KeyError):
                detail = response.text
            raise PushoverHTTPError(response.status_code, str(detail))
        result: JSONDict = response.json()
        return result

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
        payload: dict[str, str | int | bool] = {"message": message}
        if title is not None:
            payload["title"] = title
        if device is not None:
            payload["device"] = device
        if priority is not None:
            payload["priority"] = priority
        if sound is not None:
            payload["sound"] = sound
        if timestamp is not None:
            payload["timestamp"] = timestamp
        if ttl is not None:
            payload["ttl"] = ttl
        if url is not None:
            payload["url"] = url
        if url_title is not None:
            payload["url_title"] = url_title
        if html is not None:
            payload["html"] = html
        if monospace is not None:
            payload["monospace"] = monospace
        if retry is not None:
            payload["retry"] = retry
        if expire is not None:
            payload["expire"] = expire
        if callback is not None:
            payload["callback"] = callback
        if tags is not None:
            payload["tags"] = tags
        if attachment_base64 is not None:
            payload["attachment_base64"] = attachment_base64
        if attachment_type is not None:
            payload["attachment_type"] = attachment_type

        body = self._handle_response(self._client.post("/send", json=payload))
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
    ) -> JSONDict:
        payload: dict[str, str | int] = {}
        if title is not None:
            payload["title"] = title
        if text is not None:
            payload["text"] = text
        if subtext is not None:
            payload["subtext"] = subtext
        if count is not None:
            payload["count"] = count
        if percent is not None:
            payload["percent"] = percent
        if device is not None:
            payload["device"] = device
        return self._handle_response(self._client.post("/glance", json=payload))

    def list_sounds(self) -> dict[str, str]:
        body = self._handle_response(self._client.get("/sounds"))
        result: dict[str, str] = body.get("sounds", {})
        return result

    def get_limits(self) -> RateLimits:
        body = self._handle_response(self._client.get("/limits"))
        return RateLimits(
            limit=int(body["limit"]),
            remaining=int(body["remaining"]),
            reset=int(body["reset"]),
        )

    def health(self) -> bool:
        try:
            body = self._handle_response(self._client.get("/health"))
            return body.get("status") == "ok"
        except Exception:
            return False
