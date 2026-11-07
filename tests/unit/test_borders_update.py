# mypy: ignore-errors
"""Fixed-order territorial-domain update pipeline."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from agents.cognition.borders import (
    AccessExpectationMode,
    AccessExpectationStatus,
    AgreementAct,
    AgreementProvision,
    AgreementStatus,
    BorderLedger,
    CounterpartyKind,
    DomainClaimStatus,
    apply_borders_update,
    border_ledger_digest,
    default_borders_policy,
    empty_border_ledger,
)
from agents.cognition.borders_communication import (
    BORDER_FRAME_SUBJECT,
    BorderFrame,
    border_claim_relation,
)
from agents.cognition.territorial import ClaimTargetKind
from agents.models import AgentId
from world.communications import origin_utterance
from world.identifiers import EntityId

OWNER = AgentId("agent-1")
PEER = AgentId("agent-2")
OWNER_ENTITY = EntityId("body-1")
PEER_ENTITY = EntityId("body-2")
LOC_A = EntityId("loc-a")
LOC_B = EntityId("loc-b")
LOC_C = EntityId("loc-c")

IDENTITY = SimpleNamespace(
    owner_id=OWNER,
    owner_entity_id=OWNER_ENTITY,
    counterparts=(SimpleNamespace(entity_id=PEER_ENTITY, agent_id=PEER),),
)


def _claims(*locations: EntityId, strength: float = 0.8):
    return SimpleNamespace(
        claims=tuple(
            SimpleNamespace(
                target_kind=ClaimTargetKind.LOCATION,
                target_entity_id=location,
                strength=strength,
            )
            for location in locations
        )
    )


def _frame(
    act: AgreementAct,
    *,
    owner: AgentId = PEER,
    locations: tuple[str, ...] = ("loc-a", "loc-b"),
    party_kind: CounterpartyKind = CounterpartyKind.AGENT,
    party_ref: str | None = "agent-1",
    provision: AgreementProvision | None = None,
    access_mode: AccessExpectationMode | None = None,
) -> BorderFrame:
    from agents.cognition.borders import domain_claim_token_id

    return BorderFrame(
        act=act,
        domain_id=domain_claim_token_id(owner, locations),
        party_kind=party_kind,
        party_ref=party_ref,
        locations=locations,
        expiry_tick=None,
        access_mode=access_mode,
        provision=provision,
    )


def _communication(frame: BorderFrame, speaker: EntityId = PEER_ENTITY):
    return SimpleNamespace(
        speaker_id=speaker,
        listener_id=OWNER_ENTITY,
        utterance=origin_utterance(
            text=BORDER_FRAME_SUBJECT,
            speaker_id=speaker,
            relations=border_claim_relation(frame),
        ),
    )


def _observation(
    *frames: BorderFrame,
    exits: tuple[EntityId, ...] = (LOC_B,),
    regional: str | None = None,
):
    return SimpleNamespace(
        self_body=SimpleNamespace(location_id=LOC_A),
        exits=tuple(SimpleNamespace(destination_id=item) for item in exits),
        communications=tuple(_communication(frame) for frame in frames),
        regional_context=SimpleNamespace(region_id=regional),
    )


def _update(
    prior: BorderLedger,
    observation,
    *,
    claims=None,
    organizations=None,
    diplomacy=None,
    inbox=None,
    tick: int = 3,
):
    return apply_borders_update(
        owner_id=OWNER,
        tick=tick,
        observation=observation,
        territorial_claims=claims,
        prior=prior,
        identity=IDENTITY,
        organization_concepts=organizations,
        diplomacy=diplomacy,
        policy=default_borders_policy(),
        inbox=inbox,
    )


def test_missing_territorial_ledger_yields_empty_domains() -> None:
    ledger = _update(empty_border_ledger(OWNER), _observation())
    assert ledger.domains == ()
    assert ledger.digest == border_ledger_digest(ledger)


def test_own_claims_form_contiguous_and_isolated_domains() -> None:
    ledger = _update(
        empty_border_ledger(OWNER),
        _observation(),
        claims=_claims(LOC_A, LOC_B, LOC_C),
    )
    sets = sorted(
        tuple(item.value for item in domain.location_ids) for domain in ledger.domains
    )
    assert sets == [("loc-a", "loc-b"), ("loc-c",)]
    isolated = next(item for item in ledger.domains if len(item.location_ids) == 1)
    assert isolated.boundary_edges == ()
    assert "boundary_unobserved" in ledger.notices


def test_peer_claim_overlap_creates_dispute_without_reconciliation() -> None:
    ledger = _update(
        empty_border_ledger(OWNER),
        _observation(_frame(AgreementAct.CLAIM_DOMAIN)),
        claims=_claims(LOC_A, LOC_B),
    )
    assert len(ledger.disputes) == 1
    dispute = ledger.disputes[0]
    assert tuple(item.value for item in dispute.contested_location_ids) == (
        "loc-a",
        "loc-b",
    )
    assert dispute.counterparty_ref == PEER_ENTITY.value
    assert ledger.domains[0].status is DomainClaimStatus.DISPUTED


def test_agreement_requires_proposal_then_counterparty_acceptance() -> None:
    first = _update(
        empty_border_ledger(OWNER),
        _observation(
            _frame(
                AgreementAct.PROPOSE,
                provision=AgreementProvision.TERRITORIAL_ACKNOWLEDGEMENT,
            )
        ),
        claims=_claims(LOC_A, LOC_B),
    )
    assert first.agreements[0].status is AgreementStatus.PROPOSED
    second = _update(
        first,
        _observation(
            _frame(
                AgreementAct.ACCEPT,
                provision=AgreementProvision.TERRITORIAL_ACKNOWLEDGEMENT,
            )
        ),
        claims=_claims(LOC_A, LOC_B),
        tick=4,
    )
    assert second.agreements[0].status is AgreementStatus.APPARENT_ACCEPTANCE
    assert second.domains[0].status is DomainClaimStatus.RECOGNIZED


def test_reject_and_withdraw_are_retained() -> None:
    first = _update(
        empty_border_ledger(OWNER),
        _observation(_frame(AgreementAct.PROPOSE)),
        claims=_claims(LOC_A, LOC_B),
    )
    second = _update(
        first,
        _observation(_frame(AgreementAct.REJECT)),
        claims=_claims(LOC_A, LOC_B),
        tick=4,
    )
    assert second.agreements[0].status is AgreementStatus.WITHDRAWN
    assert len(second.agreements) == 1


def test_access_expectation_is_only_created_by_explicit_frame() -> None:
    silent = _update(
        empty_border_ledger(OWNER), _observation(), claims=_claims(LOC_A, LOC_B)
    )
    assert silent.access_expectations == ()
    explicit = _update(
        empty_border_ledger(OWNER),
        _observation(
            _frame(
                AgreementAct.EXPECT_ACCESS,
                access_mode=AccessExpectationMode.RESTRICTED,
            )
        ),
        claims=_claims(LOC_A, LOC_B),
    )
    assert len(explicit.access_expectations) == 1
    assert explicit.access_expectations[0].status is AccessExpectationStatus.EXPECTED
    assert explicit.access_expectations[0].mode is AccessExpectationMode.RESTRICTED


def test_unresolved_organization_and_diplomacy_anchors_are_retained() -> None:
    frame = _frame(
        AgreementAct.EXPECT_ACCESS,
        party_kind=CounterpartyKind.ORGANIZATION,
        party_ref="orgc-0123456789abcdef",
        access_mode=AccessExpectationMode.PERMISSION_EXPECTED,
    )
    ledger = _update(
        empty_border_ledger(OWNER),
        _observation(frame),
        claims=_claims(LOC_A, LOC_B),
        organizations=SimpleNamespace(concepts=()),
        diplomacy=None,
    )
    assert "unresolved_anchor" in ledger.notices
    assert len(ledger.access_expectations) == 1


def test_malformed_frame_is_dropped_with_notice() -> None:
    fake = SimpleNamespace(
        speaker_id=PEER_ENTITY,
        listener_id=OWNER_ENTITY,
        utterance=SimpleNamespace(
            content=SimpleNamespace(
                relations=(
                    SimpleNamespace(
                        subject=BORDER_FRAME_SUBJECT,
                        predicate="relation",
                        object="not-a-valid-frame",
                    ),
                )
            )
        ),
    )
    observation = _observation()
    observation.communications = (fake,)
    ledger = _update(
        empty_border_ledger(OWNER), observation, claims=_claims(LOC_A, LOC_B)
    )
    assert ledger.agreements == ()
    assert "malformed_frame" in ledger.notices
    assert ledger.domains[0].status is DomainClaimStatus.CLAIMED


def test_world_state_and_event_inputs_are_rejected() -> None:
    with pytest.raises(TypeError):
        apply_borders_update(
            owner_id=OWNER,
            tick=1,
            observation=_observation(),
            territorial_claims=None,
            prior=None,
            identity=IDENTITY,
            organization_concepts=None,
            diplomacy=None,
            policy=default_borders_policy(),
            world_state=object(),
        )
    with pytest.raises(TypeError):
        apply_borders_update(
            owner_id=OWNER,
            tick=1,
            observation=_observation(),
            territorial_claims=None,
            prior=None,
            identity=IDENTITY,
            organization_concepts=None,
            diplomacy=None,
            policy=default_borders_policy(),
            world_event=object(),
        )


def test_update_is_deterministic_and_reads_only_owner_inputs() -> None:
    first = _update(
        empty_border_ledger(OWNER),
        _observation(_frame(AgreementAct.CLAIM_DOMAIN)),
        claims=_claims(LOC_A, LOC_B),
    )
    second = _update(
        empty_border_ledger(OWNER),
        _observation(_frame(AgreementAct.CLAIM_DOMAIN)),
        claims=_claims(LOC_A, LOC_B),
    )
    assert first.digest == second.digest
    assert first.digest


def test_update_logs_are_metadata_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.borders"):
        _update(
            empty_border_ledger(OWNER),
            _observation(_frame(AgreementAct.CLAIM_DOMAIN)),
            claims=_claims(LOC_A, LOC_B),
        )
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert OWNER.value not in joined
    assert PEER.value not in joined
    assert "owner_id" not in joined
