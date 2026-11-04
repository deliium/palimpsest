"""V4-10 diplomacy harvest from exported owner ledgers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyFrame,
    DiplomaticAct,
    DiplomaticPartyKind,
    DiplomaticTermKind,
    apply_diplomacy_update,
)
from analysis.delegation_representation_contract import representation_owner_token
from analysis.diplomacy_contract import diplomacy_agent_token
from analysis.diplomacy_rows import harvest_diplomacy_rows

pytestmark = pytest.mark.unit

OWNER = "agent-a"
OTHER = "agent-b"
ORG = "orgc-" + "a" * 16
REGION = "region-1"


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        occurrences=(),
        communications=(),
        regional_context=SimpleNamespace(region_id=REGION),
        self_body=None,
        exits=(),
    )


def _ledger():
    frame = DiplomacyFrame(
        act=DiplomaticAct.PROPOSE,
        envoy_ref=OWNER,
        actor_ref=OWNER,
        party_kind=DiplomaticPartyKind.AGENT,
        party_ref=OTHER,
        topic_subject="trade",
        term_kind=DiplomaticTermKind.MATERIAL_EXCHANGE,
        revision=0,
    )
    return apply_diplomacy_update(
        owner_id=OWNER,
        tick=1,
        observation=_observation(),
        prior=None,
        frames=(frame,),
        anchor_refs=(ORG,),
    )


def test_harvest_contains_tokens_and_no_raw_agent_ids() -> None:
    ledger = _ledger()
    rows = harvest_diplomacy_rows((ledger,))
    assert rows.relations
    assert rows.instruments
    assert rows.parties
    rendered = repr(rows)
    assert OWNER not in rendered
    assert OTHER not in rendered
    assert "trade" not in rendered
    for party in rows.parties:
        if party.party_token is not None:
            assert len(party.party_token) == 16 or party.party_token.startswith("orgc-")
    assert diplomacy_agent_token(OWNER) == representation_owner_token(OWNER)


def test_harvest_preserves_owner_safe_anchors() -> None:
    ledger = _ledger()
    rows = harvest_diplomacy_rows((ledger,))
    anchors = {anchor for row in rows.instruments for anchor in row.anchor_refs}
    assert ORG in anchors


def test_harvest_of_empty_ledger_is_empty_but_typed() -> None:
    from agents.cognition import empty_diplomacy_ledger

    rows = harvest_diplomacy_rows((empty_diplomacy_ledger(OWNER, tick=0),))
    assert not rows.has_any_rows()
    assert rows.relations == ()
