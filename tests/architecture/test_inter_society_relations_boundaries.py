# mypy: ignore-errors
"""V4-15 inter-society relations authority, import, route, and pin boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.inter_society_relations_contract import (
    INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS,
)
from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications
from api.routes.inter_society_relations import (
    INTER_SOCIETY_RELATIONS_ROUTE_COUNT,
    router,
)
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import (
    ALEMBIC_HEAD_REVISION,
    V4_OWNED_CAPABILITY_FLAGS,
)
from simulation.inter_society_relations_ports import (
    INTER_SOCIETY_RELATIONS_CURSOR_PURPOSES,
)
from simulation.persistence import ACCEPTED_PERSISTENCE_CODEC_VERSIONS
from simulation.runner_models import V4CapabilityFlags
from simulation.v4_architecture import (
    V4_ANALYSIS_ONLY_CONTEXTS,
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4ContextId,
)
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]

ISR_PATHS = tuple(
    sorted(
        path
        for pattern in (
            "src/analysis/inter_society_relations_*.py",
            "src/simulation/inter_society_relations_*.py",
            "src/experiments/inter_society_relations_*.py",
            "src/persistence/inter_society_relations_filesystem.py",
            "src/research_runner/inter_society_relations_composition.py",
            "src/api/routes/inter_society_relations.py",
            "src/api/inter_society_relations_schemas.py",
            "src/api/inter_society_relations_cursor.py",
        )
        for path in ROOT.glob(pattern)
    )
)

ISR_FAMILIES = (
    "inter_society_relation_structure",
    "inter_society_domain_evidence",
    "inter_society_relation_timeseries",
    "inter_society_pair_comparison",
)

FORBIDDEN_SCORE_CLASSES = {
    "CivilizationRelationshipScore",
    "AllianceScore",
    "EnmityScore",
    "SocietyTrustScore",
    "BilateralScore",
    "RelationRank",
    "FriendshipOracle",
}

FORBIDDEN_WORLD_AUTHORITY = {
    "WorldEngine",
    "WorldState",
    "ActionSubmission",
    "AgentCommand",
    "WorldEvent",
    "ActionRequest",
}

COMMAND_CONSTRUCTORS = {
    "Attack",
    "Move",
    "Take",
    "Give",
    "Flee",
    "Help",
    "Feed",
    "Transport",
    "Wait",
    "Defend",
    "NegotiateExchange",
}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(path: Path) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_isr_paths_exist() -> None:
    assert ISR_PATHS
    names = {path.name for path in ISR_PATHS}
    expected = {
        "inter_society_relations_contract.py",
        "inter_society_relations_layers.py",
        "inter_society_relations_evidence.py",
        "inter_society_relations_detection.py",
        "inter_society_relations_identity.py",
        "inter_society_relations_timeseries.py",
        "inter_society_relations_metrics.py",
        "inter_society_relations_models.py",
        "inter_society_relations_codec.py",
        "inter_society_relations_ports.py",
        "inter_society_relations_paging.py",
        "inter_society_relations_completed_run.py",
        "inter_society_relations_publication.py",
        "inter_society_relations_filesystem.py",
        "inter_society_relations_composition.py",
        "inter_society_relations.py",
        "inter_society_relations_schemas.py",
        "inter_society_relations_cursor.py",
    }
    assert expected <= names


def test_no_new_flag_context_or_v57() -> None:
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4ContextId.MACRO_SOCIETY_IDENTITY in V4_ANALYSIS_ONLY_CONTEXTS
    spec = V4_CONTEXT_BY_ID[V4ContextId.MACRO_SOCIETY_IDENTITY]
    assert spec.capability_flag is None
    assert V4CapabilityFlags().any_enabled() is False
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 6
    for path in ISR_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "runner-config-v57" not in text, path
        assert "V4CapabilityFlags" not in text, path
        assert "v4_capability_flags" not in text, path


def test_analysis_modules_are_detached() -> None:
    forbidden = (
        "agents",
        "experiments",
        "api",
        "persistence",
        "observer",
        "infrastructure",
    )
    for path in (ROOT / "src" / "analysis").glob("inter_society_relations_*.py"):
        for module in _imported_modules(path):
            for prefix in forbidden:
                assert not (module == prefix or module.startswith(f"{prefix}.")), (
                    path,
                    module,
                )


def test_simulation_modules_are_detached() -> None:
    forbidden = (
        "analysis",
        "api",
        "experiments",
        "infrastructure",
        "persistence",
        "observer",
    )
    for path in (ROOT / "src" / "simulation").glob("inter_society_relations_*.py"):
        for module in _imported_modules(path):
            for prefix in forbidden:
                assert not (module == prefix or module.startswith(f"{prefix}.")), (
                    path,
                    module,
                )


def test_api_and_persistence_import_no_analysis() -> None:
    for path in (
        ROOT / "src" / "persistence" / "inter_society_relations_filesystem.py",
        ROOT / "src" / "api" / "routes" / "inter_society_relations.py",
        ROOT / "src" / "api" / "inter_society_relations_cursor.py",
        ROOT / "src" / "api" / "inter_society_relations_schemas.py",
    ):
        for module in _imported_modules(path):
            assert not module.startswith("analysis"), (path, module)
            assert not module.startswith("experiments"), (path, module)


def test_no_world_authority_or_command_construction() -> None:
    for path in ISR_PATHS:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_WORLD_AUTHORITY:
            assert token not in text, (path, token)
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in FORBIDDEN_SCORE_CLASSES, (path, node.name)
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(
                    node.func, "attr", None
                )
                assert name not in COMMAND_CONSTRUCTORS, (path, name)
                assert name not in {"submit", "resolve", "admit", "submit_command"}


def test_forbid_list_covers_composite_scores() -> None:
    required = {
        "civilization_relationship_score",
        "alliance_score",
        "enmity_score",
        "relationship_score",
        "trust_score",
        "score",
        "composite",
        "bilateral_score",
    }
    assert required <= INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS


def test_exactly_six_get_routes() -> None:
    source = (ROOT / "src" / "api" / "routes" / "inter_society_relations.py").read_text(
        encoding="utf-8"
    )
    assert source.count("@router.get(") == 6
    assert INTER_SOCIETY_RELATIONS_ROUTE_COUNT == 6
    assert len(router.routes) == 6
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in source


def test_no_v2_route_or_protocol_or_godot_overlay() -> None:
    for path in ISR_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "/v2" not in text
        assert "observer-protocol-v2" not in text
    ui = (ROOT / "clients/research-ui/src/api/interSocietyRelations.ts").read_text(
        encoding="utf-8"
    )
    for verb in (
        "method: 'POST'",
        "method: 'PUT'",
        "method: 'PATCH'",
        "method: 'DELETE'",
    ):
        assert verb not in ui
    session = (ROOT / "clients/godot-observer/scripts/net/session.gd").read_text(
        encoding="utf-8"
    )
    assert "inter_society" not in session
    assert "request_inter_society" not in session


def test_pins_and_catalog_append() -> None:
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert "v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v21" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert METRIC_FAMILY_COUNT == 192
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert not any(
        "0018" in path.name for path in (ROOT / "alembic" / "versions").glob("*.py")
    )
    specs = all_metric_specifications()
    assert len(specs) == 192
    assert tuple(spec.family_id.value for spec in specs[180:184]) == ISR_FAMILIES
    assert all(
        spec.family_id.value != "inter_society_relation_lanes"
        for spec in specs[180:184]
    )
    assert tuple(spec.family_id.value for spec in specs[184:188]) == (
        "infrastructure_network_structure",
        "infrastructure_condition_lifecycle",
        "infrastructure_effect_coverage",
        "infrastructure_maintenance_burden",
    )
    assert INTER_SOCIETY_RELATIONS_CURSOR_PURPOSES == (
        "summary",
        "pairs",
        "pair",
        "series",
        "windows",
        "comparison",
    )


def test_no_cognition_isr_ledger_exists() -> None:
    cognition = ROOT / "src" / "agents" / "cognition"
    offenders = sorted(cognition.glob("*inter_society*"))
    assert offenders == []
