"""V4-10 diplomacy record, ledger, and instrument invariants."""

from __future__ import annotations

from dataclasses import fields, replace

import pytest

from agents.cognition import (
    DIPLOMACY_CONFLICT_ID_PREFIX,
    DIPLOMACY_CONTACT_ID_PREFIX,
    DIPLOMACY_DECLARATION_ID_PREFIX,
    DIPLOMACY_ENVOY_ID_PREFIX,
    DIPLOMACY_INSTRUMENT_ID_PREFIX,
    DIPLOMACY_MISREPRESENTATION_ID_PREFIX,
    DIPLOMACY_NEGOTIATION_ID_PREFIX,
    DIPLOMACY_POLICY_VERSION,
    DIPLOMACY_TERMINATION_ID_PREFIX,
    LONG_RUNNING_INSTRUMENT_KINDS,
    DiplomacyError,
    DiplomacyLedger,
    DiplomaticConflict,
    DiplomaticConflictKind,
    DiplomaticContact,
    DiplomaticContactKind,
    DiplomaticDeclaration,
    DiplomaticDeclarationAct,
    DiplomaticEnvoy,
    DiplomaticEnvoyStatus,
    DiplomaticInstrument,
    DiplomaticInstrumentKind,
    DiplomaticMisrepresentation,
    DiplomaticMisrepresentationKind,
    DiplomaticNegotiation,
    DiplomaticNegotiationStatus,
    DiplomaticParty,
    DiplomaticPartyKind,
    DiplomaticPartyResolution,
    DiplomaticProvenance,
    DiplomaticRelation,
    DiplomaticStandingSummary,
    DiplomaticTermination,
    DiplomaticTerminationKind,
    DiplomaticTermKind,
    default_diplomacy_policy,
    diplomacy_conflict_id,
    diplomacy_contact_id,
    diplomacy_declaration_id,
    diplomacy_envoy_id,
    diplomacy_instrument_id,
    diplomacy_ledger_digest,
    diplomacy_misrepresentation_id,
    diplomacy_negotiation_id,
    diplomacy_party_id,
    diplomacy_relation_id,
    diplomacy_standing_summary,
    diplomacy_termination_id,
    empty_diplomacy_ledger,
    require_owner_diplomacy,
)

pytestmark = pytest.mark.unit

OWNER = "owner-a"
OTHER = "agent-b"


def _ids() -> tuple[str, str, str]:
    self_id = diplomacy_party_id(OWNER, DiplomaticPartyKind.AGENT, OWNER)
    other_id = diplomacy_party_id(OWNER, DiplomaticPartyKind.AGENT, OTHER)
    relation_id = diplomacy_relation_id(OWNER, (OWNER, OTHER))
    return self_id, other_id, relation_id


def _parties(tick: int = 0) -> tuple[DiplomaticParty, ...]:
    self_id, other_id, _ = _ids()
    rows = (
        DiplomaticParty(
            party_id=self_id,
            kind=DiplomaticPartyKind.AGENT,
            anchor_ref=OWNER,
            resolution=DiplomaticPartyResolution.RESOLVED,
            first_seen_tick=tick,
            provenance=DiplomaticProvenance.SELF_DECLARED,
        ),
        DiplomaticParty(
            party_id=other_id,
            kind=DiplomaticPartyKind.AGENT,
            anchor_ref=OTHER,
            resolution=DiplomaticPartyResolution.RESOLVED,
            first_seen_tick=tick,
            provenance=DiplomaticProvenance.COMMUNICATED,
        ),
    )
    return tuple(sorted(rows, key=lambda row: (row.first_seen_tick, row.party_id)))


def _relation(tick: int = 0) -> DiplomaticRelation:
    self_id, other_id, relation_id = _ids()
    return DiplomaticRelation(
        relation_id=relation_id,
        party_ids=(self_id, other_id),
        opened_tick=tick,
        last_tick=tick,
        provenance=DiplomaticProvenance.SELF_DECLARED,
    )


def _contact(relation_id: str, tick: int = 0) -> DiplomaticContact:
    return DiplomaticContact(
        contact_id=diplomacy_contact_id(
            OWNER,
            relation_id,
            tick,
            DiplomaticContactKind.DIRECT_CO_PRESENCE,
            "region-1",
            "evt-1",
        ),
        relation_id=relation_id,
        tick=tick,
        contact_kind=DiplomaticContactKind.DIRECT_CO_PRESENCE,
        location_anchor="region-1",
        participant_count=2,
        provenance=DiplomaticProvenance.WITNESSED_CONTACT,
        source_ref="evt-1",
    )


