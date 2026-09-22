"""Capability-based research API authentication.

Credentials travel only via headers or WebSocket subprotocols — never query
strings. Logs record capability codes and outcomes, never secrets.
"""

from __future__ import annotations

import hmac
import re
import secrets
from enum import StrEnum
from typing import Final

from fastapi import Request, WebSocket
from starlette.datastructures import Headers

from api.errors import bad_request, forbidden, unauthorized
from infrastructure.logging import get_logger
from infrastructure.settings import Settings

AUTH_HEADER: Final[str] = "x-palimpsest-token"
BEARER_PREFIX: Final[str] = "bearer "
WS_PROTOCOL_VERSION: Final[str] = "palimpsest.v1"
WS_TOKEN_PREFIX: Final[str] = "palimpsest.token."
_QUERY_SECRET_KEYS: Final[frozenset[str]] = frozenset(
    {
        "token",
        "credential",
        "credentials",
        "secret",
        "api_key",
        "apikey",
        "authorization",
        "password",
        "access_token",
    }
)
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._~\-+/=]{32,512}$")
_LOGGER = get_logger("api.security")


class ApiCapability(StrEnum):
    """Separate research capabilities (not a production authN system)."""

    SIMULATION_CONTROL = "simulation_control"
    OBJECTIVE_INSPECTION = "objective_inspection"
    AGENT_VISIBLE = "agent_visible"
    SUBJECTIVE_DEBUG = "subjective_debug"


def reject_query_string_secrets(query_keys: set[str]) -> None:
    """Fail closed when credential-like keys appear in the query string."""
    lowered = {key.lower() for key in query_keys}
    if lowered & _QUERY_SECRET_KEYS:
        _LOGGER.warning("auth_query_secret_rejected", reason_code="query_string_secret")
        raise bad_request(code="query_string_secret")


def extract_http_credential(headers: Headers) -> str | None:
    """Read credential from capability header or Authorization Bearer."""
    raw = headers.get(AUTH_HEADER)
    if raw is not None and raw.strip():
        return raw.strip()
    authorization = headers.get("authorization")
    if authorization is None:
        return None
    value = authorization.strip()
    if value.lower().startswith(BEARER_PREFIX):
        token = value[len(BEARER_PREFIX) :].strip()
        return token or None
    return None


def extract_websocket_credential(
    headers: Headers, *, subprotocols: list[str]
) -> tuple[str | None, list[str]]:
    """Extract credential from header or ``palimpsest.token.*`` subprotocol.

    Returns ``(credential, accept_protocols)`` where accept_protocols never
    echoes the secret-bearing subprotocol — only ``palimpsest.v1``.
    """
    header_token = extract_http_credential(headers)
    accepted: list[str] = []
    if WS_PROTOCOL_VERSION in subprotocols:
        accepted.append(WS_PROTOCOL_VERSION)
    token_from_protocol: str | None = None
    for item in subprotocols:
        if item.startswith(WS_TOKEN_PREFIX):
            candidate = item[len(WS_TOKEN_PREFIX) :]
            if candidate:
                token_from_protocol = candidate
    if header_token and token_from_protocol and header_token != token_from_protocol:
        _LOGGER.warning("auth_ws_token_mismatch", reason_code="credential_mismatch")
        raise unauthorized(code="credential_mismatch")
    return header_token or token_from_protocol, accepted


def _configured_secret(settings: Settings, capability: ApiCapability) -> str | None:
    if capability is ApiCapability.SIMULATION_CONTROL:
        secret = settings.api_control_credential
    elif capability is ApiCapability.OBJECTIVE_INSPECTION:
        secret = settings.api_inspection_credential
    elif capability is ApiCapability.AGENT_VISIBLE:
        secret = settings.api_agent_visible_credential
    elif capability is ApiCapability.SUBJECTIVE_DEBUG:
        secret = settings.api_debug_credential
    else:
        return None
    if secret is None:
        return None
    return secret.get_secret_value()


def _constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def require_capability(
    settings: Settings,
    *,
    capability: ApiCapability,
    presented: str | None,
    query_keys: set[str] | None = None,
) -> None:
    """Enforce capability gate. Debug is never open when disabled."""
    if query_keys is not None:
        reject_query_string_secrets(query_keys)

    if capability is ApiCapability.SUBJECTIVE_DEBUG:
        if not settings.api_debug_enabled:
            _LOGGER.warning(
                "auth_debug_disabled",
                capability=capability.value,
                reason_code="debug_disabled",
            )
            raise forbidden(code="debug_disabled")
        expected = _configured_secret(settings, capability)
        if expected is None:
            _LOGGER.error(
                "auth_debug_misconfigured",
                capability=capability.value,
                reason_code="debug_misconfigured",
            )
            raise forbidden(code="debug_misconfigured")
        if presented is None or not _TOKEN_RE.fullmatch(presented):
            raise unauthorized(code="missing_credential")
        if not _constant_time_equals(presented, expected):
            _LOGGER.warning(
                "auth_rejected",
                capability=capability.value,
                reason_code="invalid_credential",
            )
            raise unauthorized(code="invalid_credential")
        _LOGGER.debug("auth_granted", capability=capability.value)
        return

    expected = _configured_secret(settings, capability)
    if expected is None:
        if settings.api_auth_required:
            _LOGGER.error(
                "auth_misconfigured",
                capability=capability.value,
                reason_code="credential_unset",
            )
            raise forbidden(code="auth_misconfigured")
        _LOGGER.debug(
            "auth_open_local",
            capability=capability.value,
            reason_code="credential_unset",
        )
        return

    if presented is None or not _TOKEN_RE.fullmatch(presented):
        raise unauthorized(code="missing_credential")
    if not _constant_time_equals(presented, expected):
        _LOGGER.warning(
            "auth_rejected",
            capability=capability.value,
            reason_code="invalid_credential",
        )
        raise unauthorized(code="invalid_credential")
    _LOGGER.debug("auth_granted", capability=capability.value)


def require_http_capability(
    request: Request,
    settings: Settings,
    *,
    capability: ApiCapability,
) -> None:
    reject_query_string_secrets(set(request.query_params.keys()))
    presented = extract_http_credential(request.headers)
    require_capability(
        settings,
        capability=capability,
        presented=presented,
        query_keys=set(request.query_params.keys()),
    )


def require_websocket_capability(
    websocket: WebSocket,
    settings: Settings,
    *,
    capability: ApiCapability,
) -> list[str]:
    """Authenticate before accept. Returns subprotocols safe to accept."""
    query_keys = set(websocket.query_params.keys())
    reject_query_string_secrets(query_keys)
    subprotocols = list(websocket.scope.get("subprotocols") or [])
    presented, accepted = extract_websocket_credential(
        websocket.headers, subprotocols=subprotocols
    )
    require_capability(
        settings,
        capability=capability,
        presented=presented,
        query_keys=query_keys,
    )
    return accepted


def generate_operation_id() -> str:
    """Operational correlation id for manager/lease operations."""
    return secrets.token_hex(12)
