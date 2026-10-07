"""Uptake compose adapters for practical-knowledge genealogy."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from agents.cognition.practical_knowledge import (
    KnowledgeTransmissionOrigin,
    apply_practical_knowledge_compose,
    apply_practical_knowledge_from_imitation,
    apply_practical_knowledge_from_independent_discovery,
    apply_practical_knowledge_from_reconstruction,
    apply_practical_knowledge_from_teaching,
    apply_practical_knowledge_from_written_record,
    empty_practical_knowledge_ledger,
)
from agents.models import AgentId
from simulation.runner_models import KnowledgeGenealogyUptakeCompose

_LOG = logging.getLogger("tests.practical_knowledge_compose")
_KINDS = (
    "foraging_method",
    "healing_technique",
    "crafting_process",
    "navigation_knowledge",
    "building_method",
)


def test_teaching_compose_sets_source_from_public_cue(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=teaching_compose")
    ledger = empty_practical_knowledge_ledger(AgentId("learner"))
    advice = (
        SimpleNamespace(
            source_agent_id=AgentId("alice"),
            domain=SimpleNamespace(value="foraging"),
            band=SimpleNamespace(value="high"),
            occurrence_id="occ-1",
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.practical_knowledge"):
        updated, audits = apply_practical_knowledge_from_teaching(
            ledger,
            enabled_kinds=_KINDS,
            advice_delta=advice,
            tick=3,
            teaching_compose_on=True,
            teaching_mode_on=True,
            mentorship_channel_on=True,
        )
    assert updated.entries
    entry = updated.entries[0]
    assert entry.origin is KnowledgeTransmissionOrigin.TEACHING
    assert entry.source_agent_id == AgentId("alice")
    assert entry.teacher_agent_id == AgentId("alice")
    assert entry.parent_entry_ids == ()
    assert entry.hop_index == 1
    assert entry.content_key == "tech:foraging"
    assert "alice" not in entry.content_key
    assert audits
    assert "practical_knowledge_compose" in caplog.text


def test_teaching_compose_skips_when_mode_off(caplog: pytest.LogCaptureFixture) -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("learner"))
    advice = (
        SimpleNamespace(
            source_agent_id=AgentId("alice"),
            domain=SimpleNamespace(value="foraging"),
            band=SimpleNamespace(value="high"),
            occurrence_id="occ-1",
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.practical_knowledge"):
        updated, audits = apply_practical_knowledge_from_teaching(
            ledger,
            enabled_kinds=_KINDS,
            advice_delta=advice,
            tick=1,
            teaching_compose_on=True,
            teaching_mode_on=False,
            mentorship_channel_on=False,
        )
    assert updated.entries == ()
    assert audits == ()
    assert "teaching_mode_off" in caplog.text


def test_teaching_skips_non_technique_domains(caplog: pytest.LogCaptureFixture) -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("learner"))
    advice = (
        SimpleNamespace(
            source_agent_id=AgentId("alice"),
            domain=SimpleNamespace(value="communication"),
            band=SimpleNamespace(value="high"),
            occurrence_id="occ-2",
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.practical_knowledge"):
        updated, _ = apply_practical_knowledge_from_teaching(
            ledger,
            enabled_kinds=_KINDS,
            advice_delta=advice,
            tick=1,
            teaching_compose_on=True,
            teaching_mode_on=True,
        )
    assert updated.entries == ()
    assert "domain_skipped:communication" in caplog.text


def test_imitation_compose_does_not_embed_peer_id() -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("bob"))
    observation = SimpleNamespace(
        occurrences=(
            SimpleNamespace(
                kind="craft_success",
                other_entity_id=SimpleNamespace(value="entity-alice"),
                success=True,
                provenance=None,
            ),
        )
    )
    updated, audits = apply_practical_knowledge_from_imitation(
        ledger,
        enabled_kinds=_KINDS,
        observation=observation,
        tick=2,
        imitation_compose_on=True,
    )
    assert updated.entries
    entry = updated.entries[0]
    assert entry.origin is KnowledgeTransmissionOrigin.IMITATION
    assert entry.content_key == "tech:craft_success"
    assert "entity-alice" not in entry.content_key
    assert "actor:entity-alice" in entry.evidence_refs
    assert audits


def test_written_record_compose_from_artifact_cue() -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("bob"))
    artifacts = SimpleNamespace(
        interpretations=(
            SimpleNamespace(
                artifact_id="mark-9",
                record_genre=SimpleNamespace(value="instruction"),
                author_id=AgentId("scribe"),
            ),
        )
    )
    updated, audits = apply_practical_knowledge_from_written_record(
        ledger,
        enabled_kinds=_KINDS,
        observation=None,
        artifact_interpretations=artifacts,
        tick=4,
        written_compose_on=True,
        artifacts_on=True,
        durable_on=False,
        repositories_on=False,
    )
    assert updated.entries
    entry = updated.entries[0]
    assert entry.origin is KnowledgeTransmissionOrigin.WRITTEN_RECORD
    assert entry.source_agent_id == AgentId("scribe")
    assert audits


def test_written_record_skips_when_artifacts_off(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("bob"))
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.practical_knowledge"):
        updated, _ = apply_practical_knowledge_from_written_record(
            ledger,
            enabled_kinds=_KINDS,
            observation=None,
            artifact_interpretations=None,
            tick=1,
            written_compose_on=True,
            artifacts_on=False,
            durable_on=False,
            repositories_on=False,
        )
    assert updated.entries == ()
    assert "artifacts_off" in caplog.text


def test_reconstruction_skips_when_memory_off(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("bob"))
    observation = SimpleNamespace(
        occurrences=(
            SimpleNamespace(
                kind="partial_forage_recall",
                other_entity_id=None,
                success=None,
                provenance=None,
            ),
        )
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.practical_knowledge"):
        updated, _ = apply_practical_knowledge_from_reconstruction(
            ledger,
            enabled_kinds=_KINDS,
            observation=observation,
            tick=1,
            reconstruction_compose_on=True,
            reconstructive_memory_on=False,
        )
    assert updated.entries == ()
    assert "reconstructive_memory_off" in caplog.text


def test_reconstruction_compose_when_memory_on() -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("bob"))
    observation = SimpleNamespace(
        occurrences=(
            SimpleNamespace(
                kind="partial_forage_recall",
                other_entity_id=None,
                success=None,
                provenance=None,
            ),
        )
    )
    updated, audits = apply_practical_knowledge_from_reconstruction(
        ledger,
        enabled_kinds=_KINDS,
        observation=observation,
        tick=5,
        reconstruction_compose_on=True,
        reconstructive_memory_on=True,
    )
    assert updated.entries
    assert updated.entries[0].origin is KnowledgeTransmissionOrigin.RECONSTRUCTION
    assert audits


def test_independent_discovery_from_own_success() -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("bob"))
    observation = SimpleNamespace(
        occurrences=(
            SimpleNamespace(
                kind="forage_experiment",
                other_entity_id=None,
                success=True,
                provenance=None,
            ),
        )
    )
    updated, audits = apply_practical_knowledge_from_independent_discovery(
        ledger,
        enabled_kinds=_KINDS,
        observation=observation,
        tick=6,
        independent_compose_on=True,
    )
    assert updated.entries
    entry = updated.entries[0]
    assert entry.origin is KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY
    assert entry.hop_index == 0
    assert entry.parent_entry_ids == ()
    assert audits


def test_orchestrator_respects_all_compose_flags_off() -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("bob"))
    advice = (
        SimpleNamespace(
            source_agent_id=AgentId("alice"),
            domain=SimpleNamespace(value="foraging"),
            band=SimpleNamespace(value="high"),
            occurrence_id="occ-1",
        ),
    )
    updated, audits = apply_practical_knowledge_compose(
        ledger,
        enabled_kinds=_KINDS,
        tick=1,
        uptake_compose=KnowledgeGenealogyUptakeCompose(),
        advice_delta=advice,
        teaching_mode_on=True,
    )
    assert updated.entries == ()
    assert audits == ()
