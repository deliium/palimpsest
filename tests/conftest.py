"""Pytest bootstrap for Palimpsest.

Application logging is never configured during collection. The only
application log-level setting is ``PALIMPSEST_LOG_LEVEL``; tests may emit
concise DEBUG diagnostics when ``PALIMPSEST_TEST_DEBUG`` is truthy.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import asyncpg
import pytest

APPLICATION_LOG_LEVEL_ENV: Final[str] = "PALIMPSEST_LOG_LEVEL"
TEST_DEBUG_ENV: Final[str] = "PALIMPSEST_TEST_DEBUG"
APPLICATION_LOGGING_CONFIGURED_DURING_COLLECTION: bool = False

_DOCKER_EXECUTABLES: Final[frozenset[str]] = frozenset(
    {"docker", "docker-compose", "podman", "nerdctl"}
)
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})


def _debug_requested() -> bool:
    return os.environ.get(TEST_DEBUG_ENV, "").strip().lower() in _TRUTHY


def _emit_test_debug(message: str) -> None:
    if _debug_requested():
        print(f"[palimpsest-tests] DEBUG {message}", file=sys.stderr)


def pytest_configure(config: pytest.Config) -> None:
    """Register diagnostics without configuring application logging."""
    _emit_test_debug(
        "collection bootstrap "
        f"rootdir={config.rootpath} markexpr={config.option.markexpr!r}"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Assign default markers from each test path."""
    _emit_test_debug(f"collected {len(items)} items")
    for item in items:
        path = Path(str(item.path)).as_posix()
        if "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)
        elif "/tests/compose/" in path:
            item.add_marker(pytest.mark.compose)
        elif "/tests/architecture/" in path:
            item.add_marker(pytest.mark.architecture)
        elif "/tests/typecheck/" in path:
            item.add_marker(pytest.mark.typecheck)
        elif (
            item.get_closest_marker("integration") is None
            and item.get_closest_marker("compose") is None
        ):
            item.add_marker(pytest.mark.unit)


def _command_executable(args: Any) -> str:
    if isinstance(args, (list, tuple)) and args:
        command = args[0]
    else:
        command = args
    return Path(str(command)).name


def _guard_docker_invocation(args: Any, *, nodeid: str) -> None:
    executable = _command_executable(args)
    if executable in _DOCKER_EXECUTABLES:
        raise RuntimeError(
            f"Unit test {nodeid} attempted to invoke {executable}. "
            "Docker is forbidden in unit tests."
        )


def _install_subprocess_guard(monkeypatch: pytest.MonkeyPatch, nodeid: str) -> None:
    original_run = subprocess.run
    original_popen = subprocess.Popen
    original_call = subprocess.call
    original_check_call = subprocess.check_call
    original_check_output = subprocess.check_output

    def run(args: Any, *rest: Any, **kwargs: Any) -> Any:
        _guard_docker_invocation(args, nodeid=nodeid)
        return original_run(args, *rest, **kwargs)

    def popen(args: Any, *rest: Any, **kwargs: Any) -> Any:
        _guard_docker_invocation(args, nodeid=nodeid)
        return original_popen(args, *rest, **kwargs)

    def call(args: Any, *rest: Any, **kwargs: Any) -> Any:
        _guard_docker_invocation(args, nodeid=nodeid)
        return original_call(args, *rest, **kwargs)

    def check_call(args: Any, *rest: Any, **kwargs: Any) -> Any:
        _guard_docker_invocation(args, nodeid=nodeid)
        return original_check_call(args, *rest, **kwargs)

    def check_output(args: Any, *rest: Any, **kwargs: Any) -> Any:
        _guard_docker_invocation(args, nodeid=nodeid)
        return original_check_output(args, *rest, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(subprocess, "call", call)
    monkeypatch.setattr(subprocess, "check_call", check_call)
    monkeypatch.setattr(subprocess, "check_output", check_output)


def _block_postgres(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError(
        "Unit tests cannot connect to PostgreSQL. Use the integration marker "
        "and PALIMPSEST_TEST_DATABASE_URL for disposable database tests."
    )


def _install_postgres_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asyncpg, "connect", _block_postgres)
    monkeypatch.setattr(asyncpg, "create_pool", _block_postgres)

    for module_name in ("psycopg", "psycopg2"):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "connect"):
            monkeypatch.setattr(module, "connect", _block_postgres)


@pytest.fixture(autouse=True)
def _forbid_live_infrastructure_in_unit_tests(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Prevent unit tests from invoking Docker or opening PostgreSQL connections."""
    if request.node.get_closest_marker("integration") is not None:
        yield
        return
    if request.node.get_closest_marker("compose") is not None:
        yield
        return

    _install_subprocess_guard(monkeypatch, request.node.nodeid)
    _install_postgres_guard(monkeypatch)
    yield
