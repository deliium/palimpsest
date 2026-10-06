"""Unit tests for cultural feature belief formation / provenance hops."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.cultural_features import (
    CULTURAL_FEATURE_DEFAULT_HOP_CAP,
    CULTURAL_FEATURE_FIRST_HOP_INDEX,
    CulturalTransmissionChannelId,
    empty_cultural_feature_ledger,
    form_or_reinforce_cultural_belief,
    upsert_cultural_belief,
)
from agents.models import AgentId

_LOG = logging.getLogger("tests.cultural_feature_provenance")

_CHANNELS = ("observation", "teaching", "communication", "independent_rediscovery")


def test_form_independent_rediscovery_hop_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=independent_rediscovery_hop_zero")
    owner = AgentId("learner")
    ledger = empty_cultural_feature_ledger(owner, max_beliefs=8, max_evidence_refs=4)
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.cultural_features"):
        ledger = form_or_reinforce_cultural_belief(
            ledger,
            feature_kind="practice",
            content_key="practice-a",
            content_fingerprint="fp000001",
            channel=CulturalTransmissionChannelId.INDEPENDENT_REDISCOVERY,
            confidence=0.4,
            tick=1,
            enabled_provenance_channels=_CHANNELS,
        )
    assert len(ledger.beliefs) == 1
    belief = ledger.beliefs[0]
    assert belief.hop_index == CULTURAL_FEATURE_FIRST_HOP_INDEX
    assert belief.parent_belief_ids == ()
    assert "formed" in caplog.text


def test_reinforce_same_content_key() -> None:
    _LOG.debug("case_id=reinforce_same_content_key")
    owner = AgentId("learner")
    ledger = empty_cultural_feature_ledger(owner)
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="term",
        content_key="term-x",
        content_fingerprint="tok:aaaa",
        channel="observation",
        confidence=0.3,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("evt-1",),
    )
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="term",
        content_key="term-x",
        content_fingerprint="tok:bbbb",
        channel="observation",
        confidence=0.9,
        tick=2,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("evt-2",),
    )
    assert len(ledger.beliefs) == 1
    belief = ledger.beliefs[0]
    assert belief.confidence > 0.3
    assert belief.content_fingerprint == "tok:bbbb"
    assert belief.evidence_refs == ("evt-1", "evt-2")
    assert belief.last_updated_tick == 2


def test_child_hop_increments_from_parent() -> None:
    _LOG.debug("case_id=child_hop_increments")
    owner = AgentId("learner")
    ledger = empty_cultural_feature_ledger(owner)
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="practice",
        content_key="root",
        content_fingerprint="rootfp01",
        channel="observation",
        confidence=0.5,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("evt-root",),
    )
    parent_id = ledger.beliefs[0].belief_id
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="practice",
        content_key="child",
        content_fingerprint="childfp1",
        channel="teaching",
        confidence=0.5,
        tick=2,
        enabled_provenance_channels=_CHANNELS,
        parent_belief_ids=(parent_id,),
        evidence_refs=("evt-child",),
    )
    child = next(b for b in ledger.beliefs if b.content_key == "child")
    assert child.hop_index == 1
    assert child.parent_belief_ids == (parent_id,)


def test_channel_not_enabled_rejected() -> None:
    _LOG.debug("case_id=channel_not_enabled")
    owner = AgentId("learner")
    ledger = empty_cultural_feature_ledger(owner)
    with pytest.raises(ValueError, match="channel_not_enabled"):
        form_or_reinforce_cultural_belief(
            ledger,
            feature_kind="term",
            content_key="term-y",
            content_fingerprint="fpterm01",
            channel="artifact",
            confidence=0.4,
            tick=1,
            enabled_provenance_channels=("observation",),
            evidence_refs=("evt-1",),
        )


def test_evidence_ref_cap_and_eviction() -> None:
    _LOG.debug("case_id=evidence_cap_and_eviction")
    owner = AgentId("learner")
    ledger = empty_cultural_feature_ledger(owner, max_beliefs=2, max_evidence_refs=2)
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="term",
        content_key="a",
        content_fingerprint="fpaaaaaa",
        channel="observation",
        confidence=0.4,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("e1", "e2", "e3"),
    )
    assert ledger.beliefs[0].evidence_refs == ("e1", "e2")
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="term",
        content_key="b",
        content_fingerprint="fpbbbbbb",
        channel="observation",
        confidence=0.4,
        tick=2,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("e4",),
    )
    ledger = form_or_reinforce_cultural_belief(
        ledger,
        feature_kind="term",
        content_key="c",
        content_fingerprint="fpcccccc",
        channel="observation",
        confidence=0.4,
        tick=3,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("e5",),
    )
    assert len(ledger.beliefs) == 2
    keys = {b.content_key for b in ledger.beliefs}
    assert "a" not in keys
    assert keys == {"b", "c"}


def test_hop_cap_rejected() -> None:
    _LOG.debug("case_id=hop_cap")
    owner = AgentId("learner")
    ledger = empty_cultural_feature_ledger(owner)
    from agents.cognition.cultural_features import SubjectiveCulturalBelief

    deep = SubjectiveCulturalBelief(
        belief_id="deep-parent",
        owner_agent_id=owner,
        feature_kind="practice",
        content_key="deep",
        content_fingerprint="fpdeep01",
        channel="observation",
        confidence=0.5,
        parent_belief_ids=("ghost",),
        hop_index=CULTURAL_FEATURE_DEFAULT_HOP_CAP,
        mutated=False,
        recombined=False,
        evidence_refs=("e-deep",),
        acquired_tick=0,
        last_updated_tick=0,
    )
    ledger = upsert_cultural_belief(ledger, deep)
    with pytest.raises(ValueError, match="cultural_feature_hop_cap"):
        form_or_reinforce_cultural_belief(
            ledger,
            feature_kind="practice",
            content_key="too-deep",
            content_fingerprint="fptoodeep",
            channel="teaching",
            confidence=0.4,
            tick=1,
            enabled_provenance_channels=_CHANNELS,
            parent_belief_ids=("deep-parent",),
            evidence_refs=("e-child",),
        )
