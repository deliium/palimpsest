"""API capability authentication and credential transport safety."""

from __future__ import annotations

import os

import pytest
from starlette.datastructures import Headers

from api.errors import ApiError
from api.security import (
    ApiCapability,
    AUTH_HEADER,
    WS_PROTOCOL_VERSION,
    WS_TOKEN_PREFIX,
    extract_http_credential,
    extract_websocket_credential,
    reject_query_string_secrets,
    require_capability,
)
from infrastructure.settings import Settings, load_settings

pytestmark = pytest.mark.unit

STRONG = "a" * 32
STRONG_B = "b" * 32
STRONG_C = "c" * 32
STRONG_D = "d" * 32


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PALIMPSEST_"):
            monkeypatch.delenv(key, raising=False)


def _settings(**overrides: object) -> Settings:
    return load_settings(env_file=False, **overrides)


def test_query_string_secrets_are_rejected() -> None:
    with pytest.raises(ApiError) as exc:
        reject_query_string_secrets({"token"})
    assert exc.value.code == "query_string_secret"
    with pytest.raises(ApiError):
        reject_query_string_secrets({"access_token"})


def test_header_and_bearer_extraction() -> None:
    headers = Headers({AUTH_HEADER: STRONG})
    assert extract_http_credential(headers) == STRONG
    bearer = Headers({"authorization": f"Bearer {STRONG}"})
    assert extract_http_credential(bearer) == STRONG


def test_websocket_subprotocol_token_and_version() -> None:
    headers = Headers({})
    token, accepted = extract_websocket_credential(
        headers,
        subprotocols=[WS_PROTOCOL_VERSION, f"{WS_TOKEN_PREFIX}{STRONG}"],
    )
    assert token == STRONG
    assert accepted == [WS_PROTOCOL_VERSION]


def test_open_local_mode_grants_non_debug_without_credentials() -> None:
    settings = _settings(api_auth_required=False)
    require_capability(
        settings,
        capability=ApiCapability.SIMULATION_CONTROL,
        presented=None,
    )
    require_capability(
        settings,
        capability=ApiCapability.OBJECTIVE_INSPECTION,
        presented=None,
    )


def test_debug_disabled_by_default() -> None:
    settings = _settings()
    with pytest.raises(ApiError) as exc:
        require_capability(
            settings,
            capability=ApiCapability.SUBJECTIVE_DEBUG,
            presented=STRONG_D,
        )
    assert exc.value.code == "debug_disabled"


def test_auth_required_rejects_missing_and_wrong_credentials() -> None:
    settings = _settings(
        api_auth_required=True,
        api_control_credential=STRONG,
        api_inspection_credential=STRONG_B,
        api_agent_visible_credential=STRONG_C,
    )
    with pytest.raises(ApiError) as exc:
        require_capability(
            settings,
            capability=ApiCapability.SIMULATION_CONTROL,
            presented=None,
        )
    assert exc.value.code == "missing_credential"
    with pytest.raises(ApiError) as exc:
        require_capability(
            settings,
            capability=ApiCapability.SIMULATION_CONTROL,
            presented=STRONG_B,
        )
    assert exc.value.code == "invalid_credential"
    require_capability(
        settings,
        capability=ApiCapability.SIMULATION_CONTROL,
        presented=STRONG,
    )


def test_debug_requires_enabled_and_matching_credential() -> None:
    settings = _settings(
        api_debug_enabled=True,
        api_debug_credential=STRONG_D,
    )
    require_capability(
        settings,
        capability=ApiCapability.SUBJECTIVE_DEBUG,
        presented=STRONG_D,
    )
    with pytest.raises(ApiError):
        require_capability(
            settings,
            capability=ApiCapability.SUBJECTIVE_DEBUG,
            presented=STRONG,
        )
