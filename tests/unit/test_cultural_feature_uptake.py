"""Public-channel cultural feature uptake (observation / communication / compose)."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from agents.cognition.cultural_features import (
    CulturalFeatureKindId,
    CulturalTransmissionChannelId,
    apply_cultural_feature_channel_uptake,
    apply_cultural_feature_compose_adapters,
    apply_cultural_feature_from_teaching,
    collect_cultural_feature_public_cues,
    empty_cultural_feature_ledger,
)
from agents.models import AgentId

_LOG = logging.getLogger("tests.cultural_feature_uptake")


def test_communication_cue_forms_term_belief() -> None:
    owner = AgentId("bob")
    ledger = empty_cultural_feature_ledger(owner)
    observation = SimpleNamespace(
        tick=2,
        communications=(
            SimpleNamespace(
                speaker_id=AgentId("alice"),
                action_kind="tell",
                utterance=SimpleNamespace(
                    declared=SimpleNamespace(
                        claim_id=SimpleNamespace(value="claim-1"),
                        hop_count=1,
                    )
                ),
                event_id="evt-1",
            ),
        ),
        occurrences=(),
        artifacts=(),
    )
    cues = collect_cultural_feature_public_cues(observation)
    assert cues
    updated, audits = apply_cultural_feature_channel_uptake(
        ledger,
        enabled_feature_kinds=("term", "narrative_element", "social_expectation"),
        enabled_provenance_channels=("communication",),
        cues=cues,
        tick=2,
    )
    assert updated.beliefs
    assert updated.beliefs[0].channel is CulturalTransmissionChannelId.COMMUNICATION
    assert audits
    assert all(not hasattr(a, "content_key") for a in audits)


def test_teaching_compose_maps_domain_without_cloning_mentorship(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ledger = empty_cultural_feature_ledger(AgentId("learner"))
    advice = (
        SimpleNamespace(
            source_agent_id=AgentId("alice"),
            domain=SimpleNamespace(value="foraging"),
            band=SimpleNamespace(value="high"),
            occurrence_id="occ-1",
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.cultural_features"):
        updated, audits = apply_cultural_feature_from_teaching(
            ledger,
            enabled_feature_kinds=("practice",),
            enabled_provenance_channels=("teaching",),
            advice_delta=advice,
            tick=3,
            teaching_compose_on=True,
            teaching_mode_on=True,
            mentorship_compose_on=True,
            mentorship_channel_on=True,
        )
    assert updated.beliefs
    assert updated.beliefs[0].feature_kind is CulturalFeatureKindId.PRACTICE
    assert "mentor:alice" in updated.beliefs[0].evidence_refs
    assert audits
    assert "teaching_compose" in caplog.text


def test_compose_adapter_respects_mode_gate(caplog: pytest.LogCaptureFixture) -> None:
    ledger = empty_cultural_feature_ledger(AgentId("bob"))
    compose = SimpleNamespace(
        naming=True,
        narrative=False,
        norms=False,
        conventions=False,
        teaching=False,
        artifacts=False,
        mentorship=False,
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.cultural_features"):
        skipped, _ = apply_cultural_feature_compose_adapters(
            ledger,
            enabled_feature_kinds=("term",),
            enabled_provenance_channels=("communication",),
            tick=1,
            uptake_compose=compose,
            naming_mode_on=False,
            naming_keys=(("alice", "vocab:a", "fp:a"),),
        )
    assert skipped.beliefs == ()
    assert "naming_mode_off" in caplog.text