def _envoy(relation_id: str, party_id: str, envoy_ref: str = OTHER) -> DiplomaticEnvoy:
    envoy_id = diplomacy_envoy_id(OWNER, relation_id, party_id, envoy_ref, 1, 0)
    return DiplomaticEnvoy(
        envoy_id=envoy_id,
        relation_id=relation_id,
        party_id=party_id,
        envoy_ref=envoy_ref,
        mandate_ref=None,
        status=DiplomaticEnvoyStatus.CLAIMED,
        accredited_tick=1,
        end_tick=None,
        revision=0,
        provenance=DiplomaticProvenance.COMMUNICATED,
    )


def _negotiation(relation_id: str, envoy_ref: str) -> DiplomaticNegotiation:
    negotiation_id = diplomacy_negotiation_id(OWNER, relation_id, "trade", 1, 0)
    return DiplomaticNegotiation(
        negotiation_id=negotiation_id,
        relation_id=relation_id,
        topic_subject="trade",
        status=DiplomaticNegotiationStatus.OPENED,
        opened_tick=1,
        last_tick=1,
        envoy_refs=(envoy_ref,),
        term_kind=DiplomaticTermKind.MATERIAL_EXCHANGE,
        provenance=DiplomaticProvenance.COMMUNICATED,
        revision=0,
    )


def _instrument(
    relation_id: str,
    party_ids: tuple[str, str],
    *,
    kind: DiplomaticInstrumentKind = DiplomaticInstrumentKind.PROPOSAL,
    topic: str = "trade",
    term: DiplomaticTermKind = DiplomaticTermKind.MATERIAL_EXCHANGE,
    tick: int = 1,
    end_tick: int | None = None,
) -> DiplomaticInstrument:
    return DiplomaticInstrument(
        instrument_id=diplomacy_instrument_id(OWNER, relation_id, kind, topic, tick),
        relation_id=relation_id,
        party_ids=party_ids,
        kind=kind,
        term_kind=term,
        topic_subject=topic,
        opener_envoy_ref=None,
        opened_tick=tick,
        end_tick=end_tick,
        anchor_refs=(),
        revision=0,
        provenance=DiplomaticProvenance.SELF_DECLARED,
    )


def _declaration(
    instrument: DiplomaticInstrument,
    party_id: str,
    act: DiplomaticDeclarationAct,
    *,
    tick: int = 1,
    envoy_ref: str | None = None,
    revision: int = 0,
) -> DiplomaticDeclaration:
    return DiplomaticDeclaration(
        declaration_id=diplomacy_declaration_id(
            OWNER, instrument.instrument_id, party_id, act, tick, revision
        ),
        instrument_id=instrument.instrument_id,
        declarer_party_id=party_id,
        envoy_ref=envoy_ref,
        act=act,
        declared_tick=tick,
        provenance=DiplomaticProvenance.SELF_DECLARED,
        independence_ref=None,
        revision=revision,
    )


def _ledger(**overrides: object) -> DiplomacyLedger:
    self_id, other_id, relation_id = _ids()
    relation = _relation()
    envoy = _envoy(relation_id, other_id)
    instrument = _instrument(relation_id, (self_id, other_id))
    values = {
        "owner_id": OWNER,
        "tick": 2,
        "relations": (relation,),
        "parties": _parties(),
        "contacts": (_contact(relation_id),),
        "envoys": (envoy,),
        "negotiations": (_negotiation(relation_id, OTHER),),
        "instruments": (instrument,),
        "declarations": (
            _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE),
        ),
    }
    values.update(overrides)
    return DiplomacyLedger(**values)  # type: ignore[arg-type]


def test_valid_ledger_round_trips_and_summarizes() -> None:
    ledger = _ledger()
    assert ledger.policy_version == DIPLOMACY_POLICY_VERSION
    require_owner_diplomacy(ledger, OWNER)
    require_owner_diplomacy(None, OWNER)
    digest = diplomacy_ledger_digest(ledger)
    assert digest == diplomacy_ledger_digest(_ledger())
    summary = diplomacy_standing_summary(ledger, tick=2)
    assert type(summary) is DiplomaticStandingSummary
    assert summary.relations == 1
    assert summary.parties == 2
    assert summary.resolved_parties == 2
    assert summary.terminations == 0
    assert summary.last_activity_tick == 2
    assert set(name for name, _ in summary.envoy_status_counts) == {"claimed"}
    assert set(name for name, _ in summary.instrument_status_counts) == {"proposed"}
    for field in fields(DiplomaticStandingSummary):
        assert field.name not in {"score", "trust", "rank", "index", "composite"}


def test_require_owner_and_policy_fail_closed() -> None:
    with pytest.raises(TypeError, match="DiplomacyLedger"):
        require_owner_diplomacy(object(), OWNER)
    with pytest.raises(DiplomacyError) as excinfo:
        require_owner_diplomacy(_ledger(), "owner-z")
    assert excinfo.value.code == "diplomacy_owner_mismatch"
    with pytest.raises(DiplomacyError) as excinfo:
        DiplomacyLedger(owner_id=OWNER, policy_version="other")
    assert excinfo.value.code == "diplomacy_policy_mismatch"


