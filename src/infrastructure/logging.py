"""Idempotent stdlib and structlog integration.

Importing this module does not configure logging. Operational timestamps
are UTC metadata and must never become simulation IDs or seeds.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Final, TextIO, cast

import structlog
from structlog.stdlib import BoundLogger
from structlog.typing import EventDict, Processor, WrappedLogger

from infrastructure.settings import Settings, redact_secrets

OWNED_HANDLER_NAME: Final[str] = "palimpsest"
_LOCK = threading.Lock()
_SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "authorization",
        "body",
        "credential",
        "credentials",
        "database_url",
        "dsn",
        "embedding",
        "embeddings",
        "memory",
        "memories",
        "password",
        "prompt",
        "raw_response",
        "secret",
        "settings",
        "test_database_url",
        "token",
    }
)


def _redact_event(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    for key, value in list(event_dict.items()):
        lowered = key.lower()
        if lowered in _SENSITIVE_KEYS or any(
            part in lowered for part in ("password", "secret", "token", "embedding")
        ):
            event_dict[key] = "***"
        elif isinstance(value, Settings):
            event_dict[key] = value.bootstrap_fields()
        elif isinstance(value, str):
            event_dict[key] = redact_secrets(value)
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
