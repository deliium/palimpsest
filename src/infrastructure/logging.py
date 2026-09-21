"""Idempotent stdlib and structlog integration.

Importing this module does not configure logging. Operational timestamps
are UTC metadata and must never become simulation IDs or seeds.

Defense-in-depth redaction here is not the LLM provider's primary safety
mechanism; adapters must already emit metadata-only fields.
"""

from __future__ import annotations

import logging
import re
import sys
import threading
from collections.abc import Mapping, Sequence
from typing import Final, TextIO, cast

import structlog
from structlog.stdlib import BoundLogger
from structlog.typing import EventDict, Processor, WrappedLogger

from infrastructure.settings import Settings, redact_secrets

OWNED_HANDLER_NAME: Final[str] = "palimpsest"
_LOCK = threading.Lock()
_SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "api_key",
        "authorization",
        "base_url",
        "body",
        "credential",
        "credentials",
        "database_url",
        "dsn",
        "embedding",
        "embeddings",
        "endpoint",
        "endpoint_url",
        "headers",
        "llm_api_key",
        "llm_base_url",
        "memories",
        "memory",
        "messages",
        "output",
        "password",
        "prompt",
        "raw_response",
        "request_body",
        "response_body",
        "schema",
        "schemas",
        "secret",
        "settings",
        "test_database_url",
        "token",
        "url",
        "validated_output",
        "variables",
    }
)
_SENSITIVE_SUBSTRINGS: Final[tuple[str, ...]] = (
    "authorization",
    "embedding",
    "password",
    "secret",
)
_API_KEY_IN_TEXT: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(sk-[A-Za-z0-9\-_]{8,}|bearer\s+[A-Za-z0-9\-._~+/]+=*)"
)


def _key_is_sensitive(key: str) -> bool:
    lowered = key.lower()
    # Boolean presence diagnostics such as ``has_llm_api_key`` stay visible.
    if lowered.startswith("has_"):
        return False
    if lowered in _SENSITIVE_KEYS:
        return True
    if "api_key" in lowered or any(part in lowered for part in _SENSITIVE_SUBSTRINGS):
        return True
    # Match credential-like ``*_token`` keys without redacting usage ``*_tokens``.
    return lowered.endswith("_token") and not lowered.endswith("_tokens")


def _redact_string(value: str) -> str:
    redacted = redact_secrets(value)
    return _API_KEY_IN_TEXT.sub("***", redacted)


def _redact_value(value: object) -> object:
    """Redact strings and nested containers without claiming primary safety."""
    if isinstance(value, Settings):
        return value.bootstrap_fields()
    if isinstance(value, Mapping):
        return {
            key: (
                "***"
                if _key_is_sensitive(str(key))
                else _redact_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, (bytes, bytearray)):
        return b"***"
    return value


def _redact_event(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    for key, value in list(event_dict.items()):
        if _key_is_sensitive(key):
            event_dict[key] = "***"
        else:
            event_dict[key] = _redact_value(value)
    return event_dict


def _shared_processors() -> list[Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        _redact_event,
    ]


def _owned_handler(root: logging.Logger) -> logging.Handler | None:
    for handler in root.handlers:
        if getattr(handler, "name", None) == OWNED_HANDLER_NAME:
            return handler
    return None


def _silence_uvicorn_access_duplicates() -> None:
    """Uvicorn access logs would duplicate application request records."""
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.setLevel(logging.WARNING)
    access.propagate = True


def configure_logging(
    settings: Settings, *, stream: TextIO | None = None
) -> logging.Handler:
    """Configure stdlib + structlog once. Repeated calls reuse one owned handler."""
    with _LOCK:
        return _configure_locked(settings, stream)


def _configure_locked(settings: Settings, stream: TextIO | None) -> logging.Handler:
    level = getattr(logging, settings.log_level.value)
    shared = _shared_processors()
    renderer: Processor
    if settings.json_logs():
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared,
    )

    root = logging.getLogger()
    owned = _owned_handler(root)
    if owned is None:
        owned = logging.StreamHandler(stream if stream is not None else sys.stderr)
        owned.name = OWNED_HANDLER_NAME
        root.addHandler(owned)
    elif stream is not None and isinstance(owned, logging.StreamHandler):
        owned.setStream(stream)
    owned.setFormatter(formatter)
    owned.setLevel(level)
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)
    _silence_uvicorn_access_duplicates()

    log = structlog.get_logger("infrastructure.logging")
    log.debug("logging_configured", **settings.bootstrap_fields())
    log.info(
        "logging_ready",
        environment=settings.environment.value,
        log_level=settings.log_level.value,
    )
    return owned


def get_logger(name: str = "palimpsest") -> BoundLogger:
    return cast(BoundLogger, structlog.get_logger(name))


def bind_log_context(**values: str | int) -> None:
    structlog.contextvars.bind_contextvars(**values)


def clear_log_context() -> None:
    structlog.contextvars.clear_contextvars()


def log_bootstrap(settings: Settings) -> None:
    get_logger("infrastructure.settings").debug(
        "settings_loaded", **settings.bootstrap_fields()
    )


def log_lifecycle(event: str, **fields: str | int | bool) -> None:
    get_logger("infrastructure.lifecycle").info(event, **fields)


def log_recoverable(reason: str) -> None:
    get_logger("infrastructure").warning(
        "recoverable_inconsistency", reason=redact_secrets(reason)
    )


def log_setup_failure(reason: str) -> None:
    get_logger("infrastructure").error("setup_failed", reason=redact_secrets(reason))


def reset_logging_for_tests(
    original_handlers: list[logging.Handler], original_level: int
) -> None:
    """Restore root handlers after a logging test. Not used at runtime."""
    structlog.reset_defaults()
    clear_log_context()
    root = logging.getLogger()
    root.handlers = list(original_handlers)
    root.setLevel(original_level)
