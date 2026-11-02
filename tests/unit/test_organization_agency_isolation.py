"""Owner-only collective-agency inputs and foreign-ledger rejection."""

from __future__ import annotations

import pytest

from agents.cognition import (
    OrganizationAgencyError,
    OrganizationAgencyLedger,
    apply_organization_agency_update,
    organization_agency_claim_relation,
)
from tests.unit.organization_agency_helpers import (
    OTHER,
    OWNER,
    FakeCommunication,
    FakeContent,
    FakeObservation,
    FakeUtterance,
    concept_ledger,
)
from tests.unit.test_organization_agency_update import (
    _observation,
    _propose_claim,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def test_owner_ignores_communications_addressed_to_someone_else() -> None:
    claim = _propose_claim()
    other = FakeCommunication(
        speaker_id=EntityId("body-agent-2"),
        listener_id=EntityId("body-agent-3"),
        utterance=FakeUtterance(
            content=FakeContent(relations=(organization_agency_claim_relation(claim),))
        ),
    )
    ledger = apply_organization_agency_update(
        owner_id=OWNER,
        tick=1,
        observation=FakeObservation(
            observer_id=EntityId("body-agent-1"), communications=(other,)
        ),
        prior=None,
        organization_concepts=concept_ledger(),
    )
    assert ledger.concepts[0].proposals == ()


def test_foreign_prior_ledger_fails_closed() -> None:
    with pytest.raises(OrganizationAgencyError) as excinfo:
        apply_organization_agency_update(
            owner_id=OWNER,
            tick=1,
            observation=_observation(),
            prior=OrganizationAgencyLedger(owner_id=OTHER),
            organization_concepts=concept_ledger(),
        )
    assert excinfo.value.code == "organization_agency_foreign_ledger"


def test_foreign_concept_ledger_fails_closed() -> None:
    with pytest.raises(OrganizationAgencyError):
        apply_organization_agency_update(
            owner_id=OWNER,
            tick=1,
            observation=_observation(),
            prior=None,
            organization_concepts=concept_ledger(owner=OTHER),
        )


def test_event_store_and_command_inputs_are_rejected() -> None:
    from world._state import WorldState

    with pytest.raises(OrganizationAgencyError):
        apply_organization_agency_update(
            owner_id=OWNER,
            tick=1,
            observation=object.__new__(WorldState),
            prior=None,
            organization_concepts=concept_ledger(),
        )


class _StoreFreeObservation:
    def __init__(self) -> None:
        self.observer_id = EntityId("body-agent-1")
        self.occurrences: tuple[object, ...] = ()
        self.communications: tuple[object, ...] = ()

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"unexpected attribute access: {name}")


def test_update_never_reads_an_event_store() -> None:
    observation = _StoreFreeObservation()
    ledger = apply_organization_agency_update(
        owner_id=OWNER,
        tick=1,
        observation=observation,
        prior=None,
        organization_concepts=concept_ledger(),
    )
    assert ledger.owner_id == OWNER
