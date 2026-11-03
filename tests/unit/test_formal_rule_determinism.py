"""V4-06 deterministic updates and analysis identity."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agents.cognition import (
    apply_formal_rule_update,
    formal_rule_ledger_digest,
)
from agents.cognition.social_norms import (
    NormBelief,
    NormContext,
    NormExpectation,
    NormLedger,
    NormPattern,
    NormStatus,
    norm_belief_id,
)
from agents.models import AgentId
from analysis.formal_rule_evidence import build_formal_rule_windows
from analysis.formal_rule_lineage import (
    derive_formal_rule_lineage,
    summarize_formal_rules,
)
from analysis.formal_rules import harvest_formal_rule_rows
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation, ObservedArtifact, ObservedItemPlacement

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
SCOPE_DIGEST = hashlib.sha256(b"determinism").hexdigest()
SRC = Path(__file__).resolve().parents[2] / "src"


def _norm(pattern: NormPattern, expectation: NormExpectation) -> NormLedger:
    return NormLedger(
        owner_id=OWNER,
        beliefs=(
            NormBelief(
                belief_id=norm_belief_id(OWNER, pattern),
                owner_id=OWNER,
                pattern=pattern,
                expectation=expectation,
                context=NormContext(pattern=pattern),
                status=NormStatus.ACTIVE,
                confidence=0.7,
            ),
        ),
    )


def _observation(tick: int = 0, *, artifact: bool = False) -> Observation:
    artifacts: tuple[ObservedArtifact, ...] = ()
    if artifact:
        artifacts = (
            ObservedArtifact(
                entity_id=EntityId("artifact-1"),
                kind=ArtifactKind.RECORD,
                author_id=EntityId("body-1"),
                created_tick=tick,
                content=ArtifactContent(),
                content_revision=1,
                placement=ObservedItemPlacement.GROUND_HERE,
                record_genre=DurableRecordGenre.AGREEMENT,
                integrity=RecordIntegrity.INTACT,
            ),
        )
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(tick),
        tick=tick,
        artifacts=artifacts,
    )


def _interpretations() -> SimpleNamespace:
    return SimpleNamespace(
        interpretations=(
            SimpleNamespace(
                artifact_id=EntityId("artifact-1"),
                reading_marks=("maintain",),
                reading_relations=(),
            ),
        )
    )


def test_repeated_updates_are_byte_identical() -> None:
    norm = _norm(NormPattern.SHARED_UPKEEP, NormExpectation.MAINTAIN_STRUCTURE)
    first = apply_formal_rule_update(OWNER, 1, _observation(), None, social_norms=norm)
    second = apply_formal_rule_update(OWNER, 1, _observation(), None, social_norms=norm)
    assert formal_rule_ledger_digest(first) == formal_rule_ledger_digest(second)
    assert first == second


def test_shuffled_evidence_produces_the_same_digest() -> None:
    upkeep = _norm(
        NormPattern.SHARED_UPKEEP, NormExpectation.MAINTAIN_STRUCTURE
    ).beliefs[0]
    give_back = _norm(
        NormPattern.RETURN_TRANSFER, NormExpectation.GIVE_BACK
    ).beliefs[0]
    left = NormLedger(owner_id=OWNER, beliefs=(upkeep, give_back))
    right = NormLedger(owner_id=OWNER, beliefs=(give_back, upkeep))
    first = apply_formal_rule_update(
        OWNER, 1, _observation(), None, social_norms=left
    )
    second = apply_formal_rule_update(
        OWNER, 1, _observation(), None, social_norms=right
    )
    assert len(first.rules) == 2
    assert first == second
    assert formal_rule_ledger_digest(first) == formal_rule_ledger_digest(second)


def test_shuffled_communications_produce_the_same_ledger() -> None:
    from agents.cognition.formal_rule_communication import (
        FormalRuleAct,
        FormalRuleClaim,
        formal_rule_claim_relation,
    )
    from world.communications import (
        CommunicationRelation,
        CommunicationSourceBasis,
        origin_utterance,
    )
    from world.identifiers import EventId
    from world.observations import (
        ObservationProvenance,
        ObservationSourceKind,
        ObservedCommunication,
    )

    norm = _norm(NormPattern.SHARED_UPKEEP, NormExpectation.MAINTAIN_STRUCTURE)
    base = apply_formal_rule_update(
        OWNER, 1, _observation(), None, social_norms=norm
    )
    rule = base.rules[0]

    acts = (
        FormalRuleAct.SUPPORT,
        FormalRuleAct.SUPPORT,
        FormalRuleAct.OPPOSE,
    )
    communications: list[ObservedCommunication] = []
    for ordinal, act in enumerate(acts):
        claim = FormalRuleClaim(
            act=act, system_ref=rule.system_id, rule_ref=rule.rule_id
        )
        subject, predicate, obj = formal_rule_claim_relation(claim)
        relation = CommunicationRelation(
            subject=subject, predicate=predicate, object=obj
        )
        utterance = origin_utterance(
            text="rule",
            speaker_id=EntityId(f"body-{ordinal + 2}"),
            communication_id=f"comm-{ordinal}",
            relations=(relation,),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        )
        communications.append(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=1,
                    source_event_id=EventId(f"event-{ordinal}"),
                ),
                speaker_id=EntityId(f"body-{ordinal + 2}"),
                listener_id=EntityId("body-1"),
                utterance=utterance,
                action_kind="talk",
            )
        )

    def observed(order: tuple[int, ...]) -> Observation:
        return Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(2),
            tick=2,
            communications=tuple(communications[index] for index in order),
        )

    first = apply_formal_rule_update(
        OWNER, 2, observed((0, 1, 2)), base, social_norms=norm
    )
    second = apply_formal_rule_update(
        OWNER, 2, observed((2, 0, 1)), base, social_norms=norm
    )
    assert first == second
    assert formal_rule_ledger_digest(first) == formal_rule_ledger_digest(second)
    assert len(first.rules[0].evidence) > len(rule.evidence)


def test_candidate_identity_is_reproducible() -> None:
    from tests.unit.formal_rule_helpers import make_ledger

    first = harvest_formal_rule_rows([make_ledger(ticks=(0, 100))], window_ticks=100)
    second = harvest_formal_rule_rows([make_ledger(ticks=(0, 100))], window_ticks=100)
    first_windows = build_formal_rule_windows(first, window_ticks=100)
    second_windows = build_formal_rule_windows(second, window_ticks=100)
    first_analysis = derive_formal_rule_lineage(first, first_windows)
    second_analysis = derive_formal_rule_lineage(second, second_windows)
    assert [record.candidate_id for record in first_analysis.records] == [
        record.candidate_id for record in second_analysis.records
    ]
    assert summarize_formal_rules(first, first_analysis).determinism_digest == (
        summarize_formal_rules(second, second_analysis).determinism_digest
    )


def test_no_hash_uuid_or_wall_clock_in_formal_rule_domain() -> None:
    for path in sorted(SRC.glob("agents/cognition/formal_rule*.py")) + sorted(
        SRC.glob("analysis/formal_rule*.py")
    ):
        source = path.read_text(encoding="utf-8")
        assert "hash(" not in source, path
        assert "uuid4" not in source, path
        assert "time.time" not in source, path
        assert "datetime.now" not in source, path


def test_metric_documents_are_permutation_invariant() -> None:
    from analysis.formal_rule_evidence import build_formal_rule_windows
    from analysis.formal_rule_layers import project_formal_rule_layers
    from analysis.formal_rule_lineage import (
        derive_formal_rule_lineage,
        summarize_formal_rules,
    )
    from analysis.formal_rule_metrics import compute_formal_rule_development_metric
    from tests.unit.formal_rule_helpers import make_ledger

    def documents(*ledgers: Any) -> Any:
        rows = harvest_formal_rule_rows(ledgers, window_ticks=100)
        windows = build_formal_rule_windows(rows, window_ticks=100)
        analysis = derive_formal_rule_lineage(rows, windows)
        summary = summarize_formal_rules(rows, analysis)
        layers = project_formal_rule_layers(rows, analysis, summary, windows=windows)
        return compute_formal_rule_development_metric(
            summary, layers, run_id="run-1", input_revision="revision-1"
        )

    first = documents(
        make_ledger(owner="agent-1"), make_ledger(owner="agent-2", action="attack")
    )
    second = documents(
        make_ledger(owner="agent-2", action="attack"), make_ledger(owner="agent-1")
    )
    assert first.values == second.values
