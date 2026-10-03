"""Guard against architecture_id switches in cognition/runtime hot paths."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
HOT_PATHS = (
    ROOT / "src" / "agents" / "cognition" / "loop.py",
    ROOT / "src" / "simulation" / "agent_runtime.py",
    ROOT / "src" / "simulation" / "runner.py",
)

_FORBIDDEN = re.compile(
    r"(architecture_id\s*==|if\s+architecture\b)",
    re.MULTILINE,
)


@pytest.mark.parametrize("path", HOT_PATHS, ids=lambda p: p.name)
def test_no_architecture_switches_in_hot_paths(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    match = _FORBIDDEN.search(text)
    assert match is None, f"forbidden architecture switch in {path}: {match.group(0)!r}"
