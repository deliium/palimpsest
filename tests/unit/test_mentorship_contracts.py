"""Unit tests for mentorship content-kind / bond / lineage contracts."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.mentorship import (
    LINEAGE_FIRST_HOP_INDEX,
    MENTORSHIP_POLICY_VERSION,
    MentorshipBond,
    MentorshipBondRole,
    MentorshipContentKindId,
    MentorshipLedger,
    TaughtContentLineageEntry,
    empty_mentorship_ledger,
    parse_mentorship_bond_role,
    parse_mentorship_content_kind,
    require_owner_mentorship,
)
from agents.models import AgentId
from simulation.new_agent_initialization import (
    BLANK_SLATE_SUBJECTIVE_STORES,
    SUBJECTIVE_COPY_DENY_LIST,
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)

_LOG = logging.getLogger("tests.mentorship_contracts")


def test_closed_content_kind_and_role_ids() -> None:
    _LOG.debug("case_id=closed_content_kind_and_role_ids")
    assert {k.value for k in MentorshipContentKindId} == {
        "practical_skills",
        "factual_beliefs",
        "causal_hypotheses",
        "vocabulary",
        "production_recipes",
        "social_practices",
        "stories",
        "warnings",
    }
    assert {r.value for r in MentorshipBondRole} == {"mentor", "apprentice"}
    assert LINEAGE_FIRST_HOP_INDEX == 0


def test_forbidden_content_kind_aliases_rejected() -> None:
    _LOG.debug("case_id=forbidden_content_kind_aliases")
    for alias in (
        "culture_pack",
        "encyclopedia",
        "society_memory",
        "inherited_language",
        "mentor",
        "apprentice",
        "elder_teacher",
        "full_self_model_copy",
        "mentor_pack",
        "apprentice_download",
        "lineage_clone",
    ):
        with pytest.raises(
            ValueError, match="forbidden_content_kind_alias|unknown_content_kind"
        ):
            parse_mentorship_content_kind(alias)


def test_empty_ledger_construct_logs_zero_counts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=empty_ledger_construct")
    owner = AgentId("learner-m1")
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.mentorship"):
        ledger = empty_mentorship_ledger(owner)
    assert ledger.bonds == ()
    assert ledger.lineage == ()
    assert ledger.policy_version == MENTORSHIP_POLICY_VERSION
    assert "bond_count=0" in caplog.text
    assert "lineage_count=0" in caplog.text
    assert_blank_slate_subjective_state(
        owner,
        BlankSlateStoreCounts(
            mentorship_bonds=len(ledger.bonds),
            taught_content_lineage=len(ledger.lineage),
        ),
    )


def test_provenance_less_lineage_rejected(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=provenance_less_lineage_rejected")
    with caplog.at_level(logging.ERROR, logger="agents.cognition.mentorship"):
        with pytest.raises(ValueError, match="provenance_required"):
            TaughtContentLineageEntry(
                teacher_agent_id=AgentId("alice"),
                learner_agent_id=AgentId("bob"),
                content_kind=MentorshipContentKindId.PRACTICAL_SKILLS,
                content_key="skill:forge",
                content_fingerprint="fp:bob:skill:forge",
                lineage_root_id="root:alice:skill:forge",
                hop_index=LINEAGE_FIRST_HOP_INDEX,
                attempt_count=1,
                learning_evidence_count=0,
                confidence=0.4,
                mutated=False,
                acquired_tick=2,
                last_updated_tick=2,
                evidence_refs=(),
            )
    assert "provenance_required" in caplog.text


def test_missing_teacher_rejected() -> None:
    _LOG.debug("case_id=missing_teacher_rejected")
    with pytest.raises(ValueError, match="invalid_type"):
        TaughtContentLineageEntry(
            teacher_agent_id="alice",  # type: ignore[arg-type]
            learner_agent_id=AgentId("bob"),
            content_kind=MentorshipContentKindId.WARNINGS,
            content_key="warn:cliff",
            content_fingerprint="fp:bob:warn:cliff",
            lineage_root_id="root:alice:warn:cliff",
            hop_index=0,
            attempt_count=1,
            learning_evidence_count=1,
            confidence=0.5,
            mutated=False,
            acquired_tick=1,
            last_updated_tick=1,
            evidence_refs=("evt:1",),
        )


def test_bond_and_lineage_construct_ok() -> None:
    _LOG.debug("case_id=bond_and_lineage_construct")
    owner = AgentId("bob")
    bond = MentorshipBond(
        partner_agent_id=AgentId("alice"),
        role=MentorshipBondRole.APPRENTICE,
        content_kinds=(MentorshipContentKindId.PRACTICAL_SKILLS,),
        strength=0.5,
        formed_tick=3,
        last_teaching_tick=4,
    )
    entry = TaughtContentLineageEntry(
        teacher_agent_id=AgentId("alice"),
        learner_agent_id=owner,
        content_kind=MentorshipContentKindId.PRACTICAL_SKILLS,
        content_key="skill:forge",
        content_fingerprint="fp:bob:skill:forge",
        lineage_root_id="root:alice:skill:forge",
        hop_index=LINEAGE_FIRST_HOP_INDEX,
        attempt_count=2,
        learning_evidence_count=1,
        confidence=0.55,
        mutated=False,
        acquired_tick=4,
        last_updated_tick=4,
        evidence_refs=("comm:1",),
    )
    ledger = MentorshipLedger(owner_id=owner, bonds=(bond,), lineage=(entry,))
    assert len(ledger.bonds) == 1
    assert len(ledger.lineage) == 1
    assert entry.lineage_id is not None
    assert parse_mentorship_bond_role("mentor") is MentorshipBondRole.MENTOR


def test_blank_slate_includes_mentorship_counters() -> None:
    _LOG.debug("case_id=blank_slate_mentorship")
    assert "mentorship_bonds" in BLANK_SLATE_SUBJECTIVE_STORES
    assert "taught_content_lineage" in BLANK_SLATE_SUBJECTIVE_STORES
    assert "mentorship_bonds" in SUBJECTIVE_COPY_DENY_LIST
    assert "taught_content_lineage" in SUBJECTIVE_COPY_DENY_LIST
    for alias in ("mentor_pack", "apprentice_download", "lineage_clone"):
        assert alias in SUBJECTIVE_COPY_DENY_LIST
    assert_blank_slate_subjective_state(
        AgentId("entrant-m"), BlankSlateStoreCounts()
    )
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            AgentId("entrant-m"),
            BlankSlateStoreCounts(mentorship_bonds=1),
        )
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            AgentId("entrant-m"),
            BlankSlateStoreCounts(taught_content_lineage=1),
        )


def test_require_owner_rejects_foreign_ledger() -> None:
    _LOG.debug("case_id=require_owner_foreign")
    ledger = empty_mentorship_ledger(AgentId("a"))
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_mentorship(ledger, AgentId("b"), field_name="test.ledger")
