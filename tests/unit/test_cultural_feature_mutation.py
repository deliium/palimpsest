"""Unit tests for cultural feature mutation and recombination."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.cultural_features import (
    CULTURAL_FEATURE_DEFAULT_HOP_CAP,
    SubjectiveCulturalBelief,
    empty_cultural_feature_ledger,
    form_or_reinforce_cultural_belief,
    mutate_cultural_belief,
    recombine_cultural_beliefs,
    upsert_cultural_belief,
)
from agents.models import AgentId

_LOG = logging.getLogger("tests.cultural_feature_mutation")

_CHANNELS = ("observation", "teaching", "communication")


def _seed_two_parents(owner: AgentId):
    ledger = empty_cultural_feature_ledger(owner)
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="practice",
        content_key="p1",
        content_fingerprint="aaaa:bbbb:cccc",
        channel="observation",
        confidence=0.8,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("e1",),
    )
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="practice",
        content_key="p2",
        content_fingerprint="bbbb:dddd:eeee",
        channel="observation",
        confidence=0.8,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("e2",),
    )
    return ledger


def test_mutate_edits_fingerprint_deterministically(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=mutate_deterministic")
    owner = AgentId("mutator")
    ledger = empty_cultural_feature_ledger(owner)
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="term",
        content_key="term-m",
        content_fingerprint="tok0:tok1:tok2",
        channel="observation",
        confidence=0.5,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("e1",),
    )
    belief_id = ledger.beliefs[0].belief_id
    original = ledger.beliefs[0].content_fingerprint
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.cultural_features"):
        once = mutate_cultural_belief(
            ledger,
            belief_id=belief_id,
            tick=2,
            allow_mutation=True,
            mutation_requires_evidence=True,
            owner_evidence_present=True,
            max_token_edits=1,
            rng_namespace="cultural_features",
            seed_material="seed-a",
        )
        twice = mutate_cultural_belief(
            ledger,
            belief_id=belief_id,
            tick=2,
            allow_mutation=True,
            mutation_requires_evidence=True,
            owner_evidence_present=True,
            max_token_edits=1,
            rng_namespace="cultural_features",
            seed_material="seed-a",
        )
    assert once.beliefs[0].content_fingerprint != original
    assert once.beliefs[0].content_fingerprint == twice.beliefs[0].content_fingerprint
    assert once.beliefs[0].mutated is True
    assert once.beliefs[0].parent_belief_ids == ()
    assert "mutated" in caplog.text


def test_mutate_requires_evidence_skip() -> None:
    _LOG.debug("case_id=mutate_requires_evidence")
    owner = AgentId("mutator")
    ledger = empty_cultural_feature_ledger(owner)
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="term",
        content_key="term-m",
        content_fingerprint="tok0:tok1",
        channel="observation",
        confidence=0.5,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("e1",),
    )
    belief_id = ledger.beliefs[0].belief_id
    skipped = mutate_cultural_belief(
        ledger,
        belief_id=belief_id,
        tick=2,
        allow_mutation=True,
        mutation_requires_evidence=True,
        owner_evidence_present=False,
        max_token_edits=1,
        rng_namespace="cultural_features",
    )
    assert skipped.beliefs[0].mutated is False
    assert (
        skipped.beliefs[0].content_fingerprint
        == ledger.beliefs[0].content_fingerprint
    )


def test_recombine_same_kind_overlap(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=recombine_overlap")
    owner = AgentId("combiner")
    ledger = _seed_two_parents(owner)
    parent_ids = tuple(b.belief_id for b in ledger.beliefs)
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.cultural_features"):
        ledger = recombine_cultural_beliefs(
            ledger,
            parent_belief_ids=parent_ids,
            tick=3,
            allow_recombination=True,
            max_parents=2,
            min_token_overlap=0.1,
            enabled_provenance_channels=_CHANNELS,
            channel="observation",
        )
    child = next(b for b in ledger.beliefs if b.recombined)
    assert child.parent_belief_ids == parent_ids
    assert child.hop_index == 1
    assert child.mutated is False
    assert "recombined" in caplog.text


def test_recombine_hop_cap() -> None:
    _LOG.debug("case_id=recombine_hop_cap")
    owner = AgentId("combiner")
    deep_a = SubjectiveCulturalBelief(
        belief_id="a",
        owner_agent_id=owner,
        feature_kind="practice",
        content_key="a",
        content_fingerprint="xxxx:yyyy",
        channel="observation",
        confidence=0.5,
        parent_belief_ids=("ghost",),
        hop_index=CULTURAL_FEATURE_DEFAULT_HOP_CAP,
        mutated=False,
        recombined=False,
        evidence_refs=("ea",),
        acquired_tick=0,
        last_updated_tick=0,
    )
    deep_b = SubjectiveCulturalBelief(
        belief_id="b",
        owner_agent_id=owner,
        feature_kind="practice",
        content_key="b",
        content_fingerprint="yyyy:zzzz",
        channel="observation",
        confidence=0.5,
        parent_belief_ids=("ghost",),
        hop_index=CULTURAL_FEATURE_DEFAULT_HOP_CAP,
        mutated=False,
        recombined=False,
        evidence_refs=("eb",),
        acquired_tick=0,
        last_updated_tick=0,
    )
    ledger = empty_cultural_feature_ledger(owner)
    ledger = upsert_cultural_belief(ledger, deep_a)
    ledger = upsert_cultural_belief(ledger, deep_b)
    with pytest.raises(ValueError, match="cultural_feature_hop_cap"):
        recombine_cultural_beliefs(
            ledger,
            parent_belief_ids=("a", "b"),
            tick=1,
            allow_recombination=True,
            max_parents=2,
            min_token_overlap=0.1,
            enabled_provenance_channels=_CHANNELS,
            channel="observation",
        )


def test_recombine_min_overlap_rejected() -> None:
    _LOG.debug("case_id=recombine_min_overlap")
    owner = AgentId("combiner")
    ledger = empty_cultural_feature_ledger(owner)
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="practice",
        content_key="p1",
        content_fingerprint="aaaa:bbbb",
        channel="observation",
        confidence=0.5,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("e1",),
    )
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="practice",
        content_key="p2",
        content_fingerprint="cccc:dddd",
        channel="observation",
        confidence=0.5,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("e2",),
    )
    parent_ids = tuple(b.belief_id for b in ledger.beliefs)
    with pytest.raises(ValueError, match="min_token_overlap"):
        recombine_cultural_beliefs(
            ledger,
            parent_belief_ids=parent_ids,
            tick=2,
            allow_recombination=True,
            max_parents=2,
            min_token_overlap=0.5,
            enabled_provenance_channels=_CHANNELS,
            channel="observation",
        )
