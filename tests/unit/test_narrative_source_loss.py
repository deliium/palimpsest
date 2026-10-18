"""Subjective source-loss states driven only by owner-observed evidence."""

from __future__ import annotations

from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    NarrativeContent,
    NarrativeLedger,
    NarrativeOrigin,
    NarrativeRecordRef,
    NarrativeRecordRole,
    NarrativeSourceLossReason,
    NarrativeSourceLossState,
    NarrativeStatus,
    NarrativeVariant,
    NarrativeWitness,
    NarrativeWitnessKind,
    apply_narrative_update,
    default_generational_narrative_policy,
    narrative_content_fingerprint,
    narrative_variant_id,
)
from agents.models import AgentId
from tests.unit.test_cultural_narratives import _identity, _observation

_OWNER = AgentId("alice")


def _variant(**overrides: object) -> NarrativeVariant:
    content = NarrativeContent(concepts=("founding",), text="tell_story")
    values: dict[str, object] = {
        "variant_id": narrative_variant_id(
            _OWNER, narrative_content_fingerprint(content), 0, ""
        ),
        "owner_id": _OWNER,
        "content": content,
        "content_fingerprint": narrative_content_fingerprint(content),
        "origin": NarrativeOrigin.RECORD_MEDIATED
        if hasattr(NarrativeOrigin, "RECORD_MEDIATED")
        else NarrativeOrigin.RETOLD_STORY,
        "status": NarrativeStatus.ACTIVE,
        "strength": 0.5,
        "first_tick": 1,
        "last_tick": 1,
    }
    values.update(overrides)
    return NarrativeVariant(**values)  # type: ignore[arg-type]


def _record(role: NarrativeRecordRole, integrity: str) -> NarrativeRecordRef:
    return NarrativeRecordRef(
        record_id="record-1",
        role=role,
        observed_revision=1,
        tick=1,
        integrity=integrity,
    )


def _update(previous: NarrativeLedger) -> NarrativeLedger:
    return apply_narrative_update(
        observation=_observation(tick=2),
        identity=_identity(),
        previous=previous,
        policy=default_generational_narrative_policy(),
    )


def _ledger(variant: NarrativeVariant) -> NarrativeLedger:
    return NarrativeLedger(
        owner_id=_OWNER,
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        variants=(variant,),
    )


def test_damaged_record_yields_partial_without_death() -> None:
    ledger = _update(
        _ledger(
            _variant(
                record_refs=(
                    _record(NarrativeRecordRole.DAMAGED, "damaged"),
                ),
            )
        )
    )
    loss = ledger.variants[0].source_loss
    assert loss is not None
    assert loss.state is NarrativeSourceLossState.PARTIAL
    assert loss.reason is NarrativeSourceLossReason.RECORD_DAMAGED
    assert loss.record_backed is False


def test_destroyed_record_without_witnesses_yields_lost() -> None:
    ledger = _update(
        _ledger(
            _variant(
                record_refs=(
                    _record(NarrativeRecordRole.DESTROYED, "destroyed"),
                ),
            )
        )
    )
    loss = ledger.variants[0].source_loss
    assert loss is not None
    assert loss.state is NarrativeSourceLossState.LOST
    assert loss.reason is NarrativeSourceLossReason.RECORD_DESTROYED


def test_intact_record_is_a_preserving_source() -> None:
    ledger = _update(
        _ledger(
            _variant(
                record_refs=(
                    _record(NarrativeRecordRole.READ, "intact"),
                ),
            )
        )
    )
    loss = ledger.variants[0].source_loss
    assert loss is not None
    assert loss.state is NarrativeSourceLossState.INTACT
    assert loss.record_backed is True


def test_known_first_hand_witness_keeps_intact() -> None:
    witness = NarrativeWitness(
        witness_agent_id=_OWNER,
        kind=NarrativeWitnessKind.FIRST_HAND,
        hop_index=0,
        first_seen_tick=1,
        last_seen_tick=1,
    )
    ledger = _update(_ledger(_variant(source_witnesses=(witness,), first_hand=True)))
    loss = ledger.variants[0].source_loss
    assert loss is not None
    assert loss.state is NarrativeSourceLossState.INTACT
    assert loss.known_witness_count == 1
    assert loss.dead_witness_count == 0
