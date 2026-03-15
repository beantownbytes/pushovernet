import argparse
import dataclasses
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
from pydantic import BaseModel

from pushovernet.client import PushoverClient
from pushovernet.config import ServerConfig
from pushovernet.exceptions import (
    PushoverAPIError,
    PushoverHTTPError,
    PushoverRateLimitError,
)


class SendRequest(BaseModel):
    message: str
    title: Optional[str] = None
    device: Optional[str] = None
    priority: Optional[int] = None
    sound: Optional[str] = None
    timestamp: Optional[int] = None
    ttl: Optional[int] = None
    url: Optional[str] = None
    url_title: Optional[str] = None
    html: Optional[bool] = None
    monospace: Optional[bool] = None
    retry: Optional[int] = None
    expire: Optional[int] = None
    callback: Optional[str] = None
    tags: Optional[str] = None
    attachment_base64: Optional[str] = None
    attachment_type: Optional[str] = None


class GlanceRequest(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    subtext: Optional[str] = None
    count: Optional[int] = None
    percent: Optional[int] = None
    device: Optional[str] = None


_server_config: ServerConfig = ServerConfig()


def _require_api_key(x_api_key: Optional[str] = Header(None)):
    if not _server_config.api_key:
        return
    if x_api_key != _server_config.api_key:
        raise fastapi.HTTPException(status_code=401, detail="Invalid or missing API key")


def create_app(config_path: str | None = None) -> FastAPI:
    global _server_config
    _server_config = ServerConfig.load(config_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        client = PushoverClient(config_path=config_path)
        application.state.client = client
        yield
        client.close()

    application = FastAPI(title="pushovernet", lifespan=lifespan)

    @application.exception_handler(PushoverRateLimitError)
    async def handle_rate_limit(request: Request, exc: PushoverRateLimitError):
        return JSONResponse(
            status_code=429,
            content={"errors": exc.errors, "reset_at": exc.reset_at},
        )

    @application.exception_handler(PushoverAPIError)
    async def handle_api_error(request: Request, exc: PushoverAPIError):
        return JSONResponse(
            status_code=422,
            content={"errors": exc.errors, "request_id": exc.request_id},
        )

    @application.exception_handler(PushoverHTTPError)
    async def handle_http_error(request: Request, exc: PushoverHTTPError):
        return JSONResponse(
            status_code=502,
            content={"error": str(exc)},
        )

    @application.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=422,
            content={"error": str(exc)},
        )

    @application.get("/health")
    def health():
        return {"status": "ok"}

    @application.post("/send", dependencies=[Depends(_require_api_key)])
    def send(body: SendRequest):
        client: PushoverClient = application.state.client
        resp = client.send_message(**body.model_dump(exclude_none=True))
        return dataclasses.asdict(resp)

    @application.post("/glance", dependencies=[Depends(_require_api_key)])
    def glance(body: GlanceRequest):
        client: PushoverClient = application.state.client
        return client.send_glance(**body.model_dump(exclude_none=True))

    @application.get("/sounds", dependencies=[Depends(_require_api_key)])
    def sounds():
        client: PushoverClient = application.state.client
        return {"sounds": client.list_sounds()}

    @application.get("/limits", dependencies=[Depends(_require_api_key)])
    def limits():
        client: PushoverClient = application.state.client
        result = client.get_limits()
        return dataclasses.asdict(result)

    return application


app = create_app()


def run():
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
