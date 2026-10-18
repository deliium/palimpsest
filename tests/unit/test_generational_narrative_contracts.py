"""V2 generational narrative provenance contracts."""

from __future__ import annotations

import pytest

from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION,
    CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    CulturalNarrativePolicy,
    GenerationalNarrativePolicy,
    NarrativeContent,
    NarrativeLedger,
    NarrativeOrigin,
    NarrativeRecordRef,
    NarrativeRecordRole,
    NarrativeSourceLoss,
    NarrativeSourceLossReason,
    NarrativeSourceLossState,
    NarrativeStatus,
    NarrativeTheme,
    NarrativeThemeBasis,
    NarrativeTransition,
    NarrativeTransitionKind,
    NarrativeVariant,
    NarrativeWitness,
    NarrativeWitnessKind,
    default_generational_narrative_policy,
    empty_narrative_ledger,
    narrative_content_fingerprint,
    narrative_record_ref_id,
    narrative_transition_id,
    narrative_variant_id,
    narrative_witness_id,
)
from agents.models import AgentId

_OWNER = AgentId("owner")
_WITNESS = AgentId("witness")


def _content() -> NarrativeContent:
    return NarrativeContent(concepts=("founding",), text="tell_story")


def _variant(**overrides: object) -> NarrativeVariant:
    content = _content()
    values: dict[str, object] = {
        "variant_id": narrative_variant_id(
            _OWNER, narrative_content_fingerprint(content), 0, ""
        ),
        "owner_id": _OWNER,
        "content": content,
        "content_fingerprint": narrative_content_fingerprint(content),
        "origin": NarrativeOrigin.OBSERVED_EVENT,
        "status": NarrativeStatus.ACTIVE,
        "strength": 0.5,
        "first_tick": 1,
        "last_tick": 1,
    }
    values.update(overrides)
    return NarrativeVariant(**values)  # type: ignore[arg-type]


def _witness(kind: NarrativeWitnessKind, *, agent: AgentId, death: int | None = None):
    return NarrativeWitness(
        witness_agent_id=agent,
        kind=kind,
        hop_index=0,
        first_seen_tick=1,
        last_seen_tick=1,
        death_observed_tick=death,
    )


def test_generational_policy_locks_caps() -> None:
    policy = default_generational_narrative_policy()
    assert policy.version == CULTURAL_NARRATIVE_POLICY_VERSION_V2
    assert policy.max_witnesses == 8
    assert policy.max_records == 8
    assert policy.max_transitions == 16
    assert policy.max_declared_chain == 8
    with pytest.raises(ValueError):
        GenerationalNarrativePolicy(max_witnesses=9)


def test_v1_and_v2_ledgers_round_trip() -> None:
    content = _content()
    variant = _variant()
    v1 = NarrativeLedger(owner_id=_OWNER, variants=(variant,))
    assert v1.policy_version == CULTURAL_NARRATIVE_POLICY_VERSION
    witness = _witness(NarrativeWitnessKind.FIRST_HAND, agent=_OWNER)
    v2_variant = _variant(
        source_witnesses=(witness,),
        first_hand=True,
        themes=(NarrativeTheme.FOUNDERS,),
        theme_basis=NarrativeThemeBasis.OBSERVED_OCCURRENCE_KIND,
    )
    v2 = NarrativeLedger(
        owner_id=_OWNER,
        variants=(v2_variant,),
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    )
    assert v2.variants[0].first_hand is True
    assert empty_narrative_ledger(
        _OWNER, policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2
    ).policy_version == CULTURAL_NARRATIVE_POLICY_VERSION_V2
    assert content == v2.variants[0].content


def test_v1_rejects_v2_fields() -> None:
    witness = _witness(NarrativeWitnessKind.FIRST_HAND, agent=_OWNER)
    variant = _variant(source_witnesses=(witness,), first_hand=True)
    with pytest.raises(ValueError):
        NarrativeLedger(owner_id=_OWNER, variants=(variant,))


def test_all_witnesses_dead_variant_representable() -> None:
    witness = _witness(NarrativeWitnessKind.FIRST_HAND, agent=_OWNER, death=2)
    variant = _variant(
        source_witnesses=(witness,),
        first_hand=True,
        source_loss=NarrativeSourceLoss(
            state=NarrativeSourceLossState.LOST,
            reason=NarrativeSourceLossReason.ALL_FIRST_HAND_WITNESSES_DEAD,
            tick=2,
            known_witness_count=1,
            dead_witness_count=1,
            record_backed=False,
        ),
    )
    assert variant.source_loss is not None
    assert variant.status is NarrativeStatus.ACTIVE


