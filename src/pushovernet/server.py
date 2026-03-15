import argparse
import dataclasses
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

try:
    import fastapi
    import uvicorn
except ImportError:
    raise ImportError(
        "Server dependencies not installed. Install with: pip install pushovernet[server]"
    )

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pushovernet.client import PushoverClient
from pushovernet.config import ServerConfig
from pushovernet.exceptions import (
    PushoverAPIError,
    PushoverHTTPError,
    PushoverRateLimitError,
)


class SendRequest(BaseModel):
    model_config = {"json_schema_extra": {"examples": [{"message": "Server backup complete", "title": "Backup Status"}]}}

    message: str
    title: Optional[str] = Field(None, description="Notification title. Defaults to app name if omitted.")
    device: Optional[str] = Field(None, description="Target device name. Sends to all devices if omitted.")
    priority: Optional[int] = Field(None, description="Priority: -2 (lowest), -1 (low), 0 (normal), 1 (high), 2 (emergency).")
    sound: Optional[str] = Field(None, description="Notification sound name. Use GET /sounds for available options.")
    timestamp: Optional[int] = Field(None, description="Unix timestamp to display instead of time received.")
    ttl: Optional[int] = Field(None, description="Time to live in seconds. Message deleted from devices after expiry.")
    url: Optional[str] = Field(None, description="Supplementary URL to include with the message.")
    url_title: Optional[str] = Field(None, description="Display title for the supplementary URL.")
    html: Optional[bool] = Field(None, description="Enable HTML formatting in the message body.")
    monospace: Optional[bool] = Field(None, description="Display message in monospace font.")
    retry: Optional[int] = Field(None, description="Emergency priority only. Retry interval in seconds (minimum 30).")
    expire: Optional[int] = Field(None, description="Emergency priority only. Expiration in seconds (maximum 10800).")
    callback: Optional[str] = Field(None, description="Emergency priority only. URL to POST to when user acknowledges.")
    tags: Optional[str] = Field(None, description="Comma-separated tags for bulk cancellation of emergency notifications.")
    attachment_base64: Optional[str] = Field(None, description="Base64-encoded image attachment.")
    attachment_type: Optional[str] = Field(None, description="MIME type of the attachment (e.g. image/png).")


class GlanceRequest(BaseModel):
    model_config = {"json_schema_extra": {"examples": [{"title": "Queue", "count": 42}]}}

    title: Optional[str] = Field(None, description="Title (max 100 chars).")
    text: Optional[str] = Field(None, description="Main line of data (max 100 chars).")
    subtext: Optional[str] = Field(None, description="Second line of data (max 100 chars).")
    count: Optional[int] = Field(None, description="Integer value shown on the glance widget.")
    percent: Optional[int] = Field(None, description="Percentage value (0-100) shown on the glance widget.")
    device: Optional[str] = Field(None, description="Target device name.")


_server_config: ServerConfig = ServerConfig()


def _require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    if not _server_config.api_key:
        return
    if x_api_key != _server_config.api_key:
        raise fastapi.HTTPException(status_code=401, detail="Invalid or missing API key")


def create_app(config_path: str | None = None) -> FastAPI:
    global _server_config
    _server_config = ServerConfig.load(config_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        client = PushoverClient(config_path=config_path)
        application.state.client = client
        yield
        client.close()

    application = FastAPI(
        title="pushovernet",
        description="Local proxy server for the Pushover.net notification API. "
        "Allows LAN devices to send push notifications without knowing Pushover credentials.",
        version="0.1.1",
        lifespan=lifespan,
    )

    @application.exception_handler(PushoverRateLimitError)
    async def handle_rate_limit(request: Request, exc: PushoverRateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"errors": exc.errors, "reset_at": exc.reset_at},
        )

    @application.exception_handler(PushoverAPIError)
    async def handle_api_error(request: Request, exc: PushoverAPIError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"errors": exc.errors, "request_id": exc.request_id},
        )

    @application.exception_handler(PushoverHTTPError)
    async def handle_http_error(request: Request, exc: PushoverHTTPError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"error": str(exc)},
        )

    @application.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": str(exc)},
        )

    @application.get("/health", summary="Health check", description="Returns server status. Does not require API key.")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/send", dependencies=[Depends(_require_api_key)], summary="Send notification", description="Send a push notification via the Pushover API. Supports all message options including priority levels, sounds, URLs, HTML formatting, and attachments.")
    def send(body: SendRequest) -> dict[str, str | int | None]:
        client: PushoverClient = application.state.client
        resp = client.send_message(**body.model_dump(exclude_none=True))
        return dataclasses.asdict(resp)

    @application.post("/glance", dependencies=[Depends(_require_api_key)], summary="Send glance data", description="Update a Pushover glance widget with data. At least one data field (title, text, subtext, count, percent) must be provided.")
    def glance(body: GlanceRequest) -> dict[str, str | int]:
        client: PushoverClient = application.state.client
        result: dict[str, str | int] = client.send_glance(**body.model_dump(exclude_none=True))
        return result

    @application.get("/sounds", dependencies=[Depends(_require_api_key)], summary="List sounds", description="List all available notification sounds and their display names.")
    def sounds() -> dict[str, dict[str, str]]:
        client: PushoverClient = application.state.client
        return {"sounds": client.list_sounds()}

    @application.get("/limits", dependencies=[Depends(_require_api_key)], summary="Rate limits", description="Get current application rate limit status including total limit, remaining calls, and reset timestamp.")
    def limits() -> dict[str, int]:
        client: PushoverClient = application.state.client
        result = client.get_limits()
        return dataclasses.asdict(result)

    return application


app = create_app()


def run() -> None:
    parser = argparse.ArgumentParser(description="pushovernet notification proxy server")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    server_config = ServerConfig.load(args.config)
    host = args.host or server_config.host
    port = args.port or server_config.port

    application = create_app(args.config)
    uvicorn.run(application, host=host, port=port)
