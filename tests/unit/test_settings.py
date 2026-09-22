"""Settings loading, precedence, validation, and secret redaction."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infrastructure.settings import (
    LOG_LEVEL_ENV,
    SETTINGS_PREFIX,
    AppEnvironment,
    LlmAdapterKind,
    LlmStructuredOutputMode,
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
LLM_SECRET_KEY = "sk-live-hunter2-endpoint"
LOCAL_LLM_URL = "http://127.0.0.1:11434/v1"
REMOTE_LLM_URL = "https://api.example.com/v1"


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
    shared = "postgresql+asyncpg://palimpsest:hunter2@127.0.0.1:5432/palimpsest_test"
    monkeypatch.setenv(f"{SETTINGS_PREFIX}DATABASE_URL", shared)
    monkeypatch.setenv(f"{SETTINGS_PREFIX}TEST_DATABASE_URL", shared)
    settings = load_migration_settings(env_file=False)
    assert settings.database_dsn() == shared
    assert "hunter2" not in repr(settings)


def test_migration_settings_require_a_database_url() -> None:
    with pytest.raises(SettingsError, match="PALIMPSEST_DATABASE_URL"):
        load_migration_settings(env_file=False)


def test_llm_defaults_are_disabled() -> None:
    settings = load_settings(env_file=False)
    assert settings.llm_adapter_kind is LlmAdapterKind.DISABLED
    assert settings.llm_enabled() is False
    assert settings.llm_model is None
    assert settings.llm_base_url is None
    assert settings.llm_api_key is None
    assert settings.llm_structured_output_mode is LlmStructuredOutputMode.JSON_SCHEMA
    assert settings.llm_send_correlation_header is False
    bootstrap = settings.bootstrap_fields()
    assert bootstrap["llm_adapter_kind"] == "disabled"
    assert bootstrap["llm_enabled"] is False
    assert bootstrap["has_llm_api_key"] is False
    assert "llm_base_url" not in bootstrap
    assert "llm_per_attempt_timeout_seconds" not in bootstrap
    assert "llm_model" not in bootstrap
    assert LOCAL_LLM_URL not in str(bootstrap)


def test_llm_enabled_requires_model_and_base_url() -> None:
    with pytest.raises(SettingsError, match="PALIMPSEST_LLM_BASE_URL"):
        load_settings(
            env_file=False,
            llm_adapter_kind=LlmAdapterKind.OPENAI_COMPATIBLE,
            llm_model="llama3.2",
        )
    with pytest.raises(SettingsError, match="PALIMPSEST_LLM_MODEL"):
        load_settings(
            env_file=False,
            llm_adapter_kind=LlmAdapterKind.OPENAI_COMPATIBLE,
            llm_base_url=LOCAL_LLM_URL,
        )


def test_llm_accepts_local_http_and_remote_https() -> None:
    local = load_settings(
        env_file=False,
        llm_adapter_kind=LlmAdapterKind.OPENAI_COMPATIBLE,
        llm_model="llama3.2",
        llm_base_url=LOCAL_LLM_URL,
        llm_temperature=0,
    )
    assert local.llm_enabled() is True
    assert local.llm_base_url is not None
    assert local.llm_base_url.get_secret_value() == LOCAL_LLM_URL
    assert local.llm_temperature == 0.0

    ipv6 = load_settings(
        env_file=False,
        llm_adapter_kind=LlmAdapterKind.OPENAI_COMPATIBLE,
        llm_model="llama3.2",
        llm_base_url="http://[::1]:11434/v1",
    )
    assert ipv6.llm_enabled() is True

    remote = load_settings(
        env_file=False,
        llm_adapter_kind=LlmAdapterKind.OPENAI_COMPATIBLE,
        llm_model="gpt-4o-mini",
        llm_base_url=REMOTE_LLM_URL,
        llm_api_key=LLM_SECRET_KEY,
        llm_send_correlation_header=True,
    )
    assert remote.llm_send_correlation_header is True
    assert remote.llm_api_key is not None
    assert remote.llm_api_key.get_secret_value() == LLM_SECRET_KEY
    bootstrap = remote.bootstrap_fields()
    assert bootstrap["has_llm_api_key"] is True
    assert bootstrap["has_llm_model"] is True
    assert "gpt-4o-mini" not in str(bootstrap)
    assert REMOTE_LLM_URL not in str(bootstrap)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://127.0.0.1/v1",
        "http://example.com/v1",
        "http://127.0.0.1/v1/chat/completions",
        "http://127.0.0.1/v2",
        "http://user:pass@127.0.0.1/v1",
        "http://user%3Apass@127.0.0.1/v1",
        "http://127.0.0.1%40evil.example/v1",
        "http://127.0.0.1/v1?x=1",
        "http://127.0.0.1/v1#frag",
        "https://api.example.com/v1?key=sekrit",
    ],
)
def test_llm_base_url_rejects_unsafe_shapes(url: str) -> None:
    with pytest.raises(SettingsError) as exc_info:
        load_settings(
            env_file=False,
            llm_adapter_kind=LlmAdapterKind.OPENAI_COMPATIBLE,
            llm_model="llama3.2",
            llm_base_url=url,
        )
    message = str(exc_info.value)
    assert url not in message
    assert "sekrit" not in message
    assert "user:pass" not in message


def test_llm_rejects_blank_api_key_and_boolean_numerics() -> None:
    with pytest.raises(SettingsError, match="non-blank"):
        load_settings(
            env_file=False,
            llm_adapter_kind=LlmAdapterKind.OPENAI_COMPATIBLE,
            llm_model="llama3.2",
            llm_base_url=LOCAL_LLM_URL,
            llm_api_key="   ",
        )
    with pytest.raises(SettingsError, match="booleans"):
        load_settings(env_file=False, llm_max_attempts=True)
    with pytest.raises(SettingsError, match="booleans"):
        load_settings(env_file=False, llm_temperature=True)
    with pytest.raises(SettingsError, match="booleans"):
        load_settings(env_file=False, llm_per_attempt_timeout_seconds=False)


def test_llm_secrets_absent_from_repr_bootstrap_and_errors() -> None:
    settings = load_settings(
        env_file=False,
        llm_adapter_kind=LlmAdapterKind.OPENAI_COMPATIBLE,
        llm_model="llama3.2",
        llm_base_url=LOCAL_LLM_URL,
        llm_api_key=LLM_SECRET_KEY,
    )
    dumped = settings.model_dump()
    bootstrap = settings.bootstrap_fields()
    for surface in (repr(settings), str(settings), str(dumped), str(bootstrap)):
        assert LLM_SECRET_KEY not in surface
        assert LOCAL_LLM_URL not in surface
        assert "11434" not in surface

    with pytest.raises(SettingsError) as exc_info:
        load_settings(
            env_file=False,
            llm_adapter_kind=LlmAdapterKind.OPENAI_COMPATIBLE,
            llm_model="llama3.2",
            llm_base_url=f"http://leak:{LLM_SECRET_KEY}@127.0.0.1/v1",
        )
    assert LLM_SECRET_KEY not in str(exc_info.value)
    assert "leak" not in str(exc_info.value)


def test_settings_error_excludes_validation_input_values() -> None:
    with pytest.raises(SettingsError) as exc_info:
        load_settings(env_file=False, llm_max_attempts="not-an-int-sekrit")
    message = str(exc_info.value)
    assert "not-an-int-sekrit" not in message
    assert "input_value" not in message
    assert "pydantic.dev" not in message


def test_api_credentials_require_strength_and_debug_pairing() -> None:
    with pytest.raises(SettingsError, match="at least 32"):
        load_settings(env_file=False, api_control_credential="short")
    with pytest.raises(SettingsError, match="DEBUG_CREDENTIAL"):
        load_settings(env_file=False, api_debug_enabled=True)
    strong = "x" * 32
    settings = load_settings(
        env_file=False,
        api_debug_enabled=True,
        api_debug_credential=strong,
    )
    assert settings.api_debug_enabled is True
    assert "x" * 32 not in repr(settings)
    assert settings.bootstrap_fields()["has_api_debug_credential"] is True
    assert settings.bootstrap_fields()["api_debug_enabled"] is True


def test_api_auth_required_needs_capability_credentials() -> None:
    with pytest.raises(SettingsError, match="CONTROL_CREDENTIAL"):
        load_settings(env_file=False, api_auth_required=True)
    strong = "y" * 32
    settings = load_settings(
        env_file=False,
        api_auth_required=True,
        api_control_credential=strong,
        api_inspection_credential=strong,
        api_agent_visible_credential=strong,
    )
    assert settings.api_auth_required is True
    assert settings.api_max_page_size == 100
