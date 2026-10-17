"""Symbolic composition contract: ids, caps, enums, and owner scope."""

from __future__ import annotations

import pytest

from agents.cognition.semantic_naming import NamingReferentKind
from agents.cognition.symbolic_language import (
    SYMBOLIC_LANGUAGE_POLICY_VERSION,
    SymbolicComposition,
    SymbolicCompositionKind,
    SymbolicCueSummary,
    SymbolicEvidenceChannel,
    SymbolicEvidenceItem,
    SymbolicLanguagePolicy,
    SymbolicLedger,
    SymbolicReferentHypothesis,
    SymbolicStatus,
    composition_evidence_id,
    composition_id,
    default_symbolic_language_policy,
    empty_symbolic_ledger,
    require_owner_symbolic_language,
    symbolic_strength_band,
)
from agents.models import AgentId


def _composition(
    owner: AgentId, parts: tuple[str, str] = ("alpha", "beta")
) -> SymbolicComposition:
    return SymbolicComposition(
        composition_id=composition_id(owner, SymbolicCompositionKind.RELATIONAL, parts),
        owner_id=owner,
        kind=SymbolicCompositionKind.RELATIONAL,
        parts=parts,
        referent_hypothesis=SymbolicReferentHypothesis(
            NamingReferentKind.LOCATION, 0.4
        ),
    )


def test_owner_scoped_ids_are_deterministic_and_distinct() -> None:
    left = composition_id(
        AgentId("a"), SymbolicCompositionKind.RELATIONAL, ("alpha", "beta")
    )
    right = composition_id(
        AgentId("b"), SymbolicCompositionKind.RELATIONAL, ("alpha", "beta")
    )
    assert left == composition_id(
        AgentId("a"), SymbolicCompositionKind.RELATIONAL, ("alpha", "beta")
    )
    assert left != right
    assert len(left) == 64


def test_rejects_wrong_arity_self_reference_and_bad_tokens() -> None:
    owner = AgentId("a")
    with pytest.raises(ValueError, match="invalid_arity"):
        composition_id(owner, SymbolicCompositionKind.RELATIONAL, ("alpha",))
    with pytest.raises(ValueError, match="self_reference"):
        composition_id(owner, SymbolicCompositionKind.RELATIONAL, ("alpha", "alpha"))
    with pytest.raises(ValueError, match="illegal_token"):
        composition_id(owner, SymbolicCompositionKind.RELATIONAL, ("Alpha", "beta"))


def test_owner_mismatch_rejected_on_ledger_and_guard() -> None:
    owner = AgentId("a")
    foreign = _composition(AgentId("b"))
    with pytest.raises(ValueError, match="owner_mismatch"):
        SymbolicLedger(owner_id=owner, compositions=(foreign,))
    with pytest.raises(TypeError, match="must be SymbolicLedger"):
        require_owner_symbolic_language(foreign, owner, field_name="symbolic_language")


def test_evidence_ids_are_deterministic_and_channel_bound() -> None:
    owner = AgentId("a")
    comp = _composition(owner)
    first = composition_evidence_id(
        comp.composition_id, 0, SymbolicEvidenceChannel.OBSERVED, "tick-1"
    )
    second = composition_evidence_id(
        comp.composition_id, 0, SymbolicEvidenceChannel.COMMUNICATED, "tick-1"
    )
    assert first == composition_evidence_id(
        comp.composition_id, 0, SymbolicEvidenceChannel.OBSERVED, "tick-1"
    )
    assert first != second


def test_policy_is_locked_and_default() -> None:
    policy = default_symbolic_language_policy()
    assert policy.version == SYMBOLIC_LANGUAGE_POLICY_VERSION
    assert policy.max_compositions == 8
    assert policy.max_evidence == 24
    assert policy.max_per_message == 2
    with pytest.raises(ValueError, match="unsupported_policy"):
        SymbolicLanguagePolicy(active_strength=0.99)


def test_strength_bands_are_closed() -> None:
    assert symbolic_strength_band(SymbolicStatus.CANDIDATE, 0.9).value == "candidate"
    assert symbolic_strength_band(SymbolicStatus.ACTIVE, 0.1).value == "low"
    assert symbolic_strength_band(SymbolicStatus.ACTIVE, 0.5).value == "mid"
    assert symbolic_strength_band(SymbolicStatus.ACTIVE, 0.9).value == "high"


def test_cue_summary_rejects_ledger_objects() -> None:
    with pytest.raises(TypeError, match="forbidden_type"):
        SymbolicCueSummary(
            observed_entity_keys=(SymbolicLedger(owner_id=AgentId("a")),)  # type: ignore[arg-type]
        )
    assert SymbolicCueSummary(observed_entity_keys=("loc-1",)).observed_entity_keys == (
        "loc-1",
    )


def test_empty_ledger_and_evidence_caps() -> None:
    owner = AgentId("a")
    assert empty_symbolic_ledger(owner).compositions == ()
    comp = _composition(owner)
    evidence = tuple(
        SymbolicEvidenceItem(
            evidence_id=composition_evidence_id(
                comp.composition_id,
                index,
                SymbolicEvidenceChannel.OBSERVED,
                f"t{index}",
            ),
            ordinal=index,
            channel=SymbolicEvidenceChannel.OBSERVED,
            lineage_ref=f"t{index}",
            tick=index,
        )
        for index in range(25)
    )
    with pytest.raises(ValueError, match="cap_exceeded"):
        SymbolicComposition(
            composition_id=comp.composition_id,
            owner_id=owner,
            kind=comp.kind,
            parts=comp.parts,
            evidence=evidence,
        )
