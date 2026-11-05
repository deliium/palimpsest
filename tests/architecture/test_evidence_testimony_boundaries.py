"""V4-08 authority, vocabulary, seam, and compatibility invariants."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import re
from pathlib import Path
from typing import Any, cast

import pytest

import agents.cognition as cognition
import analysis
import api.routes as route_facade
import experiments
import simulation
from agents.cognition import (
    EVIDENCE_ERROR_CODES,
    EVIDENCE_FORBIDDEN_FIELD_NAMES,
    EVIDENCE_NOTICE_REASONS,
    EvidenceContradictionKind,
    EvidenceCustodyStatus,
    EvidenceError,
    EvidenceInterpretationKind,
    EvidenceLedger,
    EvidenceProvenanceChannel,
    EvidenceSourceKind,
    EvidenceTestimonyChannel,
    EvidenceTrustBasis,
    Perspective,
    apply_evidence_update,
    empty_evidence_ledger,
)
from analysis.evidence_testimony_contract import (
    EVIDENCE_CONFIDENCE_BANDS,
    EVIDENCE_CUSTODY_STATUSES,
    EVIDENCE_INTERPRETATIONS,
    EVIDENCE_PROVENANCE_CHANNELS,
    EVIDENCE_SOURCE_KINDS,
    EVIDENCE_TRUST_BASES,
)
from analysis.specifications import METRIC_FAMILY_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import ALEMBIC_HEAD_REVISION, V4_OWNED_CAPABILITY_FLAGS
from simulation.dispute_models import DISPUTE_SNAPSHOT_SCHEMA
from simulation.evidence_testimony_models import (
    EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA,
)
from simulation.evidence_testimony_ports import EVIDENCE_TESTIMONY_CURSOR_PURPOSES
from simulation.formal_rule_models import FORMAL_RULE_SNAPSHOT_SCHEMA
from simulation.organization_models import ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.v4_architecture import V4_CAPABILITY_FLAGS, V4_CONTEXTS
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

FORBIDDEN_SYMBOLS = (
    "WorldState",
    "WorldEvent",
    "PerceptionService",
    "MemoryService",
    "EventStore",
    "ActionSubmission",
    "TickToken",
    "resolve_tick",
    "EvidenceOracle",
    "TruthEngine",
    "ProofEngine",
    "Authenticator",
    "Verifier",
    "ChainOfCustodyAuthority",
    "Polygraph",
    "LieDetector",
    "WitnessAuthority",
    "EvidenceRegistry",
    "GlobalEvidenceRegistry",
    "Court",
    "Judge",
    "Jury",
    "Verdict",
    "Judgment",
    "LiabilityEngine",
)
FORBIDDEN_FIELDS = EVIDENCE_FORBIDDEN_FIELD_NAMES | {
    "correct_account",
    "true_source",
    "reliable",
    "probability_true",
}
COMMAND_TOKENS = (
    "AgentCommand(",
    "ActionSubmission(",
    "submit_command",
    "resolve_tick",
    "admit_command",
)


def _evidence_modules() -> list[Path]:
    modules: list[Path] = [
        SRC / "agents" / "cognition" / "evidence_testimony.py",
        SRC / "agents" / "cognition" / "evidence_testimony_communication.py",
        SRC / "persistence" / "evidence_testimony_filesystem.py",
        SRC / "api" / "routes" / "evidence_testimony.py",
        SRC / "api" / "evidence_testimony_schemas.py",
        SRC / "api" / "evidence_testimony_cursor.py",
        SRC / "research_runner" / "evidence_testimony_composition.py",
    ]
    modules.extend(sorted((SRC / "analysis").glob("evidence_testimony_*.py")))
    modules.extend(sorted((SRC / "simulation").glob("evidence_testimony_*.py")))
    modules.extend(sorted((SRC / "experiments").glob("evidence_testimony_*.py")))
    return modules


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
    return roots


def test_forbidden_symbols_and_command_tokens_are_absent() -> None:
    for path in _evidence_modules():
        text = re.sub(
            r"_FORBIDDEN_OBJECT_TYPES.*?\n\)",
            "",
            path.read_text(encoding="utf-8"),
            flags=re.S,
        )
        for token in FORBIDDEN_SYMBOLS:
            assert token not in text, f"{path.relative_to(SRC)}:{token}"
        for token in COMMAND_TOKENS:
            assert token not in text, f"{path.relative_to(SRC)}:{token}"


def test_no_truth_like_field_exists() -> None:
    for model in (
        EvidenceLedger,
        cognition.EvidenceSource,
        cognition.EvidenceWitnessStatement,
        cognition.EvidenceItem,
        cognition.EvidenceCustodyLink,
        cognition.EvidenceContradiction,
        cognition.EvidenceEvaluation,
        analysis.EvidenceSourceRow,
        analysis.EvidenceCandidate,
        simulation.EvidenceTestimonySnapshot,
        simulation.EvidenceSourceRecord,
        simulation.EvidenceCandidateRecord,
    ):
        names = {field.name for field in dataclasses.fields(model)}
        assert names.isdisjoint(FORBIDDEN_FIELDS), model


def test_import_boundaries_hold() -> None:
    for path in sorted((SRC / "analysis").glob("evidence_testimony_*.py")):
        assert _import_roots(path) <= {
            "analysis",
            "abc",
            "collections",
            "__future__",
            "dataclasses",
            "enum",
            "hashlib",
            "json",
            "logging",
            "re",
            "typing",
        }, path
    for relative in (
        "agents/cognition/evidence_testimony.py",
        "agents/cognition/evidence_testimony_communication.py",
    ):
        roots = _import_roots(SRC / relative)
        assert roots.isdisjoint(
            {
                "analysis",
                "experiments",
                "persistence",
                "api",
                "infrastructure",
                "observer",
                "simulation",
            }
        )
    for relative in (
        "api/routes/evidence_testimony.py",
        "api/evidence_testimony_schemas.py",
        "api/evidence_testimony_cursor.py",
    ):
        assert _import_roots(SRC / relative).isdisjoint({"analysis", "experiments"})
    assert _import_roots(
        SRC / "persistence" / "evidence_testimony_filesystem.py"
    ).isdisjoint({"analysis"})


def test_update_signature_accepts_no_world_event_or_command() -> None:
    signature = inspect.signature(apply_evidence_update)
    rendered = " ".join(
        str(parameter.annotation) for parameter in signature.parameters.values()
    )
    for forbidden in (
        "Observation",
        "WorldState",
        "WorldEvent",
        "MemoryService",
        "EventStore",
        "AgentCommand",
        "DisputeLedger",
    ):
        assert forbidden not in rendered


def test_perspective_carries_an_opaque_evidence_value() -> None:
    ledger = empty_evidence_ledger("agent-1")
    from agents.models import AgentId

    perspective = Perspective(
        agent_id=AgentId("agent-1"),
        observation=_observation(),
        memories=(),
        beliefs=(),
        inbox=(),
        semantic_beliefs=(),
        evidence=ledger,
    )
    assert perspective.to_snapshot().evidence is ledger


def _observation() -> Any:
    from world.identifiers import EntityId, WorldId, WorldRevision
    from world.observations import Observation

    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=1,
    )


def test_six_routes_are_get_only() -> None:
    from api.routes.evidence_testimony import router

    routes: list[Any] = []
    for route in router.routes:
        if getattr(route, "methods", None):
            routes.append(cast(Any, route))
    assert len(routes) == 6
    assert all(route.methods == {"GET"} for route in routes)
    assert EVIDENCE_TESTIMONY_CURSOR_PURPOSES == (
        "summary",
        "candidates",
        "candidate",
        "sources",
        "contradictions",
        "lineage",
    )


def test_vocabulary_parity_matches_cognition() -> None:
    assert EVIDENCE_SOURCE_KINDS == {item.value for item in EvidenceSourceKind}
    assert EVIDENCE_PROVENANCE_CHANNELS == {
        item.value for item in EvidenceProvenanceChannel
    }
    assert EVIDENCE_INTERPRETATIONS == {
        item.value for item in EvidenceInterpretationKind
    }
    assert EVIDENCE_CUSTODY_STATUSES == {item.value for item in EvidenceCustodyStatus}
    assert EVIDENCE_TRUST_BASES == {item.value for item in EvidenceTrustBasis}
    assert EVIDENCE_CONFIDENCE_BANDS == {"low", "mid", "high"}
    assert EvidenceTestimonyChannel.DIRECT.value == "direct"
    assert EvidenceContradictionKind.INTERPRETATION_CONFLICT.value == (
        "interpretation_conflict"
    )
    assert EVIDENCE_ERROR_CODES
    assert EVIDENCE_NOTICE_REASONS
    with pytest.raises(EvidenceError):
        raise EvidenceError("evidence_invalid_id")


def test_compatibility_pins_are_exact() -> None:
    assert METRIC_FAMILY_COUNT == 168
    assert EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA == "evidence-testimony-snapshot-v1"
    assert DISPUTE_SNAPSHOT_SCHEMA == "dispute-resolution-snapshot-v1"
    assert FORMAL_RULE_SNAPSHOT_SCHEMA == "formal-rule-snapshot-v1"
    assert ORGANIZATION_SNAPSHOT_SCHEMA_VERSION == "organization-snapshot-v3"
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert EVENT_SCHEMA_REPLAY_V22 in ACCEPTED_EVENT_SCHEMA_VERSIONS
    assert "v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v21" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_OWNED_CAPABILITY_FLAGS == frozenset(
        {"organizations", "formal_rules", "legal_disputes", "diplomacy"}
    )
    assert "runner-config-v57" not in (
        ROOT / "src" / "simulation" / "runner_models.py"
    ).read_text(encoding="utf-8")
    assert not list((ROOT / "alembic" / "versions").glob("0018_*.py"))


def test_evidence_analysis_mints_no_foreign_candidate_id() -> None:
    from analysis.evidence_testimony_contract import (
        EVIDENCE_CANDIDATE_PREFIX,
        EVIDENCE_FOREIGN_CANDIDATE_PREFIXES,
    )

    assert EVIDENCE_CANDIDATE_PREFIX == "evid-"
    for prefix in EVIDENCE_FOREIGN_CANDIDATE_PREFIXES:
        assert not EVIDENCE_CANDIDATE_PREFIX.startswith(prefix)


def test_public_facades_export_evidence_entry_points() -> None:
    for module in (cognition, analysis, experiments, simulation, route_facade):
        exported = set(getattr(module, "__all__", ()))
        assert any("Evidence" in name or "evidence" in name for name in exported), (
            module
        )
    assert cognition.EvidenceLedger is EvidenceLedger
    assert simulation.EvidenceLedger is EvidenceLedger
