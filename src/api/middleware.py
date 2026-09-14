"""Request correlation middleware. Request IDs are operational metadata."""

from __future__ import annotations

import re
import secrets
import time
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from infrastructure.logging import bind_log_context, clear_log_context, get_logger

REQUEST_ID_HEADER: Final[str] = "x-request-id"
_MAX_REQUEST_ID_LENGTH: Final[int] = 128
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_LOGGER = get_logger("api.request")


def generate_request_id() -> str:
    """Operational correlation id. Never a simulation id, seed, or event id."""
    return secrets.token_hex(16)


def resolve_request_id(raw: str | None) -> tuple[str, bool]:
    """Return ``(request_id, malformed)``. Reject unbounded or unsafe values."""
    if raw is None or raw == "":
        return generate_request_id(), False
    candidate = raw.strip()
    if len(candidate) > _MAX_REQUEST_ID_LENGTH or not _SAFE_REQUEST_ID.fullmatch(
        candidate
    ):
        return generate_request_id(), True
    return candidate, False


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inbound = _header_value(scope, REQUEST_ID_HEADER)
        request_id, malformed = resolve_request_id(inbound)
        if malformed:
            _LOGGER.warning("malformed_request_id", reason="rejected_inbound_value")
        bind_log_context(request_id=request_id)
        method = str(scope.get("method", ""))
        path = str(scope.get("path", ""))
        started = time.perf_counter()
        _LOGGER.debug(
            "request_started",
            method=method,
            path=path,
            request_id=request_id,
        )
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            _LOGGER.error(
                "unhandled_failure",
                method=method,
                path=path,
                request_id=request_id,
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            _LOGGER.debug(
                "request_completed",
                method=method,
                path=path,
                status=status_code,
                duration_ms=duration_ms,
                request_id=request_id,
            )
            clear_log_context()


def _header_value(scope: Scope, name: str) -> str | None:
    expected = name.lower().encode("ascii")
    for key, value in scope.get("headers") or []:
        if key == expected:
            return bytes(value).decode("latin-1")
    return None