def test_every_relation_resolves_and_includes_the_owner_self_party() -> None:
    self_id, other_id, _ = _ids()
    wrong_self = replace(_parties()[0], anchor_ref="someone-else")
    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(
            parties=tuple(sorted((wrong_self, _parties()[1]), key=lambda r: r.party_id))
        )
    assert excinfo.value.code == "diplomacy_self_party_missing"

    relation = replace(_relation(), party_ids=(self_id, "dpp-" + "0" * 16))
    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(relations=(relation,))
    assert excinfo.value.code == "diplomacy_foreign_reference"

    relation = replace(_relation(), party_ids=(other_id, self_id))
    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(relations=(relation,))
    assert excinfo.value.code == "diplomacy_self_party_missing"


def test_ordering_duplicate_and_foreign_reference_fail_closed() -> None:
    relation = _relation()
    first = replace(relation, opened_tick=1, last_tick=1)
    second = replace(
        relation,
        relation_id=diplomacy_relation_id(OWNER, (OWNER, "agent-c")),
        opened_tick=0,
        last_tick=0,
    )
    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(relations=(first, second))
    assert excinfo.value.code == "diplomacy_unordered_rows"

    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(parties=(_parties()[0], _parties()[0]))
    assert excinfo.value.code == "diplomacy_duplicate_id"

    self_id, other_id, _ = _ids()
    bad_envoy = replace(
        _envoy(relation.relation_id, other_id),
        party_id=self_id,
        relation_id=diplomacy_relation_id(OWNER, (OWNER, "agent-z")),
    )
    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(envoys=(bad_envoy,))
    assert excinfo.value.code == "diplomacy_foreign_reference"


def test_instrument_parties_must_match_the_relation() -> None:
    self_id, _, relation_id = _ids()
    instrument = _instrument(relation_id, (self_id,))  # type: ignore[arg-type]
    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(instruments=(instrument,))
    assert excinfo.value.code == "diplomacy_instrument_party_mismatch"


def test_declaration_kind_act_matrix_and_duplicates() -> None:
    self_id, other_id, relation_id = _ids()
    instrument = _instrument(relation_id, (self_id, other_id))
    valid = _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE)
    _ledger(instruments=(instrument,), declarations=(valid,))

    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(
            instruments=(instrument,),
            declarations=(
                _declaration(instrument, self_id, DiplomaticDeclarationAct.PROMISE),
            ),
        )
    assert excinfo.value.code == "diplomacy_declaration_kind_mismatch"

    duplicate = _declaration(
        instrument, self_id, DiplomaticDeclarationAct.PROPOSE, tick=2
    )
    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(
            instruments=(instrument,),
            declarations=tuple(
                sorted((valid, duplicate), key=lambda r: r.declaration_id)
            ),
        )
    assert excinfo.value.code == "diplomacy_duplicate_declaration"


def test_invalid_participant_count_and_termination_targets() -> None:
    relation_id = _relation().relation_id
    with pytest.raises(DiplomacyError) as excinfo:
        replace(_contact(relation_id), participant_count=0)
    assert excinfo.value.code == "diplomacy_invalid_participant_count"

    termination = DiplomaticTermination(
        termination_id=diplomacy_termination_id(
            OWNER, "instrument", "dpi-" + "0" * 16, DiplomaticTerminationKind.EXPIRED, 2
        ),
        target_kind="instrument",
        target_ref="dpi-" + "0" * 16,
        kind=DiplomaticTerminationKind.EXPIRED,
        tick=2,
        provenance=DiplomaticProvenance.COMMUNICATED,
    )
    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(terminations=(termination,))
    assert excinfo.value.code == "diplomacy_unknown_termination_target"

    with pytest.raises(DiplomacyError) as excinfo:
        DiplomaticTermination(
            termination_id=diplomacy_termination_id(
                OWNER,
                "envoy",
                "dpe-" + "0" * 16,
                DiplomaticTerminationKind.PARTY_WITHDREW,
                2,
            ),
            target_kind="envoy",
            target_ref="dpe-" + "0" * 16,
            kind=DiplomaticTerminationKind.PARTY_WITHDREW,
            tick=2,
            provenance=DiplomaticProvenance.COMMUNICATED,
        )
    assert excinfo.value.code == "diplomacy_invalid_termination"


