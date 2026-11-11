"""Two owners observing one exchange never share a market ledger."""

from __future__ import annotations

import pytest

from agents.cognition.market_institutions import apply_market_institution_update
from tests.unit.market_institutions_helpers import (
    OWNER,
    OWNER_ENTITY,
    PEER,
    PEER_ENTITY,
    observation,
    occurrence,
)

pytestmark = pytest.mark.unit


def test_two_owners_fold_their_own_views_separately() -> None:
    owner_view = observation(
        occurrences=(occurrence(actor=OWNER_ENTITY, other=PEER_ENTITY, source_tick=2),)
    )
    peer_view = observation(
        observer=PEER_ENTITY,
        occurrences=(occurrence(actor=PEER_ENTITY, other=OWNER_ENTITY, source_tick=2),),
    )
    owner_ledger = apply_market_institution_update(
        owner_id=OWNER, tick=3, observation=owner_view, prior=None
    )
    peer_ledger = apply_market_institution_update(
        owner_id=PEER, tick=3, observation=peer_view, prior=None
    )
    assert len(owner_ledger.venues) == 1
    assert len(peer_ledger.venues) == 1
    assert owner_ledger.venues[0].venue_id != peer_ledger.venues[0].venue_id
    assert owner_ledger.venues[0].owner_id == OWNER
    assert peer_ledger.venues[0].owner_id == PEER
    assert owner_ledger.venues[0].observations[0].counterparty_ids == (PEER_ENTITY,)
    assert peer_ledger.venues[0].observations[0].counterparty_ids == (OWNER_ENTITY,)
