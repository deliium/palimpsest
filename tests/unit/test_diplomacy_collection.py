"""V4-10 contact, envoy, and negotiation collection tests."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agents.cognition import (
    DiplomacyFrame,
    DiplomacyLedger,
    DiplomaticAct,
    DiplomaticContactKind,
    DiplomaticEnvoyStatus,
    DiplomaticNegotiationStatus,
    DiplomaticPartyKind,
    DiplomaticPartyResolution,
    DiplomaticTermKind,
    apply_diplomacy_update,
    diplomacy_ledger_digest,
)

pytestmark = pytest.mark.unit

OWNER = "owner-a"
ORG = "orgc-" + "a" * 16


def _observation(
    *,
    occurrences: tuple[object, ...] = (),
    communications: tuple[object, ...] = (),
    region: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        occurrences=occurrences,
        communications=communications,
        regional_context=(
            None if region is None else SimpleNamespace(region_id=region)
        ),
        self_body=None,
        exits=(),
    )


def _contact_occurrence(
    *, participants: tuple[str, ...] = ("owner-a", "agent-b"), event: str = "evt-1"
) -> SimpleNamespace:
    return SimpleNamespace(
        kind="contact_recorded",
        public_facts={
            "contact_location_id": "region-1",
            "contact_participant_ids": list(participants),
            "contact_present_ids": list(participants),
        },
        provenance=SimpleNamespace(source_event_id=SimpleNamespace(value=event)),
    )


def _communication(frame: DiplomacyFrame, *, speaker: str) -> SimpleNamespace:
    from agents.cognition import diplomacy_frame_relation

    return SimpleNamespace(
        speaker_id=SimpleNamespace(value=speaker),
        utterance=SimpleNamespace(
            content=SimpleNamespace(relations=(diplomacy_frame_relation(frame),)),
            declared=SimpleNamespace(immediate_source_id=speaker),
        ),
    )


def _update(
    *,
    tick: int,
    prior: DiplomacyLedger | None,
    observation: SimpleNamespace,
    frames: tuple[object, ...] = (),
    organization_concepts: object | None = None,
) -> DiplomacyLedger:
    return apply_diplomacy_update(
        owner_id=OWNER,
        tick=tick,
        observation=observation,
        prior=prior,
        frames=frames,
        organization_concepts=organization_concepts,
    )


def test_direct_contact_creates_relation_with_self_party_first() -> None:
    ledger = _update(
        tick=1,
        prior=None,
        observation=_observation(occurrences=(_contact_occurrence(),)),
    )
    assert len(ledger.relations) == 1
    relation = ledger.relations[0]
    assert len(relation.party_ids) == 2
    self_party = next(
        row for row in ledger.parties if row.party_id == relation.party_ids[0]
    )
    assert self_party.anchor_ref == OWNER
    assert self_party.kind is DiplomaticPartyKind.AGENT
    assert ledger.contacts[0].contact_kind is DiplomaticContactKind.DIRECT_CO_PRESENCE
    assert ledger.contacts[0].participant_count == 2
    assert ledger.contacts[0].location_anchor == "region-1"


def test_mediated_contact_uses_a_speaker_verified_frame() -> None:
    frame = DiplomacyFrame(
        act=DiplomaticAct.CONTACT,
        envoy_ref="agent-b",
        actor_ref="agent-b",
        party_kind=DiplomaticPartyKind.AGENT,
        party_ref="agent-b",
    )
    ledger = _update(
        tick=1,
        prior=None,
        observation=_observation(),
        frames=(frame,),
    )
    assert len(ledger.contacts) == 1
    assert ledger.contacts[0].contact_kind is DiplomaticContactKind.MEDIATED_MESSAGE


def test_third_party_report_resolves_no_counterparty() -> None:
    frame = DiplomacyFrame(
        act=DiplomaticAct.CONTACT,
        envoy_ref="agent-c",
        actor_ref="agent-c",
        party_kind=DiplomaticPartyKind.AGENT,
        party_ref="agent-b",
    )
    ledger = _update(tick=1, prior=None, observation=_observation(), frames=(frame,))
    assert ledger.contacts[0].contact_kind is DiplomaticContactKind.THIRD_PARTY_REPORT
    party = next(row for row in ledger.parties if row.anchor_ref == "agent-b")
    assert party.resolution is DiplomaticPartyResolution.RESOLVED


def test_organization_anchor_requires_an_owned_concept() -> None:
    frame = DiplomacyFrame(
        act=DiplomaticAct.CONTACT,
        envoy_ref="envoy-1",
        actor_ref="envoy-1",
        party_kind=DiplomaticPartyKind.ORGANIZATION,
        party_ref=ORG,
    )
    unresolved = _update(
        tick=1, prior=None, observation=_observation(), frames=(frame,)
    )
    party = next(row for row in unresolved.parties if row.anchor_ref == ORG)
    assert party.resolution is DiplomaticPartyResolution.UNRESOLVED
    assert party.kind is DiplomaticPartyKind.ORGANIZATION

    resolved = _update(
        tick=1,
        prior=None,
        observation=_observation(),
        frames=(frame,),
        organization_concepts=SimpleNamespace(
            concepts=(SimpleNamespace(organization_id=ORG),)
        ),
    )
    party = next(row for row in resolved.parties if row.anchor_ref == ORG)
    assert party.resolution is DiplomaticPartyResolution.RESOLVED


def test_settlement_anchor_requires_visible_region_context() -> None:
    frame = DiplomacyFrame(
        act=DiplomaticAct.CONTACT,
        envoy_ref="envoy-1",
        actor_ref="envoy-1",
        party_kind=DiplomaticPartyKind.SETTLEMENT,
        party_ref="region-1",
    )
    unresolved = _update(
        tick=1, prior=None, observation=_observation(), frames=(frame,)
    )
    party = next(row for row in unresolved.parties if row.anchor_ref == "region-1")
    assert party.resolution is DiplomaticPartyResolution.UNRESOLVED

    resolved = _update(
        tick=1,
        prior=None,
        observation=_observation(region="region-1"),
        frames=(frame,),
    )
    party = next(row for row in resolved.parties if row.anchor_ref == "region-1")
    assert party.resolution is DiplomaticPartyResolution.RESOLVED


def test_envoy_accreditation_is_a_claim_without_a_mandate() -> None:
    frame = DiplomacyFrame(
        act=DiplomaticAct.ACCREDIT,
        envoy_ref=OWNER,
        actor_ref=OWNER,
        party_kind=DiplomaticPartyKind.AGENT,
        party_ref="agent-b",
    )
    ledger = _update(tick=1, prior=None, observation=_observation(), frames=(frame,))
    assert len(ledger.envoys) == 1
    assert ledger.envoys[0].status is DiplomaticEnvoyStatus.CLAIMED
    assert ledger.envoys[0].mandate_ref is None


def test_negotiation_opens_and_repeats_by_revision() -> None:
    frame = DiplomacyFrame(
        act=DiplomaticAct.OPEN_NEGOTIATION,
        envoy_ref="agent-b",
        actor_ref="agent-b",
        party_kind=DiplomaticPartyKind.AGENT,
        party_ref="agent-b",
        topic_subject="trade",
        term_kind=DiplomaticTermKind.MATERIAL_EXCHANGE,
        revision=0,
    )
    first = _update(tick=1, prior=None, observation=_observation(), frames=(frame,))
    assert first.negotiations[0].status is DiplomaticNegotiationStatus.OPENED
    second = _update(tick=2, prior=first, observation=_observation(), frames=(frame,))
    assert len(second.negotiations) == 2
    assert second.negotiations[1].revision == 1
    assert second.negotiations[1].last_tick == 2


def test_repeated_observation_is_idempotent() -> None:
    observation = _observation(occurrences=(_contact_occurrence(),))
    first = _update(tick=1, prior=None, observation=observation)
    second = _update(tick=1, prior=first, observation=observation)
    assert diplomacy_ledger_digest(first) == diplomacy_ledger_digest(second)


@given(
    tick=st.integers(min_value=0, max_value=100),
    participants=st.lists(
        st.sampled_from(["agent-b", "agent-c", "agent-d"]),
        min_size=1,
        max_size=3,
        unique=True,
    ),
)
def test_contact_collection_is_deterministic(
    tick: int, participants: list[str]
) -> None:
    observation = _observation(
        occurrences=(_contact_occurrence(participants=(OWNER, *participants)),)
    )
    first = _update(tick=tick, prior=None, observation=observation)
    second = _update(tick=tick, prior=None, observation=observation)
    assert diplomacy_ledger_digest(first) == diplomacy_ledger_digest(second)
    assert len(first.contacts) == 1


def test_update_signature_accepts_only_owner_sidecars() -> None:
    signature = inspect.signature(apply_diplomacy_update)
    names = set(signature.parameters)
    assert names.isdisjoint(
        {
            "peer_ledger",
            "other_owner",
            "world_state",
            "world_engine",
            "engine_token",
            "analysis",
            "macro_society",
        }
    )
    assert {
        "representation",
        "organization_concepts",
        "collective_decisions",
        "structured_commitments",
        "disputes",
        "evidence",
    } <= names


def test_foreign_prior_owner_is_rejected() -> None:
    foreign = DiplomacyLedger(owner_id="owner-z", tick=1)
    with pytest.raises(ValueError):
        _update(tick=1, prior=foreign, observation=_observation())
