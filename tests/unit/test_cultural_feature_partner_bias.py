"""Cultural feature bias float term for aligned communicate futures."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from agents.cognition.cultural_features import (
    cultural_feature_bias_futures,
    empty_cultural_feature_ledger,
    form_or_reinforce_cultural_belief,
)
from agents.models import AgentId
from simulation.runner_models import CulturalFeatureBiasPolicy

_LOG = logging.getLogger("tests.cultural_feature_partner_bias")

_CHANNELS = ("observation", "teaching")


def test_prefer_aligned_adds_float_bias(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=prefer_aligned_float_bias")
    owner = AgentId("bob")
    ledger = form_or_reinforce_cultural_belief(
        empty_cultural_feature_ledger(owner),
        feature_kind="practice",
        content_key="practice-a",
        content_fingerprint="fp000001",
        channel="observation",
        confidence=0.9,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("evt-1",),
    )
    futures = (
        SimpleNamespace(
            future_id="f-comm",
            direction=SimpleNamespace(value="communicate"),
            target_agent_id=AgentId("alice"),
            content_key="practice-a",
        ),
        SimpleNamespace(
            future_id="f-move",
            direction=SimpleNamespace(value="move"),
            target_agent_id=AgentId("alice"),
        ),
    )
    bias = CulturalFeatureBiasPolicy(
        mode="prefer_aligned_features",
        communicate_weight=0.25,
        content_affinity=True,
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.cultural_features"):
        weights = cultural_feature_bias_futures(
            ledger=ledger, bias_policy=bias, futures=futures
        )
    assert "f-comm" in weights
    assert weights["f-comm"] > 0.0
    assert "f-move" not in weights
    assert "aligned_features" in caplog.text or "content_affinity" in caplog.text


def test_ignore_mode_passthrough() -> None:
    _LOG.debug("case_id=ignore_mode_passthrough")
    owner = AgentId("bob")
    ledger = form_or_reinforce_cultural_belief(
        empty_cultural_feature_ledger(owner),
        feature_kind="term",
        content_key="term-a",
        content_fingerprint="tokaaaaa",
        channel="observation",
        confidence=0.9,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("evt-1",),
    )
    futures = (
        SimpleNamespace(
            future_id="f-comm",
            direction=SimpleNamespace(value="communicate"),
            target_agent_id=AgentId("alice"),
        ),
    )
    bias = CulturalFeatureBiasPolicy(mode="ignore", communicate_weight=0.5)
    weights = cultural_feature_bias_futures(
        ledger=ledger, bias_policy=bias, futures=futures
    )
    assert weights == {}
