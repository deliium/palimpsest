"""V4-07 authority, boundary, determinism, and compatibility invariants.

Every forbidden architecture is a failing test: no objective justice oracle, no
court/judge/verdict, no global registry, no command construction, no world read,
no peer-ledger read, and exact version pins.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from agents.cognition.legal_disputes import (
    DISPUTE_FORBIDDEN_FIELD_NAMES,
    DisputeError,
    DisputeKind,
)
from analysis.dispute_contract import (
    DISPUTE_FORBIDDEN_RESULT_FIELDS,
    DISPUTE_OWNER_LOCAL_PREFIXES,
)
from analysis.specifications import METRIC_FAMILY_COUNT
from api.routes.dispute import router as dispute_router
from api.routes.formal_rule import router as formal_rule_router
from api.routes.organization import router as organization_router
from observer import SUPPORTED_OBSERVER_PROTOCOLS
from observer.version import SEMANTIC_EVENT_TYPES
from simulation import (
    ALEMBIC_HEAD_REVISION,
    OBSERVER_LAYOUT_SCHEMA_VERSION,
    OBSERVER_PROTOCOL_VERSION,
    V4_ANALYSIS_ONLY_CONTEXTS,
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_WRITE_PAIR_RESERVATIONS,
    V4CapabilityFlags,
    V4ContextId,
    V4ContextSpec,
    validate_v4_contexts,
)
from simulation.dispute_models import (
    DISPUTE_SNAPSHOT_POLICY_VERSION,
    DISPUTE_SNAPSHOT_SCHEMA,
)
from simulation.dispute_ports import DISPUTE_CURSOR_PURPOSES
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

DISPUTE_MODULES: tuple[Path, ...] = (
    SRC / "agents" / "cognition" / "legal_disputes.py",
    SRC / "agents" / "cognition" / "legal_dispute_communication.py",
    *sorted((SRC / "analysis").glob("dispute_*.py")),
    SRC / "analysis" / "disputes.py",
    SRC / "simulation" / "dispute_models.py",
    SRC / "simulation" / "dispute_codec.py",
    SRC / "simulation" / "dispute_paging.py",
    SRC / "simulation" / "dispute_ports.py",
    SRC / "experiments" / "dispute_harvest.py",
    SRC / "experiments" / "dispute_publication.py",
    SRC / "persistence" / "dispute_filesystem.py",
    SRC / "api" / "routes" / "dispute.py",
    SRC / "api" / "dispute_schemas.py",
    SRC / "api" / "dispute_cursor.py",
    SRC / "research_runner" / "dispute_composition.py",
)

ANALYSIS_MODULES: tuple[Path, ...] = (
    *sorted((SRC / "analysis").glob("dispute_*.py")),
    SRC / "analysis" / "disputes.py",
)

COGNITION_MODULES: tuple[Path, ...] = (
    SRC / "agents" / "cognition" / "legal_disputes.py",
    SRC / "agents" / "cognition" / "legal_dispute_communication.py",
)

FORBIDDEN_DISPUTE_SYMBOLS: frozenset[str] = frozenset(
    {
        "WorldState",
        "WorldEvent",
        "PerceptionService",
        "MemoryService",
        "EventStore",
        "ActionSubmission",
        "TickToken",
        "resolve_tick",
        "Court",
        "Judge",
        "Jury",
        "Verdict",
        "Judgment",
        "JusticeEngine",
        "ArbitrationEngine",
        "SanctionEngine",
        "LiabilityEngine",
        "GlobalDisputeRegistry",
        "DisputeRegistry",
    }
)

FORBIDDEN_OBJECT_TYPES: frozenset[str] = frozenset(
    {
        "WorldState",
        "WorldEvent",
        "PerceptionService",
        "MemoryService",
        "EventStore",
        "ActionSubmission",
        "TickToken",
        "AgentCommand",
        "PhysicalRules",
        "MetricDocument",
        "WorldEngine",
    }
)

FORBIDDEN_DISPUTE_FIELDS: frozenset[str] = DISPUTE_FORBIDDEN_FIELD_NAMES

COMMAND_TOKENS: tuple[str, ...] = (
    "AgentCommand(",
    "Give(",
    "Take(",
    "Attack(",
    "Talk(",
    "Tell(",
    "Feed(",
    "Transport(",
    "Help(",
    ".submit(",
    "ActionSubmission(",
)

DISPUTE_ROUTE_PATHS = {
    "/v1/simulations/{run_id}/disputes",
    "/v1/simulations/{run_id}/disputes/candidates",
    "/v1/simulations/{run_id}/disputes/candidates/{candidate_id}",
    "/v1/simulations/{run_id}/disputes/candidates/{candidate_id}/claims",
    "/v1/simulations/{run_id}/disputes/candidates/{candidate_id}/resolutions",
    "/v1/simulations/{run_id}/disputes/lineage",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _import_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    return roots


def _referenced_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
    return names


def _class_field_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                names.add(item.target.id)
    return names


def _routes(router: object) -> list[object]:
    return [
        route
        for route in getattr(router, "routes", ())
        if getattr(route, "methods", None) is not None
    ]


def test_dispute_module_list_matches_actual_files() -> None:
    assert DISPUTE_MODULES
    missing = [path for path in DISPUTE_MODULES if not path.is_file()]
    assert missing == []
    assert len(set(DISPUTE_MODULES)) == len(DISPUTE_MODULES)
    for expected in (
        SRC / "analysis" / "dispute_contract.py",
        SRC / "analysis" / "dispute_detection.py",
        SRC / "analysis" / "dispute_identity.py",
        SRC / "analysis" / "dispute_layers.py",
        SRC / "analysis" / "dispute_metrics.py",
    ):
        assert expected in DISPUTE_MODULES


def test_no_objective_justice_or_global_registry() -> None:
    offenders: list[tuple[str, str]] = []
    for path in DISPUTE_MODULES:
        referenced = _referenced_names(path)
        offenders.extend(
            (path.name, symbol)
            for symbol in FORBIDDEN_DISPUTE_SYMBOLS
            if symbol in referenced
        )
    assert offenders == []

    hits: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for name in (
            "Court",
            "Judge",
            "Jury",
            "Verdict",
            "Judgment",
            "JusticeEngine",
            "ArbitrationEngine",
            "SanctionEngine",
            "LiabilityEngine",
            "GlobalDisputeRegistry",
            "DisputeRegistry",
        ):
            if re.search(rf"class\s+{name}\b", text):
                hits.append(f"{path.relative_to(SRC)}:{name}")
    assert hits == []


def test_no_forbidden_justice_fields() -> None:
    for path in DISPUTE_MODULES:
        fields = _class_field_names(path)
        assert not fields & FORBIDDEN_DISPUTE_FIELDS, (path.name, fields)
    assert FORBIDDEN_DISPUTE_FIELDS == DISPUTE_FORBIDDEN_FIELD_NAMES
    assert {"verdict", "liable", "true_owner", "winner"} <= FORBIDDEN_DISPUTE_FIELDS
    assert "guilty" in DISPUTE_FORBIDDEN_RESULT_FIELDS
    forbidden_tokens = {"verdict", "guilty", "liable", "true_owner", "winner"}
    assert not forbidden_tokens & {kind.value for kind in DisputeKind}


def test_no_command_construction_or_world_read() -> None:
    for path in DISPUTE_MODULES:
        text = path.read_text(encoding="utf-8")
        for token in COMMAND_TOKENS:
            assert token not in text, (path.name, token)

    for path in (
        SRC / "world" / "_rules.py",
        SRC / "world" / "_operations.py",
        SRC / "world" / "_perception.py",
        SRC / "simulation" / "engine.py",
        SRC / "simulation" / "actions.py",
    ):
        text = path.read_text(encoding="utf-8").lower()
        assert "dispute" not in text, path

    perception = (SRC / "simulation" / "perception.py").read_text(encoding="utf-8")
    assert "disputes: object | None = None" in perception
    assert "apply_dispute_update" not in perception
    assert "legal_disputes" not in perception
    assert "DisputeLedger" not in perception

    for path in DISPUTE_MODULES:
        assert not _import_roots(path) & {"world._state", "world.events"}, path


def test_no_peer_ledger_or_cross_owner_read() -> None:
    import inspect

    from agents.cognition import DisputeLedger, apply_dispute_update
    from agents.cognition.mediation import MediationLedger
    from agents.cognition.offices import OfficeConceptLedger
    from agents.models import AgentId
    from tests.unit.formal_rule_helpers import make_ledger
    from world.identifiers import EntityId, WorldId, WorldRevision
    from world.observations import Observation

    parameters = set(inspect.signature(apply_dispute_update).parameters)
    assert not parameters & {
        "peer",
        "other_owner",
        "all_agents",
        "all_ledgers",
        "runtimes",
        "world_state",
        "event_store",
    }

    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-a"),
        revision=WorldRevision(0),
        tick=0,
    )
    for field_name, foreign in (
        ("mediation", MediationLedger(owner_id=AgentId("other"))),
        ("formal_rules", make_ledger(owner="other")),
        ("offices", OfficeConceptLedger(owner_id=AgentId("other"))),
    ):
        kwargs: dict[str, object] = {field_name: foreign}
        with pytest.raises(DisputeError) as excinfo:
            apply_dispute_update(
                "agent-a",
                0,
                observation,
                None,
                **kwargs,  # type: ignore[arg-type]
            )
        assert excinfo.value.code == "dispute_forbidden_input"

    with pytest.raises(DisputeError):
        apply_dispute_update(
            "agent-a",
            0,
            observation,
            DisputeLedger(owner_id="other"),
        )


def test_analysis_is_read_only_and_cognition_imports_no_analysis() -> None:
    forbidden = {
        "agents",
        "api",
        "experiments",
        "infrastructure",
        "observer",
        "persistence",
        "simulation",
        "world",
    }
    allowed = {
        "__future__",
        "analysis",
        "collections",
        "dataclasses",
        "enum",
        "hashlib",
        "json",
        "logging",
        "math",
        "re",
        "typing",
    }
    for path in ANALYSIS_MODULES:
        roots = _import_roots(path)
        assert not roots & forbidden, (path.name, roots & forbidden)
        assert roots <= allowed, (path.name, roots - allowed)

    for path in COGNITION_MODULES:
        roots = _import_roots(path)
        assert "analysis" not in roots, path.name
        assert "experiments" not in roots, path.name


def test_exactly_six_get_routes_and_six_cursor_purposes() -> None:
    routes = _routes(dispute_router)
    assert len(routes) == 6
    assert {getattr(route, "path", "") for route in routes} == DISPUTE_ROUTE_PATHS
    assert all(getattr(route, "methods", None) == {"GET"} for route in routes)
    assert DISPUTE_CURSOR_PURPOSES == (
        "summary",
        "candidates",
        "candidate",
        "claims",
        "resolutions",
        "lineage",
    )
    source = (SRC / "api" / "routes" / "dispute.py").read_text(encoding="utf-8")
    assert "SUBJECTIVE_DEBUG" in source
    assert "dispute_disabled" in source
    assert "dispute_cursor_invalid" in source

    formal_paths = {getattr(route, "path", "") for route in _routes(formal_rule_router)}
    organization_paths = {
        getattr(route, "path", "") for route in _routes(organization_router)
    }
    assert len(formal_paths) == 6
    assert len(organization_paths) == 6
    assert not formal_paths & DISPUTE_ROUTE_PATHS
    assert not organization_paths & DISPUTE_ROUTE_PATHS


def test_exact_context_flag_reservation_and_wire_pins() -> None:
    validate_v4_contexts()
    assert len(V4_CONTEXT_BY_ID) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_ANALYSIS_ONLY_CONTEXTS == frozenset(
        {V4ContextId.SOCIETAL_RESILIENCE, V4ContextId.MACRO_SOCIETY_IDENTITY}
    )
    owned = V4CapabilityFlags(
        organizations=True,
        formal_rules=True,
        legal_disputes=True,
    )
    assert owned.owned_enabled_names() == (
        "organizations",
        "formal_rules",
        "legal_disputes",
    )
    assert V4CapabilityFlags(legal_disputes=True).owned_enabled_names() == (
        "legal_disputes",
    )

    spec = V4_CONTEXT_BY_ID[V4ContextId.LEGAL_DISPUTES]
    assert isinstance(spec, V4ContextSpec)
    assert spec.capability_flag == "legal_disputes"
    assert spec.authority.value == "owner_scoped"
    assert spec.prerequisite_contexts == (V4ContextId.FORMAL_RULES,)
    assert spec.uses_existing_events is True
    assert spec.owner_packages == ("agents.cognition", "simulation")

    assert len(V4_WRITE_PAIR_RESERVATIONS) == 4
    assert {item.context_id.value for item in V4_WRITE_PAIR_RESERVATIONS} == {
        "infrastructure_networks",
        "epidemics",
        "ecological_feedback",
        "disasters",
    }
    assert "legal_disputes" not in {
        item.context_id.value for item in V4_WRITE_PAIR_RESERVATIONS
    }

    assert DISPUTE_SNAPSHOT_SCHEMA == "dispute-resolution-snapshot-v1"
    assert DISPUTE_SNAPSHOT_POLICY_VERSION == "dispute-analysis.v1"
    store = (SRC / "persistence" / "dispute_filesystem.py").read_text(encoding="utf-8")
    assert "dispute-resolution-store-v1" in store


def test_no_new_event_command_observer_semantic_or_migration() -> None:
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 22
    assert "v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v21" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert len(COMMAND_RULE_MATRIX) == 43
    assert METRIC_FAMILY_COUNT == 157
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert OBSERVER_LAYOUT_SCHEMA_VERSION == "observer-layout-v1"
    assert SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)

    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v56" in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    spec = V4_CONTEXT_BY_ID[V4ContextId.LEGAL_DISPUTES]
    assert spec.uses_existing_events is True


def test_carried_ledger_reaches_the_loop_snapshot() -> None:
    from agents.cognition import Perspective, empty_dispute_ledger
    from agents.models import AgentId
    from tests.unit.formal_rule_helpers import make_ledger
    from world.identifiers import EntityId, WorldId, WorldRevision
    from world.observations import Observation

    owner = AgentId("agent-a")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-a"),
        revision=WorldRevision(0),
        tick=0,
    )
    ledger = empty_dispute_ledger(owner)
    formal_rules = make_ledger(owner="agent-a")
    perspective = Perspective(
        agent_id=owner,
        observation=observation,
        memories=(),
        beliefs=(),
        inbox=(),
        formal_rules=formal_rules,
        disputes=ledger,
    )
    snapshot = perspective.to_snapshot()
    assert snapshot.disputes is ledger
    assert snapshot.formal_rules is formal_rules


def test_settings_and_app_do_not_read_dispute_content() -> None:
    settings = (SRC / "infrastructure" / "settings.py").read_text(encoding="utf-8")
    assert "DisputeLedger" not in settings
    assert "dispute_ledger" not in settings
    assert "agents.cognition.legal_disputes" not in settings
    assert "dispute_root" in settings
    assert "dispute_cursor_key" in settings

    for name in ("app.py", "dependencies.py"):
        imports = _import_roots(SRC / "api" / name)
        assert not imports & {"analysis", "experiments", "agents", "research_runner"}, (
            name
        )
    app_source = (SRC / "api" / "app.py").read_text(encoding="utf-8")
    assert "persistence.dispute_filesystem" in app_source
    assert "create_dispute_reader" in app_source


def test_owner_local_prefixes_never_appear_as_analytical_ids() -> None:
    from analysis.dispute_contract import (
        DISPUTE_CANDIDATE_ID_PREFIX,
        DISPUTE_EDGE_ID_PREFIX,
    )
    from analysis.dispute_evidence import build_dispute_windows
    from analysis.dispute_lineage import derive_dispute_lineage
    from analysis.disputes import harvest_dispute_rows
    from tests.unit.dispute_helpers import (
        OWNER,
        make_case,
        make_claim,
        make_ledger,
    )

    case = make_case(owner=OWNER, subject="bread")
    claim = make_claim(owner=OWNER, case=case, subject="bread")
    rows = harvest_dispute_rows((make_ledger(cases=(case,), claims=(claim,)),))
    analysis = derive_dispute_lineage(
        rows, build_dispute_windows(rows, window_ticks=100)
    )
    assert analysis.records
    for record in analysis.records:
        assert record.candidate_id.startswith(DISPUTE_CANDIDATE_ID_PREFIX)
        for prefix in DISPUTE_OWNER_LOCAL_PREFIXES:
            assert not record.candidate_id.startswith(prefix)
    for edge in analysis.edges:
        assert edge.edge_id.startswith(DISPUTE_EDGE_ID_PREFIX)
