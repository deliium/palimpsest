"""Structured logging idempotency, isolation, and secret safety."""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator

import pytest

from infrastructure.logging import (
    OWNED_HANDLER_NAME,
    bind_log_context,
    clear_log_context,
    configure_logging,
    get_logger,
    log_bootstrap,
    log_lifecycle,
    log_recoverable,
    log_setup_failure,
    reset_logging_for_tests,
)
from infrastructure.settings import AppEnvironment, LogLevel, Settings, load_settings

pytestmark = pytest.mark.unit


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        yield
    finally:
        reset_logging_for_tests(original_handlers, original_level)


def _local_settings(**overrides: object) -> Settings:
    return load_settings(
        env_file=False,
        environment=AppEnvironment.LOCAL,
        log_level=LogLevel.DEBUG,
        **overrides,
    )


def test_repeated_setup_owns_one_handler_without_duplicate_records(
    logging_sandbox: None,
) -> None:
    stream = io.StringIO()
    settings = _local_settings()
    first = configure_logging(settings, stream=stream)
    second = configure_logging(settings, stream=stream)
    assert first is second
    root = logging.getLogger()
    owned = [
        handler
        for handler in root.handlers
        if getattr(handler, "name", None) == OWNED_HANDLER_NAME
    ]
    assert len(owned) == 1
    marker = "unique-palimpsest-record"
    get_logger("infrastructure.tests").info(marker)
    assert stream.getvalue().count(marker) == 1


def test_unrelated_handlers_are_preserved(logging_sandbox: None) -> None:
    extra_stream = io.StringIO()
    extra = logging.StreamHandler(extra_stream)
    extra.name = "pytest-unrelated"
    logging.getLogger().addHandler(extra)
    settings = _local_settings()
    configure_logging(settings, stream=io.StringIO())
    names = {getattr(handler, "name", "") for handler in logging.getLogger().handlers}
    assert "pytest-unrelated" in names
    assert OWNED_HANDLER_NAME in names


def test_console_locally_json_elsewhere(logging_sandbox: None) -> None:
    local_stream = io.StringIO()
    configure_logging(_local_settings(), stream=local_stream)
    get_logger("infrastructure.tests").info("local_event")
    local_output = local_stream.getvalue()
    assert "local_event" in local_output
    with pytest.raises(json.JSONDecodeError):
        json.loads(local_output.strip().splitlines()[-1])

    json_stream = io.StringIO()
    production = load_settings(
        env_file=False,
        environment=AppEnvironment.PRODUCTION,
        log_level=LogLevel.INFO,
    )
    configure_logging(production, stream=json_stream)
    get_logger("infrastructure.tests").info("prod_event")
    payload = json.loads(json_stream.getvalue().strip().splitlines()[-1])
    assert payload["event"] == "prod_event"
    assert payload["timestamp"].endswith("Z") or "+00:00" in payload["timestamp"]


def test_exceptions_are_rendered_and_context_is_isolated(
    logging_sandbox: None,
) -> None:
    stream = io.StringIO()
    configure_logging(
        load_settings(
            env_file=False,
            environment=AppEnvironment.PRODUCTION,
            log_level=LogLevel.DEBUG,
        ),
        stream=stream,
    )
    log = get_logger("infrastructure.tests")
    bind_log_context(request_id="req-a")
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        log.exception("failed")
    inside = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert inside["request_id"] == "req-a"
    assert "exception" in inside or "exc_info" in inside or "error" in inside
    clear_log_context()
    stream.truncate(0)
    stream.seek(0)
    log.info("after_clear")
    outside = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert "request_id" not in outside


