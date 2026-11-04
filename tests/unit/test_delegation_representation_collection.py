"""V4-09 collection: claims, positions, revocations, anchors, owner speech."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from agents.cognition import (
    RepresentationDurationKind,
    RepresentationPositionStance,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationRecognitionBasis,
    RepresentationScopeKind,
    RepresentationStatus,
    default_representation_policy,
)
from agents.cognition.delegation_representation import (
    RepresentationError,
    RepresentationLedger,
    apply_representation_update,
    empty_representation_ledger,
    record_representation_utterance,
    representation_ledger_digest,
)
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
    representation_frame_relation,
)
from world.actions import Tell
from world.communications import origin_utterance
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_OWNER = "agent-owner"
_PRINCIPAL = "agent-principal"
_REP = "agent-representative"
_MANDATE = None


def _frame(
    act: RepresentationAct,
    *,
    mandate_ref: str | None = None,
    principal_kind: RepresentationPrincipalKind = RepresentationPrincipalKind.AGENT,
    principal_ref: str | None = _PRINCIPAL,
    representative_ref: str = _REP,
    scope_kind: RepresentationScopeKind = RepresentationScopeKind.SPEAK_FOR,
    scope_subject: str | None = "border",
    duration_kind: RepresentationDurationKind = (
        RepresentationDurationKind.UNTIL_REVOKED
    ),
    end_tick: int | None = None,
    provenance: RepresentationProvenance = RepresentationProvenance.SELF_DECLARED,
    actor_ref: str | None = _REP,
    revision: int = 0,
) -> RepresentationFrame:
    if act in {RepresentationAct.CLAIM, RepresentationAct.DELEGATE}:
        mandate_ref = None
    elif mandate_ref is None:
        mandate_ref = "rmd-" + "1" * 16
    return RepresentationFrame(
        act=act,
        mandate_ref=mandate_ref,
        principal_kind=principal_kind,
        principal_ref=principal_ref,
        representative_ref=representative_ref,
        scope_kind=scope_kind,
        scope_subject=scope_subject,
        duration_kind=duration_kind,
        end_tick=end_tick,
        provenance=provenance,
        revision=revision,
        actor_ref=actor_ref,
    )


def _apply(
    prior: Any = None,
    *frames: RepresentationFrame,
    tick: int = 1,
    observation: object | None = None,
    organization_concepts: object | None = None,
    collective_decisions: object | None = None,
    offices: object | None = None,
    formal_rules: object | None = None,
) -> RepresentationLedger:
    return apply_representation_update(
        owner_id=_OWNER,
        tick=tick,
        observation=observation,
        prior=prior,
        frames=frames,
        organization_concepts=organization_concepts,
        collective_decisions=collective_decisions,
        offices=offices,
        formal_rules=formal_rules,
        policy=default_representation_policy(),
    )


def _communication(frame: RepresentationFrame, speaker: str) -> object:
    return SimpleNamespace(
        speaker_id=EntityId(speaker),
        utterance=origin_utterance(
            text="representation",
            speaker_id=EntityId(speaker),
            relations=(representation_frame_relation(frame),),
        ),
    )


def test_self_claim_is_claimed_only() -> None:
    ledger = _apply(None, _frame(RepresentationAct.CLAIM))
    assert len(ledger.mandates) == 1
    mandate = ledger.mandates[0]
    assert mandate.status is RepresentationStatus.CLAIMED
    assert mandate.recognition_basis is RepresentationRecognitionBasis.NONE
    assert mandate.principal_resolved is True
    assert mandate.provenance is RepresentationProvenance.SELF_DECLARED


def test_agent_principal_delegation_is_recognized() -> None:
    ledger = _apply(
        None,
        _frame(
            RepresentationAct.DELEGATE,
            representative_ref="agent-c",
            actor_ref=_PRINCIPAL,
        ),
    )
    mandate = ledger.mandates[0]
    assert mandate.status is RepresentationStatus.RECOGNIZED
    assert mandate.recognition_basis is (
        RepresentationRecognitionBasis.PRINCIPAL_DECLARATION
    )
    assert mandate.principal_declared is True
    assert mandate.representative_id == "agent-c"


def test_duplicate_claim_increments_revision() -> None:
    first = _apply(None, _frame(RepresentationAct.CLAIM))
    second = _apply(first, _frame(RepresentationAct.CLAIM), tick=2)
    assert len(second.mandates) == 1
    assert second.mandates[0].revision == 1
    assert "representation_duplicate_claim" in second.notices


def test_support_and_opposition_are_retained_and_status_is_contested() -> None:
    claimed = _apply(None, _frame(RepresentationAct.CLAIM))
    mandate_id = claimed.mandates[0].mandate_id
    supported = _apply(
        claimed,
        _frame(
            RepresentationAct.SUPPORT,
            mandate_ref=mandate_id,
            actor_ref="agent-c",
        ),
        tick=2,
    )
    contested = _apply(
        supported,
        _frame(
            RepresentationAct.OPPOSE,
            mandate_ref=mandate_id,
            actor_ref="agent-d",
        ),
        tick=3,
    )
    assert contested.mandates[0].status is RepresentationStatus.CONTESTED
    assert len([row for row in contested.positions if row.active]) == 2
    assert {row.stance for row in contested.positions} == {
        RepresentationPositionStance.SUPPORT,
        RepresentationPositionStance.OPPOSE,
    }


def test_stance_replacement_deactivates_old_row() -> None:
    claimed = _apply(None, _frame(RepresentationAct.CLAIM))
    mandate_id = claimed.mandates[0].mandate_id
    supported = _apply(
        claimed,
        _frame(RepresentationAct.SUPPORT, mandate_ref=mandate_id, actor_ref="agent-c"),
        tick=2,
    )
    opposed = _apply(
        supported,
        _frame(RepresentationAct.OPPOSE, mandate_ref=mandate_id, actor_ref="agent-c"),
        tick=3,
    )
    active = [row for row in opposed.positions if row.active]
    inactive = [row for row in opposed.positions if not row.active]
    assert len(active) == 1
    assert active[0].stance is RepresentationPositionStance.OPPOSE
    assert len(inactive) == 1


def test_collective_accept_is_downgraded_to_support() -> None:
    collective = "orgc-" + "1" * 16
    claimed = _apply(
        None,
        _frame(
            RepresentationAct.CLAIM,
            principal_kind=RepresentationPrincipalKind.ORGANIZATION,
            principal_ref=collective,
        ),
        organization_concepts=SimpleNamespace(
            concepts=(SimpleNamespace(organization_id=collective),)
        ),
    )
    mandate_id = claimed.mandates[0].mandate_id
    accepted = _apply(
        claimed,
        _frame(
            RepresentationAct.ACCEPT,
            mandate_ref=mandate_id,
            principal_kind=RepresentationPrincipalKind.ORGANIZATION,
            principal_ref=collective,
            actor_ref="agent-member",
        ),
        tick=2,
        organization_concepts=SimpleNamespace(
            concepts=(SimpleNamespace(organization_id=collective),)
        ),
    )
    assert accepted.mandates[0].principal_declared is False
    positions = [row for row in accepted.positions if row.active]
    assert len(positions) == 1
    assert positions[0].provenance is RepresentationProvenance.COMMUNICATED


def test_observation_collects_verified_speaker_and_drops_forgery() -> None:
    claim = _frame(RepresentationAct.CLAIM)
    forged = _frame(RepresentationAct.CLAIM, representative_ref="agent-other")
    observation = SimpleNamespace(
        communications=(
            _communication(claim, _REP),
            _communication(forged, _REP),
        )
    )
    ledger = _apply(None, observation=observation)
    assert len(ledger.mandates) == 1
    assert ledger.mandates[0].representative_id == _REP


def test_region_anchors_refresh_and_cap() -> None:
    observation = SimpleNamespace(
        regional_context=SimpleNamespace(region_id="region-a"),
        self_body=SimpleNamespace(
            journey=SimpleNamespace(
                origin_region_id="region-b", destination_region_id="region-c"
            )
        ),
        exits=(SimpleNamespace(destination_region_id="region-d"),),
    )
    ledger = _apply(None, observation=observation)
    assert ledger.region_anchors == (
        "region-a",
        "region-b",
        "region-c",
        "region-d",
    )


def test_settlement_principal_requires_visible_region() -> None:
    observation = SimpleNamespace(
        regional_context=SimpleNamespace(region_id="region-a"),
        self_body=None,
        exits=(),
    )
    resolved = _apply(
        None,
        _frame(
            RepresentationAct.CLAIM,
            principal_kind=RepresentationPrincipalKind.SETTLEMENT,
            principal_ref="region-a",
        ),
        observation=observation,
    )
    assert resolved.mandates[0].principal_resolved is True

    unresolved = _apply(
        None,
        _frame(
            RepresentationAct.CLAIM,
            principal_kind=RepresentationPrincipalKind.SETTLEMENT,
            principal_ref="region-z",
        ),
        observation=observation,
    )
    assert unresolved.mandates[0].principal_resolved is False
    assert "representation_region_unavailable" in unresolved.notices


def test_missing_org_concept_leaves_claim_unresolved() -> None:
    collective = "orgc-" + "2" * 16
    ledger = _apply(
        None,
        _frame(
            RepresentationAct.CLAIM,
            principal_kind=RepresentationPrincipalKind.ORGANIZATION,
            principal_ref=collective,
        ),
        organization_concepts=SimpleNamespace(concepts=()),
    )
    assert ledger.mandates[0].principal_resolved is False
    assert ledger.mandates[0].status is RepresentationStatus.CLAIMED
    assert "representation_unresolved_principal" in ledger.notices


def test_owner_utterance_is_recorded_from_tell() -> None:
    speaker = EntityId(_OWNER)
    frame = _frame(
        RepresentationAct.CLAIM,
        representative_ref=_OWNER,
        actor_ref=_OWNER,
    )
    command = Tell(
        recipient_id=EntityId(_PRINCIPAL),
        utterance=origin_utterance(
            text="hello",
            speaker_id=speaker,
            relations=(representation_frame_relation(frame),),
        ),
    )
    ledger = record_representation_utterance(
        empty_representation_ledger(_OWNER),
        command,
        owner_id=_OWNER,
        tick=1,
    )
    assert len(ledger.mandates) == 1


def test_foreign_owner_and_world_inputs_are_rejected() -> None:
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class WorldState:
        tick: int = 1

    @dataclass(frozen=True)
    class FakeObservation:
        world_state: WorldState

    foreign = replace(empty_representation_ledger(_OWNER), owner_id="agent-other")
    with pytest.raises(RepresentationError, match="representation_invalid_owner"):
        _apply(foreign, _frame(RepresentationAct.CLAIM))

    with pytest.raises(RepresentationError, match="representation_forbidden_input"):
        apply_representation_update(
            owner_id=_OWNER,
            tick=1,
            observation=FakeObservation(world_state=WorldState()),
            prior=None,
            frames=(),
            organization_concepts=None,
            collective_decisions=None,
            offices=None,
            formal_rules=None,
            policy=default_representation_policy(),
        )


def test_update_is_deterministic_for_permuted_frames() -> None:
    first = _frame(RepresentationAct.CLAIM)
    second = _frame(
        RepresentationAct.CLAIM,
        representative_ref="agent-other",
        actor_ref="agent-other",
    )
    forward = _apply(None, first, second)
    backward = _apply(None, second, first)
    assert representation_ledger_digest(forward) == representation_ledger_digest(
        backward
    )
