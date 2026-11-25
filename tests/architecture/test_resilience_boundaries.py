# mypy: ignore-errors
"""Import and pin gates for detached societal resilience (V4-40)."""

from __future__ import annotations

import ast
from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT
from experiments import BENCHMARK_SCENARIO_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V63,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    V4CapabilityFlags,
)
from simulation.v4_architecture import (
    V4_ANALYSIS_ONLY_CONTEXTS,
    V4_CAPABILITY_FLAGS,
    V4ContextId,
    validate_v4_contexts,
)
from world._rules import COMMAND_RULE_MATRIX

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_societal_resilience_remains_detached_and_flagless() -> None:
    validate_v4_contexts()
    assert V4ContextId.SOCIETAL_RESILIENCE in V4_ANALYSIS_ONLY_CONTEXTS
    assert "disasters" in V4_CAPABILITY_FLAGS
    flags = V4CapabilityFlags(disasters=True)
    assert "societal_resilience" not in flags.owned_enabled_names()


def test_analysis_resilience_modules_have_no_runner_or_cognition_imports() -> None:
    for path in SRC.glob("analysis/resilience_*.py"):
        for module in _imports(path):
            root = module.split(".", 1)[0]
            assert root not in {
                "agents",
                "api",
                "experiments",
                "observer",
                "persistence",
                "infrastructure",
            }, (path, module)
            assert not module.startswith("world._"), (path, module)
            assert module not in {
                "simulation.runner",
                "simulation.engine",
                "simulation.agent_runtime",
            }, (path, module)


def test_no_live_path_imports_resilience_report_or_reducers() -> None:
    forbidden_suffixes = (
        "resilience_report",
        "resilience_report_codec",
        "resilience_physical",
        "resilience_social",
        "resilience_capture",
    )
    for package in ("world", "agents", "observer", "api"):
        package_root = SRC / package
        if not package_root.exists():
            continue
        for path in package_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for suffix in forbidden_suffixes:
                assert f"analysis.{suffix}" not in text, (path, suffix)
                assert f"experiments.{suffix}" not in text, (path, suffix)


def test_baseline_pins_unchanged() -> None:
    assert len(COMMAND_RULE_MATRIX) == 45
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert METRIC_FAMILY_COUNT == 275
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    assert RUNNER_SCHEMA_VERSION_V63 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 29
    assert 26 in ACCEPTED_EVENT_SCHEMA_VERSIONS
    assert "v24" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert BENCHMARK_SCENARIO_COUNT == 16
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []
