"""Application settings. Importing this module does not read secrets or connect."""

from __future__ import annotations

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


def redact_secrets(text: str) -> str:
    """Strip URL credentials and DSN-like values from diagnostic text."""
    redacted = _CREDENTIALS_IN_URL.sub(r"\1***\2", text)
    redacted = re.sub(
        re.escape(_ASYNC_SCHEME) + r"[^\s'\"\\]+",
        f"{_ASYNC_SCHEME}***",
        redacted,
    )
    redacted = re.sub(r"postgresql://[^\s'\"\\]+", "postgresql://***", redacted)
    return _PASSWORD_ASSIGNMENT.sub(r"\1=***", redacted)


def _reject_bool(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("booleans are not valid integer settings")
    return value


class Settings(BaseSettings):
    """Typed configuration. Instantiate via ``load_settings``; not at import time."""

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

    @field_validator(
        "api_port",
        "pool_size",
        "max_overflow",
        "default_run_seed",
        mode="before",
    )
    @classmethod
    def reject_boolean_integers(cls, value: object) -> object:
        return _reject_bool(value)

    @field_validator("pool_timeout_seconds", mode="before")
    @classmethod
    def reject_boolean_floats(cls, value: object) -> object:
        return _reject_bool(value)

    @field_validator("default_run_seed")
    @classmethod
    def reject_negative_seed(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("default_run_seed must be a non-negative integer")
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

    def bootstrap_fields(self) -> dict[str, str | int | bool]:
        """Secret-safe DEBUG details. No DSN, credentials, or wholesale dump."""
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
        }

    def __repr__(self) -> str:
        return (
            "Settings("
            f"environment={self.environment.value!r}, "
            f"log_level={self.log_level.value!r}, "
            f"api_host={self.api_host!r}, "
            f"api_port={self.api_port}, "
            "database_url=SecretStr('**********'), "
            f"pool_size={self.pool_size})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def _validate_asyncpg_url(url: str) -> None:
    if not url.startswith(_ASYNC_SCHEME):
        raise ValueError("database URL must use postgresql+asyncpg")


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
        raise SettingsError(redact_secrets(str(exc))) from None


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

