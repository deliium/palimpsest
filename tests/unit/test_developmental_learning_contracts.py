"""Unit tests for developmental learning domain/source contracts."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.developmental_learning import (
    DEVELOPMENTAL_LEARNING_POLICY_VERSION,
    DevelopmentalDomainId,
    DevelopmentalDomainRate,
    DevelopmentalKnowledgeEntry,
    DevelopmentalSourceId,
    DevelopmentalStageCompose,
    empty_developmental_knowledge_ledger,
    parse_developmental_domain_id,
    parse_developmental_source_id,
    require_owner_developmental_knowledge,
    upsert_developmental_entry,
)
from agents.models import AgentId
from simulation.new_agent_initialization import (
    BLANK_SLATE_SUBJECTIVE_STORES,
    SUBJECTIVE_COPY_DENY_LIST,
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)

_LOG = logging.getLogger("tests.developmental_learning_contracts")


def test_closed_domain_and_source_ids() -> None:
    _LOG.debug("case_id=closed_domain_and_source_ids")
    assert {d.value for d in DevelopmentalDomainId} == {
        "locations",
        "resources",
        "hazards",
        "skills",
        "social_actors",
        "vocabulary",
        "norms",
        "stories",
        "practices",
    }
    assert {s.value for s in DevelopmentalSourceId} == {
        "observation",
        "instruction",
        "imitation",
        "communication",
        "artifact",
        "experimentation",
    }


def test_forbidden_domain_and_source_aliases_rejected() -> None:
    _LOG.debug("case_id=forbidden_aliases_rejected")
    for alias in (
        "culture_pack",
        "encyclopedia",
        "society_memory",
        "inherited_language",
        "student",
        "elder_teacher",
    ):
        with pytest.raises(ValueError, match="forbidden_domain_alias|unknown_domain"):
            parse_developmental_domain_id(alias)
    for alias in (
        "society_download",
        "parent_memory_copy",
        "global_dictionary",
        "analysis_feedback",
    ):
        with pytest.raises(ValueError, match="forbidden_source_alias|unknown_source"):
            parse_developmental_source_id(alias)


def test_empty_ledger_construct_logs_domain_count_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=empty_ledger_construct")
    owner = AgentId("learner-1")
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.developmental_learning"):
        ledger = empty_developmental_knowledge_ledger(owner)
    assert ledger.entries == ()
    assert ledger.policy_version == DEVELOPMENTAL_LEARNING_POLICY_VERSION
    assert "domain_count=0" in caplog.text
    assert_blank_slate_subjective_state(
        owner, BlankSlateStoreCounts(developmental_knowledge=len(ledger.entries))
    )


def test_provenance_less_entry_rejected(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=provenance_less_rejected")
    with caplog.at_level(logging.ERROR, logger="agents.cognition.developmental_learning"):
        with pytest.raises(ValueError, match="provenance_required"):
            DevelopmentalKnowledgeEntry(
                domain_id=DevelopmentalDomainId.LOCATIONS,
                concept_key="loc:alpha",
                source_id=DevelopmentalSourceId.OBSERVATION,
                confidence=0.5,
                acquired_tick=1,
                evidence_refs=(),
            )
    assert "provenance_required" in caplog.text


def test_upsert_requires_provenance_and_writes_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=upsert_with_provenance")
    owner = AgentId("learner-2")
    ledger = empty_developmental_knowledge_ledger(owner)
    entry = DevelopmentalKnowledgeEntry(
        domain_id=DevelopmentalDomainId.RESOURCES,
        concept_key="res:berry",
        source_id=DevelopmentalSourceId.OBSERVATION,
        confidence=0.4,
        acquired_tick=3,
        evidence_refs=("evt:1",),
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.developmental_learning"):
        updated = upsert_developmental_entry(ledger, entry)
    assert len(updated.entries) == 1
    assert updated.entries[0].concept_key == "res:berry"
    assert "developmental_write" in caplog.text


def test_domain_rate_defaults() -> None:
    _LOG.debug("case_id=domain_rate_defaults")
    rate = DevelopmentalDomainRate(base_rate=0.5)
    assert rate.stage_compose is DevelopmentalStageCompose.MULTIPLY_LIFECYCLE_LEARNING_RATE
    assert rate.min_exposures == 0
    assert rate.confidence_floor == 0.0
    with pytest.raises(ValueError, match="out_of_range"):
        DevelopmentalDomainRate(base_rate=0.0)


def test_blank_slate_includes_developmental_knowledge() -> None:
    _LOG.debug("case_id=blank_slate_developmental_knowledge")
    assert "developmental_knowledge" in BLANK_SLATE_SUBJECTIVE_STORES
    assert "developmental_knowledge" in SUBJECTIVE_COPY_DENY_LIST
    for alias in ("society_download", "culture_pack", "encyclopedia", "language_pack"):
        assert alias in SUBJECTIVE_COPY_DENY_LIST
    assert_blank_slate_subjective_state(
        AgentId("entrant-dev"), BlankSlateStoreCounts()
    )
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            AgentId("entrant-dev"),
            BlankSlateStoreCounts(developmental_knowledge=1),
        )


def test_require_owner_rejects_foreign_ledger() -> None:
    _LOG.debug("case_id=require_owner_foreign")
    ledger = empty_developmental_knowledge_ledger(AgentId("a"))
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_developmental_knowledge(
            ledger, AgentId("b"), field_name="test.ledger"
        )
