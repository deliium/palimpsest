"""Unit tests for cultural feature ledger runtime / checkpoint carry."""

from __future__ import annotations

import logging

from agents.cognition.cultural_features import (
    empty_cultural_feature_ledger,
    form_or_reinforce_cultural_belief,
)
from agents.cognition.models import SubjectiveSnapshot
from agents.models import AgentId
from memory.models import MemoryTrace

_LOG = logging.getLogger("tests.cultural_feature_runtime_carry")

_CHANNELS = ("observation", "teaching", "independent_rediscovery")


def test_subjective_snapshot_carries_cultural_features() -> None:
    _LOG.debug("case_id=subjective_snapshot_cultural_features")
    owner = AgentId("bob")
    ledger = form_or_reinforce_cultural_belief(
        empty_cultural_feature_ledger(owner),
        feature_kind="practice",
        content_key="practice-a",
        content_fingerprint="fp000001",
        channel="observation",
        confidence=0.5,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("evt-1",),
    )
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        cultural_features=ledger,
    )
    assert snapshot.cultural_features is ledger
    assert len(snapshot.cultural_features.beliefs) == 1


def test_empty_cultural_features_blank_slate_compatible() -> None:
    _LOG.debug("case_id=empty_cultural_features_blank_slate")
    owner = AgentId("entrant")
    ledger = empty_cultural_feature_ledger(owner)
    assert isinstance(ledger.beliefs, tuple)
    assert ledger.beliefs == ()
    assert MemoryTrace is not None
