"""Application settings. Importing this module does not read secrets or connect.

LLM settings (``PALIMPSEST_LLM_*``) are disabled by default. A future cognition
consumer owns mapping these values into ``llm.factory`` and provider lifecycle;
this module never imports ``llm`` and never opens sockets.
"""

from __future__ import annotations

import math
import re
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Final, Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOG_LEVEL_ENV: Final[str] = "PALIMPSEST_LOG_LEVEL"
SETTINGS_PREFIX: Final[str] = "PALIMPSEST_"
TEST_DATABASE_MARKER: Final[str] = "palimpsest_test"
_SYSTEM_DATABASES: Final[frozenset[str]] = frozenset(
    {"postgres", "template0", "template1"}
)
_ASYNC_SCHEME: Final[str] = "postgresql+asyncpg://"
_CREDENTIALS_IN_URL = re.compile(r"(://[^:/?#]+:)([^@]+)(@)")
_PASSWORD_ASSIGNMENT = re.compile(
    r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*\S+"
)
_HTTP_URL = re.compile(r"https?://[^\s'\"\\]+")
_LLM_MODEL_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)
_LOCAL_HTTP_HOSTS: Final[frozenset[str]] = frozenset({"localhost", "127.0.0.1", "::1"})
_DEFAULT_LLM_MAX_REQUEST_BYTES: Final[int] = 1_048_576
_DEFAULT_LLM_MAX_RESPONSE_BYTES: Final[int] = 1_048_576
_DEFAULT_LLM_MAX_HEADER_BYTES: Final[int] = 8_192
_DEFAULT_API_MAX_PAGE_SIZE: Final[int] = 100
_DEFAULT_API_STREAM_QUEUE_SIZE: Final[int] = 64
_DEFAULT_OBSERVER_STREAM_QUEUE_SIZE: Final[int] = 64
_DEFAULT_OBSERVER_CATCHUP_PAGE_SIZE: Final[int] = 50
_DEFAULT_MEMORY_RETRIEVE_MAX_CANDIDATES: Final[int] = 4_096
_DEFAULT_LLM_MAX_CONCURRENCY: Final[int] = 1
_DEFAULT_API_STREAM_HEARTBEAT_SECONDS: Final[float] = 15.0
_DEFAULT_API_STREAM_POLL_SECONDS: Final[float] = 0.25
_DEFAULT_API_LEASE_TTL_SECONDS: Final[float] = 30.0
_DEFAULT_API_LEASE_HEARTBEAT_SECONDS: Final[float] = 10.0
_DEFAULT_API_DRAIN_TIMEOUT_SECONDS: Final[float] = 30.0
_MIN_API_CREDENTIAL_LENGTH: Final[int] = 32
_MAX_MEMORY_RETRIEVE_MAX_CANDIDATES: Final[int] = 100_000
_MAX_LLM_MAX_CONCURRENCY: Final[int] = 256


class SettingsError(Exception):
    """Raised when settings are invalid. Messages never include credentials."""


class AppEnvironment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LlmAdapterKind(StrEnum):
    """Settings-side adapter selector. Aligns with ``llm.factory`` kinds."""

    DISABLED = "disabled"
    OPENAI_COMPATIBLE = "openai_compatible"


class LlmStructuredOutputMode(StrEnum):
    """Settings-side structured-output mode. Aligns with ``llm`` modes."""

    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"
    PROMPT_ONLY = "prompt_only"


def redact_secrets(text: str) -> str:
    """Strip URL credentials and DSN-like values from diagnostic text."""
    redacted = _CREDENTIALS_IN_URL.sub(r"\1***\2", text)
    redacted = re.sub(
        re.escape(_ASYNC_SCHEME) + r"[^\s'\"\\]+",
        f"{_ASYNC_SCHEME}***",
        redacted,
    )
    redacted = re.sub(r"postgresql://[^\s'\"\\]+", "postgresql://***", redacted)
    redacted = _HTTP_URL.sub("http(s)://***", redacted)
    return _PASSWORD_ASSIGNMENT.sub(r"\1=***", redacted)


def _reject_bool(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("booleans are not valid integer settings")
    return value


def _settings_error_from_validation(exc: ValidationError) -> SettingsError:
    """Build a SettingsError without Pydantic input values or context."""
    parts: list[str] = []
    for err in exc.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    ):
        loc = ".".join(str(item) for item in err.get("loc", ()))
        msg = str(err.get("msg", "invalid value"))
        if loc:
            parts.append(f"{loc}: {msg}")
        else:
            parts.append(msg)
    message = "; ".join(parts) if parts else "invalid settings"
    return SettingsError(redact_secrets(message))


