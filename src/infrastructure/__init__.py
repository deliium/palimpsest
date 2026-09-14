"""Technical adapters for settings, logging, and PostgreSQL.

Public facade. Importing this package does not load secrets, configure
logging, or connect to external services.
"""

from infrastructure.database import (
    DatabaseResources,
    check_readiness,
    create_database_resources,
    dispose_engine,
    session_scope,
)
from infrastructure.logging import (
    bind_log_context,
    clear_log_context,
    configure_logging,
    get_logger,
    log_bootstrap,
    log_lifecycle,
    log_recoverable,
    log_setup_failure,
)
from infrastructure.settings import (
    LOG_LEVEL_ENV,
    SETTINGS_PREFIX,
    AppEnvironment,
    LogLevel,
    Settings,
    SettingsError,
    load_runtime_settings,
    load_settings,
    redact_secrets,
)

__all__ = [
    "LOG_LEVEL_ENV",
    "SETTINGS_PREFIX",
    "AppEnvironment",
    "DatabaseResources",
    "LogLevel",
    "Settings",
    "SettingsError",
    "bind_log_context",
    "check_readiness",
    "clear_log_context",
    "configure_logging",
    "create_database_resources",
    "dispose_engine",
    "get_logger",
    "load_runtime_settings",
    "load_settings",
    "log_bootstrap",
    "log_lifecycle",
    "log_recoverable",
    "log_setup_failure",
    "redact_secrets",
    "session_scope",
]