def test_conflict_references_resolve() -> None:
    _, other_id, relation_id = _ids()
    conflict = DiplomaticConflict(
        conflict_id=diplomacy_conflict_id(
            OWNER, relation_id, DiplomaticConflictKind.DUPLICATE_ENVOY, (other_id,)
        ),
        relation_id=relation_id,
        kind=DiplomaticConflictKind.DUPLICATE_ENVOY,
        observed_tick=2,
        instrument_refs=(),
        party_refs=(other_id,),
        provenance=DiplomaticProvenance.COMMUNICATED,
    )
    ledger = _ledger(conflicts=(conflict,))
    assert len(ledger.conflicts) == 1

    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(conflicts=(replace(conflict, party_refs=("dpp-" + "0" * 16,)),))
    assert excinfo.value.code == "diplomacy_foreign_reference"


def test_misrepresentation_and_id_minters_are_deterministic() -> None:
    assert diplomacy_relation_id(OWNER, ("a", "b")) == diplomacy_relation_id(
        OWNER, ("b", "a")
    )
    assert diplomacy_relation_id(OWNER, ("a", "b")) != diplomacy_relation_id(
        "owner-b", ("a", "b")
    )
    assert diplomacy_contact_id(
        OWNER, "dpl-" + "0" * 16, 1, DiplomaticContactKind.MEDIATED_MESSAGE, None, None
    ).startswith(DIPLOMACY_CONTACT_ID_PREFIX)
    assert diplomacy_envoy_id(
        OWNER, "dpl-" + "0" * 16, "dpp-" + "0" * 16, OTHER, 1, 0
    ).startswith(DIPLOMACY_ENVOY_ID_PREFIX)
    assert diplomacy_negotiation_id(OWNER, "dpl-" + "0" * 16, "trade", 1, 0).startswith(
        DIPLOMACY_NEGOTIATION_ID_PREFIX
    )
    assert diplomacy_instrument_id(
        OWNER,
        "dpl-" + "0" * 16,
        DiplomaticInstrumentKind.PROPOSAL,
        "trade",
        1,
    ).startswith(DIPLOMACY_INSTRUMENT_ID_PREFIX)
    assert diplomacy_declaration_id(
        OWNER,
        "dpi-" + "0" * 16,
        "dpp-" + "0" * 16,
        DiplomaticDeclarationAct.ACCEPT,
        1,
        0,
    ).startswith(DIPLOMACY_DECLARATION_ID_PREFIX)
    assert diplomacy_misrepresentation_id(
        OWNER,
        "dpi-" + "0" * 16,
        DiplomaticMisrepresentationKind.SCOPE_EXCEEDED,
        "dpd-" + "0" * 16,
    ).startswith(DIPLOMACY_MISREPRESENTATION_ID_PREFIX)
    assert diplomacy_termination_id(
        OWNER, "instrument", "dpi-" + "0" * 16, DiplomaticTerminationKind.EXPIRED, 2
    ).startswith(DIPLOMACY_TERMINATION_ID_PREFIX)
    assert diplomacy_conflict_id(
        OWNER,
        "dpl-" + "0" * 16,
        DiplomaticConflictKind.AGREEMENT_DISPUTE,
        ("b", "a"),
    ).startswith(DIPLOMACY_CONFLICT_ID_PREFIX)
    assert LONG_RUNNING_INSTRUMENT_KINDS == {
        "agreement",
        "promise",
        "shared_project",
    }


def test_misrepresentation_has_no_truth_or_guilt_fields() -> None:
    row = DiplomaticMisrepresentation(
        misrepresentation_id=diplomacy_misrepresentation_id(
            OWNER,
            "dpi-" + "0" * 16,
            DiplomaticMisrepresentationKind.MANDATE_UNRECOGNIZED,
            "dpd-" + "0" * 16,
        ),
        instrument_id="dpi-" + "0" * 16,
        kind=DiplomaticMisrepresentationKind.MANDATE_UNRECOGNIZED,
        observed_tick=1,
        envoy_ref=OTHER,
        declarer_party_id="dpp-" + "0" * 16,
        provenance=DiplomaticProvenance.COMMUNICATED,
    )
    names = {field.name for field in fields(type(row))}
    assert names.isdisjoint(
        {"truth", "lie", "guilt", "bad_faith", "verified", "legitimate"}
    )


def test_anchorless_unknown_party_is_stable() -> None:
    party_id = diplomacy_party_id(OWNER, DiplomaticPartyKind.UNKNOWN, None)
    assert party_id == diplomacy_party_id(OWNER, DiplomaticPartyKind.UNKNOWN, None)
    party = DiplomaticParty(
        party_id=party_id,
        kind=DiplomaticPartyKind.UNKNOWN,
        anchor_ref=None,
        resolution=DiplomaticPartyResolution.UNRESOLVED,
        first_seen_tick=0,
        provenance=DiplomaticProvenance.COMMUNICATED,
    )
    assert party.party_id == party_id


def test_empty_ledger_and_policy() -> None:
    ledger = empty_diplomacy_ledger(OWNER, tick=4)
    assert ledger.tick == 4
    assert ledger.relations == ()
    assert default_diplomacy_policy().max_total_records == 320