class Settings(BaseSettings):
    """Typed configuration. Instantiate via ``load_settings``; not at import time.

    LLM fields are disabled by default. A future cognition consumer owns
    settings-to-``llm.factory`` mapping and provider lifecycle; this module
    does not construct providers.
    """

    model_config = SettingsConfigDict(
        env_prefix=SETTINGS_PREFIX,
        env_file=None,
        extra="forbid",
        frozen=True,
        case_sensitive=False,
    )

    environment: AppEnvironment = AppEnvironment.LOCAL
    log_level: LogLevel = LogLevel.INFO
    api_host: str = "127.0.0.1"
    api_port: Annotated[int, Field(ge=1, le=65535)] = 8080
    database_url: SecretStr | None = Field(default=None, repr=False)
    test_database_url: SecretStr | None = Field(default=None, repr=False)
    pool_size: Annotated[int, Field(ge=1)] = 5
    max_overflow: Annotated[int, Field(ge=0)] = 10
    pool_timeout_seconds: Annotated[float, Field(gt=0)] = 30.0
    default_run_seed: int | None = None

    llm_adapter_kind: LlmAdapterKind = LlmAdapterKind.DISABLED
    llm_model: str | None = Field(default=None, repr=False)
    llm_base_url: SecretStr | None = Field(default=None, repr=False)
    llm_api_key: SecretStr | None = Field(default=None, repr=False)
    llm_structured_output_mode: LlmStructuredOutputMode = (
        LlmStructuredOutputMode.JSON_SCHEMA
    )
    llm_temperature: float | None = None
    llm_max_attempts: Annotated[int, Field(ge=1)] = 3
    llm_per_attempt_timeout_seconds: Annotated[float, Field(gt=0)] = 30.0
    llm_total_deadline_seconds: float | None = None
    llm_max_request_bytes: Annotated[int, Field(ge=1)] = _DEFAULT_LLM_MAX_REQUEST_BYTES
    llm_max_response_bytes: Annotated[int, Field(ge=1)] = (
        _DEFAULT_LLM_MAX_RESPONSE_BYTES
    )
    llm_max_header_bytes: Annotated[int, Field(ge=1)] = _DEFAULT_LLM_MAX_HEADER_BYTES
    llm_send_correlation_header: bool = False

    # Research API (PALIMPSEST_API_*). Debug is disabled by default.
    api_auth_required: bool = False
    api_control_credential: SecretStr | None = Field(default=None, repr=False)
    api_inspection_credential: SecretStr | None = Field(default=None, repr=False)
    api_agent_visible_credential: SecretStr | None = Field(default=None, repr=False)
    api_debug_enabled: bool = False
    api_debug_credential: SecretStr | None = Field(default=None, repr=False)
    api_max_page_size: Annotated[
        int, Field(ge=1, le=1000)
    ] = _DEFAULT_API_MAX_PAGE_SIZE
    api_stream_queue_size: Annotated[int, Field(ge=1, le=10_000)] = (
        _DEFAULT_API_STREAM_QUEUE_SIZE
    )
    api_stream_heartbeat_seconds: Annotated[float, Field(gt=0)] = (
        _DEFAULT_API_STREAM_HEARTBEAT_SECONDS
    )
    api_stream_poll_seconds: Annotated[float, Field(gt=0)] = (
        _DEFAULT_API_STREAM_POLL_SECONDS
    )
    api_lease_ttl_seconds: Annotated[float, Field(gt=0)] = (
        _DEFAULT_API_LEASE_TTL_SECONDS
    )
    api_lease_heartbeat_seconds: Annotated[float, Field(gt=0)] = (
        _DEFAULT_API_LEASE_HEARTBEAT_SECONDS
    )
    api_drain_timeout_seconds: Annotated[float, Field(gt=0)] = (
        _DEFAULT_API_DRAIN_TIMEOUT_SECONDS
    )
    # Long-experiment scale knobs (defaults preserve short-run behavior).
    # These never imply in-DB DELETE of snapshots, stream records, or traces.
    observer_stream_queue_size: Annotated[int, Field(ge=1, le=10_000)] = (
        _DEFAULT_OBSERVER_STREAM_QUEUE_SIZE
    )
    observer_catchup_page_size: Annotated[int, Field(ge=1, le=1000)] = (
        _DEFAULT_OBSERVER_CATCHUP_PAGE_SIZE
    )
    memory_retrieve_max_candidates: Annotated[
        int, Field(ge=1, le=_MAX_MEMORY_RETRIEVE_MAX_CANDIDATES)
    ] = _DEFAULT_MEMORY_RETRIEVE_MAX_CANDIDATES
    llm_max_concurrency: Annotated[int, Field(ge=1, le=_MAX_LLM_MAX_CONCURRENCY)] = (
        _DEFAULT_LLM_MAX_CONCURRENCY
    )
    cognition_trace_soft_cap_invocations: Annotated[int | None, Field(ge=1)] = None
    cognition_trace_soft_cap_bytes: Annotated[int | None, Field(ge=1)] = None
    presentation_web_root: Path | None = None
    revision: str = ""

    @field_validator(
        "api_port",
        "pool_size",
        "max_overflow",
        "default_run_seed",
        "llm_max_attempts",
        "llm_max_request_bytes",
        "llm_max_response_bytes",
        "llm_max_header_bytes",
        "api_max_page_size",
        "api_stream_queue_size",
        "observer_stream_queue_size",
        "observer_catchup_page_size",
        "memory_retrieve_max_candidates",
        "llm_max_concurrency",
        "cognition_trace_soft_cap_invocations",
        "cognition_trace_soft_cap_bytes",
        mode="before",
    )
    @classmethod
    def reject_boolean_integers(cls, value: object) -> object:
        return _reject_bool(value)

    @field_validator(
        "pool_timeout_seconds",
        "llm_temperature",
        "llm_per_attempt_timeout_seconds",
        "llm_total_deadline_seconds",
        "api_stream_heartbeat_seconds",
        "api_stream_poll_seconds",
        "api_lease_ttl_seconds",
        "api_lease_heartbeat_seconds",
        "api_drain_timeout_seconds",
        mode="before",
    )
    @classmethod
    def reject_boolean_floats(cls, value: object) -> object:
        return _reject_bool(value)

    @field_validator("presentation_web_root", mode="before")
    @classmethod
    def empty_presentation_root_is_unset(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("revision", mode="before")
    @classmethod
    def blank_revision_is_unset(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        raise ValueError("revision must be a string")

    @field_validator("default_run_seed")
    @classmethod
    def reject_negative_seed(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("default_run_seed must be a non-negative integer")
        return value

    @field_validator("llm_temperature")
    @classmethod
    def validate_llm_temperature(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("llm_temperature must be a finite number")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("llm_temperature must be finite")
        if number < 0.0 or number > 2.0:
            raise ValueError("llm_temperature out of range")
        return number

    @field_validator("llm_per_attempt_timeout_seconds")
    @classmethod
    def validate_llm_per_attempt_timeout(cls, value: float) -> float:
        if not math.isfinite(float(value)):
            raise ValueError("llm_per_attempt_timeout_seconds must be finite")
        return float(value)

    @field_validator("llm_total_deadline_seconds")
    @classmethod
    def validate_llm_total_deadline(cls, value: float | None) -> float | None:
        if value is None:
            return None
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("llm_total_deadline_seconds must be finite")
        if number <= 0.0:
            raise ValueError("llm_total_deadline_seconds must be > 0")
        return number

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("llm_model must be a string")
        if not value or value.strip() != value or not value.strip():
            raise ValueError("llm_model must be a non-blank string")
        if _LLM_MODEL_RE.fullmatch(value) is None:
            raise ValueError("llm_model contains unsupported characters")
        return value

    @field_validator("llm_api_key")
    @classmethod
    def validate_llm_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        raw = value.get_secret_value()
        if not raw or raw.strip() != raw or not raw.strip():
            raise ValueError("llm_api_key must be a non-blank string")
        return value

    @field_validator(
        "api_control_credential",
        "api_inspection_credential",
        "api_agent_visible_credential",
        "api_debug_credential",
    )
    @classmethod
    def validate_api_credentials(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        raw = value.get_secret_value()
        if not raw or raw.strip() != raw or not raw.strip():
            raise ValueError("API credential must be a non-blank string")
        if len(raw) < _MIN_API_CREDENTIAL_LENGTH:
            raise ValueError(
                "API credential must be at least "
                f"{_MIN_API_CREDENTIAL_LENGTH} characters"
            )
        if any(ch.isspace() for ch in raw):
            raise ValueError("API credential must not contain whitespace")
        return value

    @field_validator(
        "api_stream_heartbeat_seconds",
        "api_stream_poll_seconds",
        "api_lease_ttl_seconds",
        "api_lease_heartbeat_seconds",
        "api_drain_timeout_seconds",
    )
    @classmethod
    def validate_api_positive_finite(cls, value: float) -> float:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("API duration settings must be finite")
        return number

    @field_validator("llm_base_url")
    @classmethod
    def validate_llm_base_url_shape(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        _validate_llm_base_url(value.get_secret_value())
        return value

    @model_validator(mode="after")
    def validate_database_urls(self) -> Settings:
        if self.database_url is not None:
            _validate_asyncpg_url(self.database_url.get_secret_value())
        if self.test_database_url is not None:
            raw = self.test_database_url.get_secret_value()
            _validate_asyncpg_url(raw)
            _validate_disposable_test_database(raw)
        return self

    @model_validator(mode="after")
    def validate_scale_knobs(self) -> Settings:
        if self.observer_catchup_page_size > self.api_max_page_size:
            raise ValueError(
                "PALIMPSEST_OBSERVER_CATCHUP_PAGE_SIZE must be <= "
                "PALIMPSEST_API_MAX_PAGE_SIZE"
            )
        return self

    @model_validator(mode="after")
    def validate_api_auth_consistency(self) -> Settings:
        if self.api_auth_required:
            if self.api_control_credential is None:
                raise ValueError(
                    "PALIMPSEST_API_CONTROL_CREDENTIAL is required when "
                    "PALIMPSEST_API_AUTH_REQUIRED is true"
                )
            if self.api_inspection_credential is None:
                raise ValueError(
                    "PALIMPSEST_API_INSPECTION_CREDENTIAL is required when "
                    "PALIMPSEST_API_AUTH_REQUIRED is true"
                )
            if self.api_agent_visible_credential is None:
                raise ValueError(
                    "PALIMPSEST_API_AGENT_VISIBLE_CREDENTIAL is required when "
                    "PALIMPSEST_API_AUTH_REQUIRED is true"
                )
        if self.api_debug_enabled and self.api_debug_credential is None:
            raise ValueError(
                "PALIMPSEST_API_DEBUG_CREDENTIAL is required when "
                "PALIMPSEST_API_DEBUG_ENABLED is true"
            )
        if self.api_lease_heartbeat_seconds >= self.api_lease_ttl_seconds:
            raise ValueError(
                "PALIMPSEST_API_LEASE_HEARTBEAT_SECONDS must be less than "
                "PALIMPSEST_API_LEASE_TTL_SECONDS"
            )
        return self

    @model_validator(mode="after")
    def validate_llm_when_enabled(self) -> Settings:
        if self.llm_adapter_kind is LlmAdapterKind.DISABLED:
            return self
        if self.llm_base_url is None:
            raise ValueError(
                "PALIMPSEST_LLM_BASE_URL is required when the LLM adapter is enabled"
            )
        if self.llm_model is None:
            raise ValueError(
                "PALIMPSEST_LLM_MODEL is required when the LLM adapter is enabled"
            )
        # Re-validate so enablement cannot skip URL/host checks.
        _validate_llm_base_url(self.llm_base_url.get_secret_value())
        return self

    def require_runtime_database(self) -> Settings:
        if self.database_url is None:
            raise SettingsError("PALIMPSEST_DATABASE_URL is required at runtime")
        _validate_asyncpg_url(self.database_url.get_secret_value())
        return self

    def database_dsn(self) -> str:
        if self.database_url is None:
            raise SettingsError("PALIMPSEST_DATABASE_URL is required at runtime")
        return self.database_url.get_secret_value()

    def test_database_dsn(self) -> str:
        if self.test_database_url is None:
            raise SettingsError(
                "PALIMPSEST_TEST_DATABASE_URL is required for integration tests"
            )
        return self.test_database_url.get_secret_value()

    def json_logs(self) -> bool:
        return self.environment != AppEnvironment.LOCAL

    def llm_enabled(self) -> bool:
        return self.llm_adapter_kind is not LlmAdapterKind.DISABLED

    def bootstrap_fields(self) -> dict[str, str | int | bool]:
        """Secret-safe DEBUG details: booleans, enums, and counts only.

        Never includes endpoints, credentials, models, rejected inputs, or
        wholesale settings dumps.
        """
        return {
            "environment": self.environment.value,
            "log_level": self.log_level.value,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "has_database_url": self.database_url is not None,
            "has_test_database_url": self.test_database_url is not None,
            "has_default_run_seed": self.default_run_seed is not None,
            "llm_adapter_kind": self.llm_adapter_kind.value,
            "llm_enabled": self.llm_enabled(),
            "llm_structured_output_mode": self.llm_structured_output_mode.value,
            "has_llm_model": self.llm_model is not None,
            "has_llm_base_url": self.llm_base_url is not None,
            "has_llm_api_key": self.llm_api_key is not None,
            "llm_max_attempts": self.llm_max_attempts,
            "has_llm_total_deadline": self.llm_total_deadline_seconds is not None,
            "llm_max_request_bytes": self.llm_max_request_bytes,
            "llm_max_response_bytes": self.llm_max_response_bytes,
            "llm_max_header_bytes": self.llm_max_header_bytes,
            "llm_send_correlation_header": self.llm_send_correlation_header,
            "has_llm_temperature": self.llm_temperature is not None,
            "api_auth_required": self.api_auth_required,
            "api_debug_enabled": self.api_debug_enabled,
            "has_api_control_credential": self.api_control_credential is not None,
            "has_api_inspection_credential": self.api_inspection_credential is not None,
            "has_api_agent_visible_credential": (
                self.api_agent_visible_credential is not None
            ),
            "has_api_debug_credential": self.api_debug_credential is not None,
            "api_max_page_size": self.api_max_page_size,
            "api_stream_queue_size": self.api_stream_queue_size,
            "observer_stream_queue_size": self.observer_stream_queue_size,
            "observer_catchup_page_size": self.observer_catchup_page_size,
            "memory_retrieve_max_candidates": self.memory_retrieve_max_candidates,
            "llm_max_concurrency": self.llm_max_concurrency,
            "cognition_trace_soft_cap_invocations_enabled": (
                self.cognition_trace_soft_cap_invocations is not None
            ),
            "cognition_trace_soft_cap_bytes_enabled": (
                self.cognition_trace_soft_cap_bytes is not None
            ),
            "has_presentation_web_root": self.presentation_web_root is not None,
            "has_revision": bool(self.revision),
        }

    def scale_knob_fields(self) -> dict[str, int | str]:
        """Secret-safe scale knob values for DEBUG load logging."""
        return {
            "api_stream_queue_size": self.api_stream_queue_size,
            "observer_stream_queue_size": self.observer_stream_queue_size,
            "observer_catchup_page_size": self.observer_catchup_page_size,
            "memory_retrieve_max_candidates": self.memory_retrieve_max_candidates,
            "llm_max_concurrency": self.llm_max_concurrency,
            "cognition_trace_soft_cap_invocations": (
                "disabled"
                if self.cognition_trace_soft_cap_invocations is None
                else self.cognition_trace_soft_cap_invocations
            ),
            "cognition_trace_soft_cap_bytes": (
                "disabled"
                if self.cognition_trace_soft_cap_bytes is None
                else self.cognition_trace_soft_cap_bytes
            ),
        }

    def __repr__(self) -> str:
        return (
            "Settings("
            f"environment={self.environment.value!r}, "
            f"log_level={self.log_level.value!r}, "
            f"api_host={self.api_host!r}, "
            f"api_port={self.api_port}, "
            "database_url=SecretStr('**********'), "
            f"pool_size={self.pool_size}, "
            f"llm_adapter_kind={self.llm_adapter_kind.value!r}, "
            f"llm_enabled={self.llm_enabled()}, "
            f"has_llm_api_key={self.llm_api_key is not None}, "
            f"api_auth_required={self.api_auth_required}, "
            f"api_debug_enabled={self.api_debug_enabled})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def _validate_asyncpg_url(url: str) -> None:
    if not url.startswith(_ASYNC_SCHEME):
        raise ValueError("database URL must use postgresql+asyncpg")


def _validate_llm_base_url(url: str) -> None:
    """Validate LLM base URL without embedding the URL in error messages."""
    if not isinstance(url, str) or not url or url.strip() != url:
        raise ValueError("LLM base URL is invalid")
    if "://" not in url:
        raise ValueError("LLM base URL scheme is invalid")
    scheme, remainder = url.split("://", 1)
    if scheme not in {"http", "https"}:
        raise ValueError("LLM base URL scheme is invalid")
    authority = remainder.split("/", 1)[0]
    if "@" in authority or "%40" in authority.lower():
        raise ValueError("LLM base URL must not include userinfo")
    if "?" in url or "#" in url:
        raise ValueError("LLM base URL must not include query or fragment")

    parsed = urlparse(url)
    if parsed.scheme != scheme:
        raise ValueError("LLM base URL scheme is invalid")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("LLM base URL must not include userinfo")
    if parsed.query or parsed.fragment:
        raise ValueError("LLM base URL must not include query or fragment")
    hostname = parsed.hostname
    if hostname is None or not hostname:
        raise ValueError("LLM base URL host is required")
    path = parsed.path or ""
    if path.rstrip("/") != "/v1":
        raise ValueError("LLM base URL path must be /v1")
    if scheme == "http" and hostname.lower() not in _LOCAL_HTTP_HOSTS:
        raise ValueError("LLM HTTP base URL must target an allowed local endpoint")


def database_name_from_url(url: str) -> str:
    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    return (parsed.path or "").lstrip("/").split("?")[0]


def _validate_disposable_test_database(url: str) -> None:
    name = database_name_from_url(url)
    if not name or name in _SYSTEM_DATABASES:
        raise ValueError(
            "PALIMPSEST_TEST_DATABASE_URL must not target a shared system database"
        )
    if TEST_DATABASE_MARKER not in name:
        raise ValueError(
            "PALIMPSEST_TEST_DATABASE_URL must name a disposable "
            f"{TEST_DATABASE_MARKER} database"
        )


def project_root_env_file(start: Path | None = None) -> Path:
    """Documented project-root ``.env`` lookup (directory containing pyproject.toml)."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate / ".env"
    return here / ".env"


def load_settings(
    *,
    env_file: Path | Literal[False] | None = None,
    **overrides: Any,
) -> Settings:
    """Load settings. Missing ``.env`` is allowed. Does not connect to PostgreSQL.

    Environment variables override ``.env``. Pass ``env_file=False`` to skip
    the project-root dotenv lookup (used by tests).
    """
    if env_file is False:
        dotenv: Path | None = None
    elif env_file is not None:
        dotenv = env_file if env_file.is_file() else None
    else:
        candidate = project_root_env_file()
        dotenv = candidate if candidate.is_file() else None
    try:
        return Settings(
            _env_file=dotenv,  # type: ignore[call-arg]
            _env_file_encoding="utf-8",
            **overrides,
        )
    except ValidationError as exc:
        raise _settings_error_from_validation(exc) from None


def load_runtime_settings(
    *,
    env_file: Path | Literal[False] | None = None,
    **overrides: Any,
) -> Settings:
    """Load settings and reject missing runtime database configuration."""
    return load_settings(env_file=env_file, **overrides).require_runtime_database()


def load_migration_settings(
    *,
    env_file: Path | Literal[False] | None = None,
    **overrides: Any,
) -> Settings:
    """Settings for Alembic. URL comes from validated settings, not alembic.ini.

    Integration tests may supply only ``PALIMPSEST_TEST_DATABASE_URL``.
    When both ``PALIMPSEST_DATABASE_URL`` and ``PALIMPSEST_TEST_DATABASE_URL``
    are present and disagree, refuse to migrate rather than guessing.
    """
    if "database_url" in overrides:
        return load_runtime_settings(env_file=env_file, **overrides)

    settings = load_settings(env_file=env_file, **overrides)
    database_url = settings.database_url
    test_database_url = settings.test_database_url

    if database_url is not None and test_database_url is not None:
        if database_url.get_secret_value() != test_database_url.get_secret_value():
            raise SettingsError(
                "Ambiguous migration target: PALIMPSEST_DATABASE_URL and "
                "PALIMPSEST_TEST_DATABASE_URL disagree; refusing to migrate"
            )
        return settings.require_runtime_database()

    if database_url is not None:
        return settings.require_runtime_database()

    if test_database_url is not None:
        return settings.model_copy(
            update={"database_url": test_database_url}
        ).require_runtime_database()

    raise SettingsError("PALIMPSEST_DATABASE_URL is required at runtime")