def test_all_witnesses_dead_with_intact_record() -> None:
    witness = _witness(NarrativeWitnessKind.FIRST_HAND, agent=_OWNER, death=2)
    record = NarrativeRecordRef(
        record_id="record-1",
        role=NarrativeRecordRole.READ,
        observed_revision=1,
        tick=2,
        integrity="intact",
    )
    variant = _variant(
        source_witnesses=(witness,),
        first_hand=True,
        record_refs=(record,),
        source_loss=NarrativeSourceLoss(
            state=NarrativeSourceLossState.INTACT,
            reason=NarrativeSourceLossReason.NONE,
            tick=2,
            known_witness_count=1,
            dead_witness_count=1,
            record_backed=True,
        ),
    )
    assert variant.record_refs[0].record_id == "record-1"


def test_source_loss_counts_must_match_witnesses() -> None:
    witness = _witness(NarrativeWitnessKind.FIRST_HAND, agent=_OWNER, death=2)
    with pytest.raises(ValueError):
        _variant(
            source_witnesses=(witness,),
            first_hand=True,
            source_loss=NarrativeSourceLoss(
                state=NarrativeSourceLossState.LOST,
                reason=NarrativeSourceLossReason.ALL_FIRST_HAND_WITNESSES_DEAD,
                tick=2,
                known_witness_count=2,
                dead_witness_count=1,
                record_backed=False,
            ),
        )


def test_themes_are_ordered_and_unclassified_not_mixed() -> None:
    ordered = _variant(
        themes=(NarrativeTheme.FOUNDERS, NarrativeTheme.MIGRATIONS),
        theme_basis=NarrativeThemeBasis.OBSERVED_OCCURRENCE_KIND,
    )
    assert ordered.themes == (
        NarrativeTheme.FOUNDERS,
        NarrativeTheme.MIGRATIONS,
    )
    with pytest.raises(ValueError):
        _variant(
            themes=(NarrativeTheme.MIGRATIONS, NarrativeTheme.FOUNDERS),
            theme_basis=NarrativeThemeBasis.OBSERVED_OCCURRENCE_KIND,
        )
    with pytest.raises(ValueError):
        _variant(
            themes=(NarrativeTheme.UNCLASSIFIED, NarrativeTheme.FOUNDERS),
            theme_basis=NarrativeThemeBasis.OBSERVED_OCCURRENCE_KIND,
        )


def test_transition_ids_are_unique_and_stable() -> None:
    variant = _variant()
    transition_id = narrative_transition_id(
        _OWNER, variant.variant_id, NarrativeTransitionKind.MINTED, 1, "origin"
    )
    transition = NarrativeTransition(
        transition_id=transition_id,
        kind=NarrativeTransitionKind.MINTED,
        tick=1,
        carrier_agent_id=_OWNER,
    )
    assert transition.transition_id == narrative_transition_id(
        _OWNER, variant.variant_id, NarrativeTransitionKind.MINTED, 1, "origin"
    )
    with pytest.raises(ValueError):
        _variant(transitions=(transition, transition))
    with pytest.raises(ValueError):
        _variant(
            transitions=(
                NarrativeTransition(
                    transition_id=transition_id,
                    kind=NarrativeTransitionKind.MINTED,
                    tick=1,
                    parent_variant_ids=(variant.variant_id,),
                ),
            )
        )


def test_record_and_witness_helpers_are_deterministic() -> None:
    variant_id = _variant().variant_id
    assert narrative_witness_id(
        _OWNER, variant_id, _OWNER, NarrativeWitnessKind.FIRST_HAND, 0
    ) == narrative_witness_id(
        _OWNER, variant_id, _OWNER, NarrativeWitnessKind.FIRST_HAND, 0
    )
    assert narrative_record_ref_id(
        variant_id, "record-1", 1, NarrativeRecordRole.READ
    ) == narrative_record_ref_id(
        variant_id, "record-1", 1, NarrativeRecordRole.READ
    )


def test_no_truth_fields_exist() -> None:
    forbidden = {
        "true",
        "false",
        "correct",
        "verified",
        "accuracy",
        "objective_truth",
    }
    names = set(NarrativeVariant.__dataclass_fields__)
    names |= set(NarrativeLedger.__dataclass_fields__)
    assert not (names & forbidden)


def test_caller_mutation_cannot_alter_frozen_values() -> None:
    themes = [NarrativeTheme.FOUNDERS]
    variant = _variant(
        themes=themes,  # type: ignore[arg-type]
        theme_basis=NarrativeThemeBasis.OBSERVED_OCCURRENCE_KIND,
    )
    themes.append(NarrativeTheme.MIGRATIONS)
    assert variant.themes == (NarrativeTheme.FOUNDERS,)
    with pytest.raises(AttributeError):
        variant.strength = 0.9  # type: ignore[misc]


def test_cultural_policy_still_v1_only() -> None:
    assert CulturalNarrativePolicy().version == CULTURAL_NARRATIVE_POLICY_VERSION
    with pytest.raises(ValueError):
        CulturalNarrativePolicy(version=CULTURAL_NARRATIVE_POLICY_VERSION_V2)
