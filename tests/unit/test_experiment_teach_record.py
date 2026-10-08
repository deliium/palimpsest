"""Teach and record cite an experiment only after the owner remembers it."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.cognition.experimentation import cite_experiment_event
from agents.cognition.memory import build_direct_observation_memory_trace
from agents.cognition.practical_knowledge import (
    apply_practical_knowledge_from_teaching,
    empty_practical_knowledge_ledger,
)
from agents.models import AgentId
from world.actions import Inscribe, Tell
from world.artifacts import ArtifactContent, ArtifactKind
from world.communications import origin_utterance
from world.identifiers import EntityId, EventId, WorldRevision
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)

_OWNER = AgentId("owner-1")
_PEER = AgentId("peer-1")
_ROOT = Path(__file__).resolve().parents[2]


def _trace(owner: AgentId, event_id: str):
    occurrence = ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId(event_id),
        ),
        kind="experiment_resolved",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId("body-1"),
        other_entity_id=EntityId("item-a"),
        public_facts={
            "kind": "experiment_resolved",
            "outcome_class": "success",
            "delta": "none",
            "operator": "combine",
            "discovery_mode": "deliberate",
        },
    )
    return build_direct_observation_memory_trace(
        owner_id=owner,
        observation_tick=2,
        observation_revision=WorldRevision(1),
        occurrence=occurrence,
        location_id=EntityId("loc-1"),
    )


def test_resolver_does_not_emit_tell_or_inscribe() -> None:
    source = (_ROOT / "src" / "world" / "_experiment_apply.py").read_text(
        encoding="utf-8"
    )
    rules = (_ROOT / "src" / "world" / "_rules.py").read_text(encoding="utf-8")
    assert "Tell(" not in source
    assert "Inscribe(" not in source
    assert "class ExperimentResolved" not in source
    apply_slice = rules.split("def _apply_experiment", 1)[1].split(
        "\ndef ", 1
    )[0]
    assert "Tell(" not in apply_slice
    assert "Inscribe(" not in apply_slice


def test_later_tell_and_inscribe_cite_the_remembered_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    traces = (_trace(_OWNER, "evt-exp-1"), _trace(_PEER, "evt-peer"))
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.experimentation"):
        taught = cite_experiment_event(
            _OWNER,
            traces,
            "evt-exp-1",
            "tech:combine_items",
            channel="teach",
        )
        recorded = cite_experiment_event(
            _OWNER,
            traces,
            "evt-exp-1",
            "tech:combine_items",
            channel="record",
        )
    assert taught is not None and recorded is not None
    assert taught.event_ref == "evt:evt-exp-1"
    assert recorded.event_ref == "evt:evt-exp-1"
    tell = Tell(
        recipient_id=EntityId("body-2"),
        utterance=origin_utterance(text="shown", speaker_id=EntityId("body-1")),
    )
    inscribe = Inscribe(kind=ArtifactKind.NOTE, content=ArtifactContent())
    assert tell.kind == "tell"
    assert inscribe.kind == ArtifactKind.NOTE
    knowledge = empty_practical_knowledge_ledger(_OWNER)
    updated, _audits = apply_practical_knowledge_from_teaching(
        knowledge,
        enabled_kinds=("foraging_method",),
        advice_delta=(
            SimpleNamespace(
                source_agent_id=_OWNER,
                domain=SimpleNamespace(value="foraging"),
                band=SimpleNamespace(value="high"),
                occurrence_id="occ-1",
            ),
        ),
        tick=3,
        teaching_compose_on=True,
        teaching_mode_on=True,
        experiment_event_ref=taught.event_ref,
    )
    assert taught.event_ref in updated.entries[0].evidence_refs
    assert "experiment_teach_cited event_id=evt-exp-1" in caplog.text
    assert "experiment_record_cited event_id=evt-exp-1" in caplog.text
    assert cite_experiment_event(
        _OWNER, traces, "evt-peer", "tech:combine_items", channel="teach"
    ) is None


def test_empty_technique_token_skips_the_label_and_keeps_the_trace(
    caplog: pytest.LogCaptureFixture,
) -> None:
    trace = _trace(_OWNER, "evt-exp-1")
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.experimentation"):
        cited = cite_experiment_event(
            _OWNER, (trace,), "evt-exp-1", "", channel="record"
        )
    assert cited is not None
    assert cited.event_ref == "evt:evt-exp-1"
    assert cited.technique_label == ""
    assert trace.provenance.observed_source_id == EventId("evt-exp-1")
    assert "experiment_label_skipped event_id=evt-exp-1" in caplog.text
