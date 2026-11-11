"""V4-18 deepening invariants: no new flag, write pair, or authority."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications
from analysis.trade_networks_contract import (
    TradeCoverage,
    TradeFlowClass,
)
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import ALEMBIC_HEAD_REVISION, V4_OWNED_CAPABILITY_FLAGS
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
)
from simulation.trade_networks_models import (
    TRADE_SNAPSHOT_COVERAGES,
    TRADE_SNAPSHOT_FLOW_CLASSES,
    TRADE_SNAPSHOT_NETWORK_STATUSES,
)
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
)
from simulation.versioning import V4_DEEPENING_WRITE_PAIRS
from world._rules import COMMAND_RULE_MATRIX

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
TRADE_FAMILIES = (
    "trade_corridor_structure",
    "trade_flow_composition",
    "trade_location_centrality",
    "trade_dependence",
    "cross_society_trade_flows",
    "trade_network_lineage",
)


def _trade_paths(prefix: str) -> tuple[Path, ...]:
    return tuple(sorted((SRC / prefix).glob("trade_networks_*.py")))


def _ast_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    return names


def test_pins_are_unchanged() -> None:
    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    assert RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27
    assert "v25" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert list((ROOT / "alembic" / "versions").glob("0018_*.py")) == []


def test_v4_contexts_and_flags_are_unchanged() -> None:
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_OWNED_CAPABILITY_FLAGS == frozenset(
        {
            "organizations",
            "formal_rules",
            "legal_disputes",
            "diplomacy",
            "organized_conflict",
            "infrastructure_networks",
        "supply_chains",
        "markets_credit",
        }
    )


def test_deepening_pairs_are_unchanged() -> None:
    assert [item.event_schema for item in V4_DEEPENING_WRITE_PAIRS] == [27]
    assert [item.codec_version for item in V4_DEEPENING_WRITE_PAIRS] == ["v25"]
    assert 28 not in ACCEPTED_EVENT_SCHEMA_VERSIONS
    assert "v26" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS


def test_no_v57_or_new_flag_reference() -> None:
    offenders = [
        path
        for path in SRC.rglob("*.py")
        if "runner-config-v57" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
    assert len(V4_CAPABILITY_FLAGS) == 12


def test_metric_catalog_is_204() -> None:
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 208
    assert len(specs) == 208
    assert [spec.family_id.value for spec in specs[192:198]] == list(TRADE_FAMILIES)
    assert [spec.family_id.value for spec in specs[198:204]] == [
        "supply_chain_structure",
        "supply_dependency_graph",
        "supply_bottleneck_pressure",
        "supply_resource_tool_dependency",
        "supply_location_infrastructure_reliance",
        "supply_organization_coordination",
    ]


def test_trade_analysis_imports_are_read_only() -> None:
    forbidden = {
        "simulation.engine",
        "simulation.bootstrap",
        "experiments",
        "api",
        "persistence",
        "observer",
        "agents.cognition",
    }
    for path in _trade_paths("analysis"):
        imports = _ast_names(path)
        for name in imports:
            assert name not in forbidden, (path, name)
            assert not name.startswith("world._"), (path, name)


def test_trade_simulation_does_not_import_analysis() -> None:
    for path in _trade_paths("simulation"):
        assert "analysis" not in _ast_names(path), path


def test_trade_surfaces_contain_no_forbidden_authority_fields() -> None:
    words = (
        "price",
        "money",
        "currency",
        "central_planner",
        "route_plan",
        "quota",
        "allocation",
        "score",
        "ranking",
    )
    paths = [
        *_trade_paths("analysis"),
        *_trade_paths("simulation"),
        *(SRC / "api").glob("trade_networks_*.py"),
        SRC / "api" / "routes" / "trade_networks.py",
        *_trade_paths("experiments"),
        ROOT / "clients/research-ui/src/api/tradeNetworks.ts",
        ROOT / "clients/research-ui/src/views/TradeNetworksPanel.svelte",
        ROOT
        / "clients/godot-observer/fixtures/protocol/civilization/overlay_trade.json",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        if path.name == "trade_networks_contract.py":
            continue
        for word in words:
            assert word not in text, (path, word)


def test_snapshot_network_statuses_match_analysis_lineage() -> None:
    assert TRADE_SNAPSHOT_FLOW_CLASSES == tuple(
        item.value for item in TradeFlowClass
    )
    assert TRADE_SNAPSHOT_COVERAGES == tuple(item.value for item in TradeCoverage)
    assert {
        "emerged",
        "continued",
        "transformed",
        "split",
        "merge",
        "dissolved",
    }.issubset(set(TRADE_SNAPSHOT_NETWORK_STATUSES))


def test_trade_modules_never_reference_commands_or_world_authority() -> None:
    names = {"WorldState", "WorldEngine", "ActionSubmission", "AgentCommand"}
    matrix = "COMMAND_RULE_MATRIX"
    for path in (
        *_trade_paths("analysis"),
        *_trade_paths("simulation"),
        *(SRC / "api").glob("trade_networks_*.py"),
        SRC / "api" / "routes" / "trade_networks.py",
        *_trade_paths("experiments"),
    ):
        ast_names = _ast_names(path)
        assert not names & ast_names, (path, names & ast_names)
        assert matrix not in ast_names, path
