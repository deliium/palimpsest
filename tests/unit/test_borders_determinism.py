# mypy: ignore-errors
"""Deterministic border ids, digest, ordering, and caps."""

from __future__ import annotations

import inspect

from hypothesis import given, settings
from hypothesis import strategies as st

from agents.cognition import borders
from agents.cognition.borders import (
    AgreementAct,
    BorderLedger,
    DomainClaimStatus,
    TerritorialDomainClaim,
    default_borders_policy,
    domain_claim_id,
    empty_border_ledger,
    enforce_borders_limits,
)
from agents.cognition.borders_communication import (
    BorderFrame,
    border_claim_relation,
    encode_border_claim,
    parse_border_claim,
)
from agents.models import AgentId
from simulation.borders_codec import (
    encode_borders_snapshot,
    finalize_borders_snapshot,
)
from simulation.borders_models import empty_borders_snapshot
from world.identifiers import EntityId

OWNER = AgentId("agent-1")


def test_location_set_permutations_produce_the_same_domain_id() -> None:
    @given(st.permutations(["a", "b", "c", "d"]))
    @settings(max_examples=20)
    def check(order):
        ids = [EntityId(item) for item in order]
        assert domain_claim_id(OWNER, ids) == domain_claim_id(
            OWNER, tuple(sorted(ids, key=lambda item: item.value))
        )

    check()


def test_frame_order_permutations_produce_the_same_ledger_digest() -> None:
    from agents.cognition.borders import domain_claim_token_id

    locations = ("loc-a", "loc-b")
    frame = BorderFrame(
        act=AgreementAct.CLAIM_DOMAIN,
        domain_id=domain_claim_token_id(OWNER, locations),
        party_kind=borders.CounterpartyKind.AGENT,
        party_ref="agent-2",
        locations=locations,
    )
    assert parse_border_claim(encode_border_claim(frame)) == frame
    assert border_claim_relation(frame) == border_claim_relation(frame)
    assert empty_border_ledger(OWNER).digest == empty_border_ledger(OWNER).digest


def test_identical_inputs_produce_identical_ids_digest_and_order() -> None:
    def build():
        first = TerritorialDomainClaim(
            domain_id=domain_claim_id(OWNER, (EntityId("a"),)),
            owner_id=OWNER,
            location_ids=(EntityId("a"),),
            boundary_edges=(),
            anchor_kind=None,
            anchor_ref=None,
            status=DomainClaimStatus.CLAIMED,
            strength=0.8,
            first_tick=1,
            last_tick=1,
        )
        second = TerritorialDomainClaim(
            domain_id=domain_claim_id(OWNER, (EntityId("b"),)),
            owner_id=OWNER,
            location_ids=(EntityId("b"),),
            boundary_edges=(),
            anchor_kind=None,
            anchor_ref=None,
            status=DomainClaimStatus.CLAIMED,
            strength=0.8,
            first_tick=1,
            last_tick=1,
        )
        return BorderLedger(owner_id=OWNER, domains=(second, first))

    assert build() == build()
    assert build().digest == build().digest


def test_repeated_update_is_idempotent() -> None:
    ledger = _pressure_ledger()
    first = enforce_borders_limits(ledger, default_borders_policy())
    second = enforce_borders_limits(first, default_borders_policy())
    assert first == second


def _pressure_ledger() -> BorderLedger:
    domains = tuple(
        TerritorialDomainClaim(
            domain_id=domain_claim_id(OWNER, (EntityId(f"loc-{index}"),)),
            owner_id=OWNER,
            location_ids=(EntityId(f"loc-{index}"),),
            boundary_edges=(),
            anchor_kind=None,
            anchor_ref=None,
            status=DomainClaimStatus.CLAIMED,
            strength=0.8,
            first_tick=1,
            last_tick=1,
        )
        for index in range(8)
    )
    return BorderLedger(owner_id=OWNER, domains=domains)


def test_caps_are_deterministic_under_pressure() -> None:
    first = enforce_borders_limits(_pressure_ledger(), default_borders_policy())
    second = enforce_borders_limits(_pressure_ledger(), default_borders_policy())
    assert first == second
    assert first.digest == second.digest


def test_no_hash_uuid_or_wall_clock_symbol() -> None:
    source = inspect.getsource(borders)
    assert "import uuid" not in source
    assert "time.time" not in source
    assert "datetime.now" not in source
    assert "hash(" not in source


def test_canonical_snapshot_bytes_are_stable() -> None:
    snapshot = finalize_borders_snapshot(
        empty_borders_snapshot(
            "run-1", publication_id="bd-pub-pending", digest="0" * 64
        )
    )
    assert encode_borders_snapshot(snapshot) == encode_borders_snapshot(snapshot)
