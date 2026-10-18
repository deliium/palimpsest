"""The cognitive loop uses the V2 policy only when the run spec is present."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.configuration import (
    CognitionCulturalNarrativeMode,
    CognitionLoopConfig,
    build_cognitive_loop,
)
from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    default_generational_narrative_policy,
)
from agents.cognition.loop import _build_narrative_cue_summary


def test_v2_policy_is_reported_in_condition_fingerprint() -> None:
    config = CognitionLoopConfig(
        cultural_narrative_mode=CognitionCulturalNarrativeMode.DETERMINISTIC,
        cultural_narrative_policy=default_generational_narrative_policy(),
        generational_narrative_spec_digest="a" * 64,
    )
    material = config.condition_fingerprint_material()
    assert material["generational_narrative_spec_digest"] == "a" * 64


def test_loop_accepts_the_generational_spec_without_new_mode() -> None:
    spec = SimpleNamespace(generational_narratives_mode="deterministic")
    loop = build_cognitive_loop(
        generational_narratives_spec=spec,
        durable_records_active=True,
    )
    assert loop._generational_narratives_spec is spec
    assert loop._durable_records_active is True
    assert loop._cultural_narrative_policy is None


def test_loop_carries_v2_policy_when_configured() -> None:
    policy = default_generational_narrative_policy()
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            cultural_narrative_mode=(
                CognitionCulturalNarrativeMode.DETERMINISTIC
            ),
            cultural_narrative_policy=policy,
        )
    )
    assert loop._cultural_narrative_policy is policy
    assert loop._cultural_narrative_policy.version == (
        CULTURAL_NARRATIVE_POLICY_VERSION_V2
    )


def test_record_cues_are_absent_when_durable_records_are_off() -> None:
    interpretations = SimpleNamespace(
        interpretations=(
            SimpleNamespace(
                artifact_id=SimpleNamespace(value="record-1"),
                observed_revision=1,
                source_tick=1,
                distorted=False,
                reading_marks=(),
                reading_relations=(),
            ),
        )
    )
    off = _build_narrative_cue_summary(
        artifact_interpretations=interpretations,
        retrieve_context=None,
        durable_records_active=False,
    )
    on = _build_narrative_cue_summary(
        artifact_interpretations=interpretations,
        retrieve_context=None,
        durable_records_active=True,
    )
    assert off.records == ()
    assert len(on.records) == 1
    assert on.records[0].record_id == "record-1"
