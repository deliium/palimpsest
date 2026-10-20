"""Typed mediation undertaking compilation and attempt attribution."""

from __future__ import annotations

from agents.cognition.mediation import (
    MediationCase,
    MediationCaseStatus,
    MediationEvidence,
    MediationEvidenceChannel,
    MediationLedger,
    MediationRecommendation,
    MediationRecommendationStatus,
    mediation_case_id,
    mediation_evidence_id,
    mediation_recommendation_id,
)
from agents.cognition.mediation_actions import (
    compile_mediation_undertaking,
    record_mediation_attempt,
    selected_mediation_recommendation,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.actions import Give, Wait
from world.identifiers import EntityId

_OWNER = AgentId("ada")
_PARTY = AgentId("bob")
_CASE = "f" * 64
_CONTEXT = "a" * 16


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=_PARTY, entity_id=EntityId("body-bob")),
        ),
    )


def _ledger(
    *,
    item_token: str = "bread",
    action: str = "give",
    proposed: AgentId = _OWNER,
    window_last: int = 8,
) -> MediationLedger:
    evidence = MediationEvidence(
        evidence_id=mediation_evidence_id(
            _CASE, 0, MediationEvidenceChannel.OBSERVED, "lineage"
        ),
        ordinal=0,
        channel=MediationEvidenceChannel.OBSERVED,
        lineage_ref="lineage",
        root_ref="root",
        tick=1,
    )
    case = MediationCase(
        case_id=mediation_case_id(_OWNER, _CASE),
        owner_id=_OWNER,
        case_ref=_CASE,
        subject_token="item_share",
        context_key=_CONTEXT,
        status=MediationCaseStatus.UNRESOLVED,
        first_tick=1,
        last_tick=1,
        window_first_tick=1,
        window_last_tick=window_last,
        origin_id=_PARTY,
        party_ids=(_PARTY, AgentId("carol")),
        evidence=(evidence,),
    )
    recommendation = MediationRecommendation(
        recommendation_id=mediation_recommendation_id(_OWNER, _CASE, 0),
        owner_id=_OWNER,
        case_ref=_CASE,
        revision=0,
        proposed_actor_id=proposed,
        action_token=action,
        first_tick=1,
        last_tick=1,
        window_first_tick=1,
        window_last_tick=window_last,
        target_ids=(_PARTY,),
        item_token=item_token,
        terms=("return_item",),
    )
    return MediationLedger(
        owner_id=_OWNER,
        cases=(case,),
        recommendations=(recommendation,),
        first_observed_tick=1,
        last_observed_tick=1,
        observation_count=1,
    )


def test_named_non_food_item_compiles_to_give() -> None:
    ledger = _ledger()
    compiled = compile_mediation_undertaking(
        ledger,
        owner_id=_OWNER,
        tick=2,
        identity=_identity(),
        inventory=(EntityId("bread"), EntityId("stone")),
    )
    assert compiled is not None
    recommendation, command = compiled
    assert recommendation.revision == 0
    assert type(command) is Give
    assert command.item_id == EntityId("bread")
    assert command.recipient_id == EntityId("body-bob")


def test_unavailable_or_altered_item_is_not_substituted() -> None:
    ledger = _ledger(item_token="apple")
    assert (
        compile_mediation_undertaking(
            ledger,
            owner_id=_OWNER,
            tick=2,
            identity=_identity(),
            inventory=(EntityId("bread"),),
        )
        is None
    )
    assert (
        compile_mediation_undertaking(
            _ledger(action="feed"),
            owner_id=_OWNER,
            tick=2,
            identity=_identity(),
            inventory=(EntityId("bread"),),
        )
        is None
    )


def test_superseded_recommendation_is_not_actionable() -> None:
    ledger = _ledger()
    recommendation = ledger.recommendations[0]
    from dataclasses import replace

    superseded = replace(
        recommendation, status=MediationRecommendationStatus.SUPERSEDED
    )
    ledger = replace(ledger, recommendations=(superseded,))
    assert selected_mediation_recommendation(ledger, _OWNER, 2) is None


def test_expired_window_blocks_compilation() -> None:
    ledger = _ledger(window_last=3)
    assert (
        compile_mediation_undertaking(
            ledger,
            owner_id=_OWNER,
            tick=4,
            identity=_identity(),
            inventory=(EntityId("bread"),),
        )
        is None
    )


def test_attempt_attribution_uses_matching_final_command() -> None:
    ledger = _ledger()
    recommendation = ledger.recommendations[0]
    updated = record_mediation_attempt(
        ledger,
        recommendation,
        owner_id=_OWNER,
        tick=2,
        final_command=Give(
            recipient_id=EntityId("body-bob"), item_id=EntityId("bread")
        ),
        identity=_identity(),
    )
    assert len(updated.attempts) == 1
    attempt = updated.attempts[0]
    assert attempt.recommendation_revision == recommendation.revision
    assert attempt.item_token == "bread"
    assert attempt.resulting_command_token == "give"
    for mismatched in (
        Wait(),
        Give(recipient_id=EntityId("body-carol"), item_id=EntityId("bread")),
        Give(recipient_id=EntityId("body-bob"), item_id=EntityId("stone")),
    ):
        untouched = record_mediation_attempt(
            ledger,
            recommendation,
            owner_id=_OWNER,
            tick=2,
            final_command=mismatched,
            identity=_identity(),
        )
        assert untouched == ledger


def test_compiled_and_attributed_restitution_is_measured_once() -> None:
    from analysis.mediation import (
        MediationEffectRow,
        compute_conflict_mediation,
        harvest_mediation_snapshot,
    )

    ledger = _ledger()
    compiled = compile_mediation_undertaking(
        ledger,
        owner_id=_OWNER,
        tick=2,
        identity=_identity(),
        inventory=(EntityId("bread"),),
    )
    assert compiled is not None
    recommendation, command = compiled
    attributed = record_mediation_attempt(
        ledger,
        recommendation,
        owner_id=_OWNER,
        tick=2,
        final_command=command,
        identity=_identity(),
    )
    snapshot = harvest_mediation_snapshot(attributed)
    document = compute_conflict_mediation(
        (snapshot,),
        run_id="run-restitution",
        input_revision="rev-1",
        tick=3,
        effects=(
            MediationEffectRow(
                actor_id=_OWNER.value,
                recipient_id=_PARTY.value,
                item_token="bread",
                tick=2,
            ),
        ),
    )
    assert document.values["attempted_follow_through_count"] == 1
    assert document.values["effected_follow_through_count"] == 1
    assert document.values["ambiguous_effect_count"] == 0
