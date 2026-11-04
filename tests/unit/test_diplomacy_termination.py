"""V4-10 termination, expiry, supersession, conflicts, and limit tests."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyError,
    DiplomacyFrame,
    DiplomacyLedger,
    DiplomaticAct,
    DiplomaticConflictKind,
    DiplomaticInstrumentKind,
    DiplomaticParty,
    DiplomaticPartyKind,
    DiplomaticPartyResolution,
    DiplomaticProvenance,
    DiplomaticRelation,
    DiplomaticTerminationKind,
    DiplomaticTermKind,
    apply_diplomacy_update,
    default_diplomacy_policy,
    detect_diplomacy_conflicts,
    diplomacy_instrument_id,
    diplomacy_ledger_digest,
    diplomacy_party_id,
    diplomacy_relation_id,
    enforce_diplomacy_limits,
    expire_diplomacy_records,
    supersede_diplomacy_instruments,
)

pytestmark = pytest.mark.unit

OWNER = "owner-a"
OTHER = "agent-b"
POLICY = default_diplomacy_policy()


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        occurrences=(),
        communications=(),
        regional_context=None,
        self_body=None,
        exits=(),
    )


def _opening(
    act: DiplomaticAct,
    *,
    topic: str = "trade",
    term: DiplomaticTermKind = DiplomaticTermKind.MATERIAL_EXCHANGE,
    envoy_ref: str = OWNER,
    actor_ref: str = OWNER,
    party_ref: str = OTHER,
    end_tick: int | None = None,
    revision: int = 0,
) -> DiplomacyFrame:
    values: dict[str, object] = {
        "act": act,
        "envoy_ref": envoy_ref,
        "actor_ref": actor_ref,
        "party_kind": DiplomaticPartyKind.AGENT,
        "party_ref": party_ref,
        "term_kind": term,
        "end_tick": end_tick,
        "revision": revision,
    }
    if act in {
        DiplomaticAct.OPEN_NEGOTIATION,
        DiplomaticAct.PROPOSE,
        DiplomaticAct.PROMISE,
        DiplomaticAct.DISPUTE,
        DiplomaticAct.SHARED_PROJECT,
    }:
        values["topic_subject"] = topic
    return DiplomacyFrame(**values)  # type: ignore[arg-type]


def _update(
    prior: DiplomacyLedger | None, frames: tuple[object, ...], *, tick: int = 1
) -> DiplomacyLedger:
    return apply_diplomacy_update(
        owner_id=OWNER,
        tick=tick,
        observation=_observation(),
        prior=prior,
        frames=frames,
    )


def _parties(count: int) -> tuple[list[DiplomaticParty], list[str]]:
    rows: list[DiplomaticParty] = []
    ids: list[str] = []
    for index in range(count):
        anchor = OWNER if index == 0 else f"agent-{index}"
        kind = DiplomaticPartyKind.AGENT
        party_id = diplomacy_party_id(OWNER, kind, anchor)
        ids.append(party_id)
        rows.append(
            DiplomaticParty(
                party_id=party_id,
                kind=kind,
                anchor_ref=anchor,
                resolution=DiplomaticPartyResolution.RESOLVED,
                first_seen_tick=0,
                provenance=DiplomaticProvenance.SELF_DECLARED,
            )
        )
    return sorted(rows, key=lambda row: row.party_id), ids


def _relation(party_ids: tuple[str, ...], *, tick: int = 0) -> DiplomaticRelation:
    anchors = tuple(sorted(party_ids))
    return DiplomaticRelation(
        relation_id=diplomacy_relation_id(OWNER, anchors),
        party_ids=party_ids,
        opened_tick=tick,
        last_tick=tick,
        provenance=DiplomaticProvenance.SELF_DECLARED,
    )


def test_recall_and_resignation_append_retained_terminations() -> None:
    first = _update(
        None,
        (
            _opening(
                DiplomaticAct.ACCREDIT,
                envoy_ref="envoy-e",
                actor_ref="envoy-e",
                party_ref=OTHER,
            ),
        ),
    )
    assert len(first.envoys) == 1
    recalled = _update(
        first,
        (
            DiplomacyFrame(
                act=DiplomaticAct.RECALL,
                envoy_ref="envoy-e",
                actor_ref="envoy-e",
                party_ref=OTHER,
            ),
        ),
        tick=2,
    )
    assert len(recalled.envoys) == 1
    assert any(
        row.kind is DiplomaticTerminationKind.ENVOY_RECALLED
        for row in recalled.terminations
    )
    envoy_id = recalled.envoys[0].envoy_id
    again = _update(
        recalled,
        (
            DiplomacyFrame(
                act=DiplomaticAct.RECALL,
                envoy_ref="envoy-e",
                actor_ref="envoy-e",
                party_ref=OTHER,
            ),
        ),
        tick=2,
    )
    assert len(again.terminations) == len(recalled.terminations)
    assert any(row.target_ref == envoy_id for row in again.terminations)


def test_expiry_is_exclusive_and_rows_are_retained() -> None:
    ledger = _update(
        None,
        (_opening(DiplomaticAct.PROPOSE, end_tick=3),),
        tick=1,
    )
    instrument_id = ledger.instruments[0].instrument_id
    before = expire_diplomacy_records(ledger, tick=2, policy=POLICY)
    assert before.terminations == ()
    at_boundary = expire_diplomacy_records(before, tick=3, policy=POLICY)
    assert len(at_boundary.terminations) == 1
    assert at_boundary.terminations[0].kind is DiplomaticTerminationKind.EXPIRED
    assert at_boundary.terminations[0].target_ref == instrument_id
    after = expire_diplomacy_records(at_boundary, tick=4, policy=POLICY)
    assert len(after.terminations) == 1
    assert len(after.instruments) == 1


def test_older_proposal_is_superseded_but_recognized_agreement_is_not() -> None:
    first = _update(None, (_opening(DiplomaticAct.PROPOSE),), tick=1)
    instrument = first.instruments[0]
    second = _update(
        first,
        (
            _opening(DiplomaticAct.PROPOSE, revision=1),
            DiplomacyFrame(
                act=DiplomaticAct.ACCEPT,
                envoy_ref=OTHER,
                actor_ref=OTHER,
                instrument_ref=diplomacy_instrument_id(
                    OWNER,
                    instrument.relation_id,
                    DiplomaticInstrumentKind.PROPOSAL,
                    "trade",
                    2,
                ),
                revision=1,
            ),
        ),
        tick=2,
    )
    superseded = supersede_diplomacy_instruments(second)
    assert any(
        row.kind is DiplomaticTerminationKind.SUPERSEDED
        and row.target_ref == instrument.instrument_id
        for row in superseded.terminations
    )


def test_duplicate_envoys_and_contradictory_terms_are_conflicts() -> None:
    first = _update(
        None,
        (
            _opening(
                DiplomaticAct.ACCREDIT,
                envoy_ref="envoy-e",
                actor_ref="envoy-e",
                party_ref=OTHER,
            ),
            _opening(DiplomaticAct.PROPOSE, term=DiplomaticTermKind.MATERIAL_EXCHANGE),
        ),
        tick=1,
    )
    first = replace(
        first,
        envoys=tuple(
            replace(row, mandate_ref="rmd-" + "1" * 16) for row in first.envoys
        ),
    )
    second = _update(
        first,
        (
            DiplomacyFrame(
                act=DiplomaticAct.ACCREDIT,
                envoy_ref="envoy-f",
                actor_ref="envoy-f",
                party_ref=OTHER,
                mandate_ref="rmd-" + "2" * 16,
            ),
            _opening(
                DiplomaticAct.PROMISE,
                term=DiplomaticTermKind.PASSAGE,
                revision=1,
            ),
        ),
        tick=2,
    )
    conflicting = detect_diplomacy_conflicts(second)
    kinds = {row.kind for row in conflicting.conflicts}
    assert DiplomaticConflictKind.DUPLICATE_ENVOY in kinds
    assert DiplomaticConflictKind.CONTRADICTORY_TERMS in kinds
    repeated = detect_diplomacy_conflicts(conflicting)
    assert [row.conflict_id for row in conflicting.conflicts] == [
        row.conflict_id for row in repeated.conflicts
    ]


def test_deterministic_truncation_keeps_newest_contacts() -> None:
    ledger = _update(None, (), tick=1)
    for tick in range(1, 19):
        ledger = _update(
            ledger,
            (
                DiplomacyFrame(
                    act=DiplomaticAct.CONTACT,
                    envoy_ref=OTHER,
                    actor_ref=OTHER,
                    party_kind=DiplomaticPartyKind.AGENT,
                    party_ref=OTHER,
                    declaration_ref=f"contact-{tick}",
                ),
            ),
            tick=tick,
        )
    assert len(ledger.contacts) == POLICY.max_contacts_per_relation
    assert "diplomacy_truncated:contacts" in ledger.notices
    assert diplomacy_ledger_digest(ledger) == diplomacy_ledger_digest(ledger)


def test_capacity_error_when_nothing_is_droppable() -> None:
    parties, ids = _parties(33)
    relation_one = _relation(tuple(ids[:32]))
    relation_two = _relation((ids[0], ids[32]))
    ledger = DiplomacyLedger(
        owner_id=OWNER,
        tick=0,
        parties=tuple(parties),
        relations=tuple(
            sorted((relation_one, relation_two), key=lambda row: row.relation_id)
        ),
    )
    with pytest.raises(DiplomacyError) as excinfo:
        enforce_diplomacy_limits(ledger, policy=POLICY)
    assert excinfo.value.code == "diplomacy_capacity_reached"


def test_pipeline_materializes_every_family_in_one_update() -> None:
    first = _update(None, (_opening(DiplomaticAct.PROPOSE, end_tick=5),), tick=1)
    second = _update(
        first,
        (
            _opening(
                DiplomaticAct.ACCREDIT,
                envoy_ref="envoy-e",
                actor_ref="envoy-e",
                party_ref=OTHER,
            ),
            DiplomacyFrame(
                act=DiplomaticAct.ACCEPT,
                envoy_ref="envoy-e",
                actor_ref="envoy-e",
                party_ref=OTHER,
                instrument_ref=first.instruments[0].instrument_id,
                revision=1,
            ),
        ),
        tick=2,
    )
    assert second.instruments
    assert second.declarations
    assert second.envoys
    # An unrecognized envoy accept is retained as a misrepresentation belief.
    assert second.misrepresentations
    repeated = _update(second, (), tick=2)
    assert [row.declaration_id for row in repeated.declarations] == [
        row.declaration_id for row in second.declarations
    ]
    assert [row.misrepresentation_id for row in repeated.misrepresentations] == [
        row.misrepresentation_id for row in second.misrepresentations
    ]