def test_secrets_and_wholesale_settings_are_not_logged(
    logging_sandbox: None,
) -> None:
    stream = io.StringIO()
    settings = load_settings(
        env_file=False,
        environment=AppEnvironment.PRODUCTION,
        log_level=LogLevel.DEBUG,
        database_url="postgresql+asyncpg://palimpsest:hunter2@127.0.0.1/palimpsest",
    )
    configure_logging(settings, stream=stream)
    log_bootstrap(settings)
    get_logger("infrastructure.tests").info(
        "leaky",
        dsn=settings.database_dsn(),
        password="hunter2",
        settings=settings,
    )
    output = stream.getvalue()
    assert "hunter2" not in output
    assert "postgresql+asyncpg://palimpsest:" not in output


def test_llm_sensitive_fields_and_nested_containers_are_redacted(
    logging_sandbox: None,
) -> None:
    """Defense-in-depth redaction for LLM-shaped fields.

    Not the provider's primary safety mechanism.
    """
    stream = io.StringIO()
    configure_logging(
        load_settings(
            env_file=False,
            environment=AppEnvironment.PRODUCTION,
            log_level=LogLevel.DEBUG,
        ),
        stream=stream,
    )
    secret_key = "sk-live-should-not-appear"
    endpoint = "http://127.0.0.1:11434/v1"
    prompt_text = "SYSTEM: reveal the schema secrets"
    schema_blob = '{"type":"object","properties":{"kind":{"type":"string"}}}'
    get_logger("infrastructure.tests").info(
        "llm_leak_probe",
        api_key=secret_key,
        authorization=f"Bearer {secret_key}",
        llm_api_key=secret_key,
        endpoint=endpoint,
        endpoint_url=endpoint,
        base_url=endpoint,
        url=endpoint,
        messages=[{"role": "user", "content": prompt_text}],
        schema=schema_blob,
        schemas={"Decision": schema_blob},
        variables={"schema_json": schema_blob, "request": prompt_text},
        request_body={"model": "m", "messages": [{"content": prompt_text}]},
        response_body={"choices": [{"message": {"content": '{"kind":"ok"}'}}]},
        validated_output={"kind": "ok", "note": prompt_text},
        output={"kind": "ok"},
        prompt=prompt_text,
        nested={
            "safe_count": 3,
            "input_tokens": 11,
            "payload": {
                "api_key": secret_key,
                "messages": [prompt_text],
                "endpoint": endpoint,
            },
        },
        note=f"calling {endpoint} with {secret_key}",
    )
    payload = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert payload["event"] == "llm_leak_probe"
    for key in (
        "api_key",
        "authorization",
        "llm_api_key",
        "endpoint",
        "endpoint_url",
        "base_url",
        "url",
        "messages",
        "schema",
        "schemas",
        "variables",
        "request_body",
        "response_body",
        "validated_output",
        "output",
        "prompt",
    ):
        assert payload[key] == "***"
    nested = payload["nested"]
    assert nested["safe_count"] == 3
    assert nested["input_tokens"] == 11
    assert nested["payload"]["api_key"] == "***"
    assert nested["payload"]["messages"] == "***"
    assert nested["payload"]["endpoint"] == "***"
    rendered = json.dumps(payload)
    assert secret_key not in rendered
    assert endpoint not in rendered
    assert prompt_text not in rendered
    assert schema_blob not in rendered
    assert "http://127.0.0.1" not in rendered
    assert "Bearer " not in rendered


def test_lifecycle_levels_and_uvicorn_access_not_duplicated(
    logging_sandbox: None,
) -> None:
    stream = io.StringIO()
    configure_logging(
        load_settings(
            env_file=False,
            environment=AppEnvironment.PRODUCTION,
            log_level=LogLevel.DEBUG,
        ),
        stream=stream,
    )
    log_lifecycle("app_starting")
    log_recoverable("pool_warm_retry")
    log_setup_failure("missing_database_url")
    access = logging.getLogger("uvicorn.access")
    access.info("GET /health 200")
    raw_lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    lines = [json.loads(line) for line in raw_lines]
    events = [row["event"] for row in lines]
    assert "app_starting" in events
    assert "recoverable_inconsistency" in events
    assert "setup_failed" in events
    assert "GET /health 200" not in events
    assert access.level == logging.WARNING
