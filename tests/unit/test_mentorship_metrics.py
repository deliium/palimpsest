"""Mentorship fidelity / mutation / bonds metric families."""

from __future__ import annotations

from agents.cognition.mentorship import (
    MentorshipAudit,
    MentorshipBondRole,
    MentorshipContentKindId,
    MentorshipLedger,
    empty_mentorship_ledger,
    form_or_reinforce_mentorship_bond,
    mutate_taught_content_lineage,
    record_taught_content_lineage,
)
from agents.models import AgentId
from analysis.mentorship_metrics import (
    MENTORSHIP_BONDS_METRIC_VERSION,
    MENTORSHIP_FIDELITY_METRIC_VERSION,
    MENTORSHIP_MUTATION_METRIC_VERSION,
    compute_mentorship_bonds,
    compute_mentorship_fidelity,
    compute_mentorship_mutation,
)
from analysis.models import MetricAvailability
from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications


def _audit(
    *,
    owner: str,
    teacher: str,
    hop: int,
    mutated: bool,
    tick: int,
) -> MentorshipAudit:
    return MentorshipAudit(
        owner_id=AgentId(owner),
        partner_agent_id=AgentId(teacher),
        role=MentorshipBondRole.APPRENTICE,
        content_kind=MentorshipContentKindId.PRACTICAL_SKILLS,
        hop_index=hop,
        attempt_count=1,
        learning_evidence_count=1,
        confidence_band="mid",
        mutated=mutated,
        tick=tick,
        reason_code="teaching_uptake",
    )


def test_metric_family_count_includes_mentorship() -> None:
    specs = all_metric_specifications()
    assert len(specs) == METRIC_FAMILY_COUNT == 68
    ids = {spec.family_id.value for spec in specs}
    assert {
        "mentorship_fidelity",
        "mentorship_mutation",
        "mentorship_bonds",
    } <= ids


def test_alice_bob_carol_david_fidelity_and_mutation() -> None:
    """Alice→Bob→Carol→David: hops 0..3; mutation on Carol's re-teach."""
    audits = (
        _audit(owner="bob", teacher="alice", hop=0, mutated=False, tick=1),
        _audit(owner="carol", teacher="bob", hop=1, mutated=False, tick=2),
        _audit(owner="david", teacher="carol", hop=2, mutated=True, tick=3),
        _audit(owner="erin", teacher="david", hop=3, mutated=True, tick=4),
    )
    fidelity = compute_mentorship_fidelity(
        audits, run_id="run-ak-fid", input_revision="rev-1"
    )
    assert fidelity.algorithm_version == "1"
    assert fidelity.availability is MetricAvailability.PRESENT
    assert fidelity.values["faithful_share"] == 0.5
    assert fidelity.values["max_hop_index"] == 3
    assert MENTORSHIP_FIDELITY_METRIC_VERSION.endswith("@1")

    mutation = compute_mentorship_mutation(
        audits, run_id="run-ak-mut", input_revision="rev-1"
    )
    assert mutation.availability is MetricAvailability.PRESENT
    assert mutation.values["mutated_count"] == 2
    assert mutation.values["mutation_rate"] == 0.5
    assert MENTORSHIP_MUTATION_METRIC_VERSION.endswith("@1")

    bob = empty_mentorship_ledger(AgentId("bob"))
    bob = form_or_reinforce_mentorship_bond(
        bob,
        partner_agent_id=AgentId("alice"),
        owner_role=MentorshipBondRole.APPRENTICE,
        content_kinds=(MentorshipContentKindId.PRACTICAL_SKILLS,),
        tick=1,
        successful_act_count=2,
        projected_trust=0.7,
        form_after_successful_acts=1,
        min_trust=0.1,
        reinforce_on_learning_evidence=True,
        initial_strength=0.6,
    )
    bonds = compute_mentorship_bonds(
        audits,
        run_id="run-ak-bonds",
        input_revision="rev-1",
        ledgers=(bob,),
    )
    assert bonds.availability is MetricAvailability.PRESENT
    assert bonds.values["active_bond_count"] == 1
    assert MENTORSHIP_BONDS_METRIC_VERSION.endswith("@1")


def test_lineage_mutation_sets_mutated_flag() -> None:
    ledger = empty_mentorship_ledger(AgentId("carol"))
    ledger = record_taught_content_lineage(
        ledger,
        teacher_agent_id=AgentId("bob"),
        content_kind=MentorshipContentKindId.PRACTICAL_SKILLS,
        content_key="skill:foraging",
        content_fingerprint="fp:bob:foraging:high",
        tick=1,
        evidence_refs=("occ-1",),
        confidence=0.5,
        uptake_succeeded=True,
        record_attempts=True,
        max_hop_depth=4,
        parent_lineage_id="lin-bob-1",
        lineage_root_id="root-alice",
        parent_hop_index=0,
    )
    lineage_id = ledger.lineage[0].lineage_id
    assert lineage_id is not None
    mutated = mutate_taught_content_lineage(
        ledger,
        lineage_id=lineage_id,
        content_fingerprint="fp:carol:foraging:revised",
        confidence=0.4,
        tick=2,
        allow_learner_mutation=True,
        mutation_requires_evidence=True,
        owner_evidence_present=True,
    )
    assert type(mutated) is MentorshipLedger
    assert mutated.lineage[0].mutated is True
