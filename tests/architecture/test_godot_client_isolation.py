"""The Godot observer client stays outside the Python package."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
SRC = ROOT / "src"
SCRIPTS = ROOT / "clients" / "godot-observer" / "scripts"
REGRESSION_GATE = ROOT / "tests" / "unit" / "test_v1_regression_gate.py"

SCANNED = (
    "clients/godot-observer",
    "godot",
    "localhost",
    "127.0.0.1",
)

_PACKAGE_LIST_KEYS = frozenset({"packages", "root_packages"})
_FORBIDDEN_PACKAGE_VALUES = frozenset(
    {
        "godot",
        "src/godot",
        "clients/godot-observer",
    }
)


def _package_entries(value: object, key: str | None = None) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            found.extend(_package_entries(child, str(child_key)))
        return found
    if isinstance(value, list) and key in _PACKAGE_LIST_KEYS:
        for item in value:
            if isinstance(item, str):
                found.append(item)
        return found
    if isinstance(value, list):
        for item in value:
            found.extend(_package_entries(item, key))
    return found


def _scan() -> dict[str, object]:
    document = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    package_hits = [
        entry
        for entry in _package_entries(document)
        if entry in _FORBIDDEN_PACKAGE_VALUES or "clients/godot-observer" in entry
    ]
    source_hits: list[str] = []
    for path in sorted(SRC.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".json", ".toml", ".txt", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if "clients/godot-observer" in text or "godot" in lowered:
            source_hits.append(str(path.relative_to(ROOT)))
    script_hits: list[str] = []
    if SCRIPTS.is_dir():
        for path in sorted(SCRIPTS.rglob("*.gd")):
            text = path.read_text(encoding="utf-8")
            if "localhost" in text or "127.0.0.1" in text:
                script_hits.append(str(path.relative_to(ROOT)))
    gate = REGRESSION_GATE.read_text(encoding="utf-8").lower()
    return {
        "scanned": list(SCANNED),
        "package_hits": package_hits,
        "source_hits": source_hits,
        "script_hits": script_hits,
        "regression_gate_mentions_godot": "godot" in gate,
    }


def test_godot_client_stays_outside_the_python_package() -> None:
    report = _scan()
    assert report["scanned"] == list(SCANNED)
    assert report["package_hits"] == []
    assert report["source_hits"] == []
    assert report["script_hits"] == []
    assert report["regression_gate_mentions_godot"] is False
