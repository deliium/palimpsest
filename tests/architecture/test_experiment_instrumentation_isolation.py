"""Architecture gate: experiment instrumentation stays outside domain packages."""

from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

_FORBIDDEN_IMPORTS = ("import experiments", "from experiments")
_FORBIDDEN_SYMBOLS = (
    "StoryTruthSpec",
    "StoryInterventionArbiter",
    "ExperimentCoordinator",
    "CollectorMetricDocument",
    "collect_arm_summary",
)
_DOMAIN_ROOTS = (
    "world",
    "agents",
    "memory",
    "social",
    "simulation",
)


def test_domain_and_simulation_never_import_experiments() -> None:
    for package in _DOMAIN_ROOTS:
        root = SRC / package
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in _FORBIDDEN_IMPORTS:
                assert marker not in text, f"{path}: {marker}"
            for symbol in _FORBIDDEN_SYMBOLS:
                assert symbol not in text, f"{path}: {symbol}"


def test_cognition_memory_social_never_reference_collectors() -> None:
    for package in ("agents/cognition", "memory", "social"):
        root = SRC / package
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "StoryTruthSpec" not in text
            assert "CollectorMetricDocument" not in text
            assert "collect_arm_summary" not in text
            assert "ExperimentCoordinator" not in text
