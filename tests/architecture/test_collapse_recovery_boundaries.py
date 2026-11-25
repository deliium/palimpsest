"""Import and pin gates for detached collapse-recovery (V4-41)."""

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

_COLLAPSE_ANALYSIS = (
    "collapse_recovery_evidence",
    "collapse_recovery_indicators",
    "collapse_recovery_episodes",
    "collapse_recovery_lineage",
    "collapse_recovery_continuity",
    "collapse_recovery_report",
    "collapse_recovery_report_codec",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_collapse_recovery_remains_detached_and_flagless() -> None:
    validate_v4_contexts()
    assert V4ContextId.SOCIETAL_RESILIENCE in V4_ANALYSIS_ONLY_CONTEXTS
    flags = V4CapabilityFlags(disasters=True)
    assert "collapse_recovery" not in flags.owned_enabled_names()
    assert "civilization_collapsed" not in flags.owned_enabled_names()


def test_analysis_collapse_modules_have_no_runner_or_cognition_imports() -> None:
    for name in _COLLAPSE_ANALYSIS:
        path = SRC / "analysis" / f"{name}.py"
        assert path.is_file(), path
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


def test_only_trusted_experiments_import_collapse_capture() -> None:
    capture_module = "experiments.collapse_recovery_capture"
    allowed = {
        SRC / "experiments" / "collapse_recovery_capture.py",
        SRC / "experiments" / "__init__.py",
    }
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if capture_module not in text and "collapse_recovery_capture" not in text:
            continue
        if path in allowed:
            continue
        # Tests may import; production packages other than experiments must not.
        if "tests" in path.parts:
            continue
        if path.is_relative_to(SRC / "experiments"):
            # Only the capture module itself and package init are allowed.
            assert path in allowed, path
            continue
        raise AssertionError(f"unexpected collapse capture import in {path}")


def test_no_live_path_imports_collapse_analysis() -> None:
    for package in ("world", "agents", "observer", "api", "simulation"):
        package_root = SRC / package
        if not package_root.exists():
            continue
        for path in package_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for suffix in _COLLAPSE_ANALYSIS:
                assert f"analysis.{suffix}" not in text, (path, suffix)
            assert "experiments.collapse_recovery_capture" not in text, path


def test_baseline_pins_unchanged_for_collapse_recovery() -> None:
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
