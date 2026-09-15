"""Typing contracts for V1 domain unions and invalid fixtures."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TYPECHECK = ROOT / "tests" / "typecheck"
INVALID = TYPECHECK / "invalid"


def _run_mypy(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(ROOT / "pyproject.toml"),
            str(path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_v1_domain_contracts_typecheck() -> None:
    completed = _run_mypy(TYPECHECK / "v1_domain_contracts.py")
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize(
    ("fixture", "expected_code"),
    [
        ("bad_entity_id.txt", "arg-type"),
        ("bad_command_request.txt", "arg-type"),
        ("bad_tuple_mutation.txt", "unused-ignore"),
    ],
)
def test_invalid_fixtures_fail_mypy(fixture: str, expected_code: str) -> None:
    source = INVALID / fixture
    # Copy to a temporary .py path so mypy parses it as Python.
    target = INVALID / f"_{fixture.removesuffix('.txt')}.py"
    try:
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        completed = _run_mypy(target)
    finally:
        if target.exists():
            target.unlink()
    assert completed.returncode != 0
    combined = completed.stdout + completed.stderr
    # Tuple assignment to immutable tuple reports different codes across mypy versions.
    if fixture == "bad_tuple_mutation.txt":
        assert "tuple" in combined.lower() or "index" in combined.lower()
    else:
        assert expected_code in combined
