"""Settings loading, precedence, validation, and secret redaction."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infrastructure.settings import (
    LOG_LEVEL_ENV,
    SETTINGS_PREFIX,
    AppEnvironment,
    LogLevel,
    SettingsError,
    load_migration_settings,
    load_runtime_settings,
    load_settings,
    project_root_env_file,
)
from simulation.models import SimulationRunConfig

pytestmark = pytest.mark.unit

SECRET_DSN = "postgresql+asyncpg://palimpsest:hunter2@127.0.0.1:5432/palimpsest"


@pytest.fixture(autouse=True)
def isolate_palimpsest_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith(SETTINGS_PREFIX):
            monkeypatch.delenv(key, raising=False)


def test_import_does_not_require_database_url() -> None:
    settings = load_settings(env_file=False)
    assert settings.database_url is None
    assert settings.environment is AppEnvironment.LOCAL


def test_runtime_settings_reject_missing_database_url() -> None:
    with pytest.raises(SettingsError, match="PALIMPSEST_DATABASE_URL"):
        load_runtime_settings(env_file=False)


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(SettingsError):
        load_settings(env_file=False, environment="staging")


def test_invalid_pool_bounds_and_seed_are_rejected() -> None:
    with pytest.raises(SettingsError):
        load_settings(env_file=False, pool_size=0)
    with pytest.raises(SettingsError):
        load_settings(env_file=False, max_overflow=-1)
    with pytest.raises(SettingsError):
        load_settings(env_file=False, default_run_seed=-1)


def test_booleans_are_rejected_as_integer_settings() -> None:
    with pytest.raises(SettingsError, match="booleans"):
        load_settings(env_file=False, pool_size=True)
    with pytest.raises(SettingsError, match="booleans"):
        load_settings(env_file=False, api_port=False)
    with pytest.raises(SettingsError, match="booleans"):
        load_settings(env_file=False, default_run_seed=True)


def test_non_asyncpg_urls_are_rejected() -> None:
    with pytest.raises(SettingsError, match="postgresql\\+asyncpg"):
        load_settings(
            env_file=False,
            database_url="postgresql://palimpsest:hunter2@127.0.0.1/palimpsest",
        )


def test_test_database_url_requires_disposable_name() -> None:
    with pytest.raises(SettingsError, match="palimpsest_test"):
        load_settings(env_file=False, test_database_url=SECRET_DSN)
    with pytest.raises(SettingsError, match="shared system database"):
        load_settings(
            env_file=False,
            test_database_url=(
                "postgresql+asyncpg://palimpsest_test:hunter2@127.0.0.1:5432/postgres"
            ),
        )


def test_credentials_are_absent_from_repr_errors_and_bootstrap() -> None:
    settings = load_settings(env_file=False, database_url=SECRET_DSN)
    dumped = settings.model_dump()
    assert "hunter2" not in repr(settings)
    assert "hunter2" not in str(settings)
    assert "hunter2" not in str(dumped)
    assert "hunter2" not in str(settings.bootstrap_fields())
    with pytest.raises(SettingsError) as exc_info:
        load_settings(
            env_file=False,
            database_url="postgresql://palimpsest:hunter2@127.0.0.1/palimpsest",
        )
    assert "hunter2" not in str(exc_info.value)


def test_environment_overrides_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "PALIMPSEST_LOG_LEVEL=WARNING\nPALIMPSEST_API_PORT=9000\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(LOG_LEVEL_ENV, "DEBUG")
    settings = load_settings(env_file=env_file)
    assert settings.log_level is LogLevel.DEBUG
    assert settings.api_port == 9000


def test_project_root_env_lookup_finds_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)
    assert project_root_env_file(nested) == tmp_path / ".env"


def test_default_run_seed_is_copied_into_explicit_run_config() -> None:
    settings = load_settings(env_file=False, default_run_seed=42)
    seed = settings.default_run_seed
    assert seed is not None
    config = SimulationRunConfig(seed=seed)
    assert config.seed == 42
    assert config.seed == settings.default_run_seed


def test_runtime_settings_accept_asyncpg_url() -> None:
    settings = load_runtime_settings(env_file=False, database_url=SECRET_DSN)
    assert settings.database_dsn() == SECRET_DSN
    assert settings.test_database_url is None


def test_migration_settings_accept_test_database_url_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        f"{SETTINGS_PREFIX}TEST_DATABASE_URL",
        "postgresql+asyncpg://palimpsest:hunter2@127.0.0.1:5432/palimpsest_test",
    )
    settings = load_migration_settings(env_file=False)
    assert settings.database_dsn().endswith("/palimpsest_test")
    assert "hunter2" not in repr(settings)


def test_migration_settings_reject_disagreeing_database_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(f"{SETTINGS_PREFIX}DATABASE_URL", SECRET_DSN)
    monkeypatch.setenv(
        f"{SETTINGS_PREFIX}TEST_DATABASE_URL",
        "postgresql+asyncpg://palimpsest:hunter2@127.0.0.1:5432/palimpsest_test",
    )
    with pytest.raises(SettingsError, match="Ambiguous migration target"):
        load_migration_settings(env_file=False)


def test_migration_settings_accept_agreeing_database_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared = (
        "postgresql+asyncpg://palimpsest:hunter2@127.0.0.1:5432/palimpsest_test"
    )
    monkeypatch.setenv(f"{SETTINGS_PREFIX}DATABASE_URL", shared)
    monkeypatch.setenv(f"{SETTINGS_PREFIX}TEST_DATABASE_URL", shared)
    settings = load_migration_settings(env_file=False)
    assert settings.database_dsn() == shared
    assert "hunter2" not in repr(settings)


def test_migration_settings_require_a_database_url() -> None:
    with pytest.raises(SettingsError, match="PALIMPSEST_DATABASE_URL"):
        load_migration_settings(env_file=False)
