"""Cognition compile gates and cultural uptake for knowledge repositories."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from agents.cognition.artifacts import ArtifactInterpretationMode
from agents.cognition.cultural_features import (
    CulturalFeatureKindId,
    collect_cultural_feature_public_cues,
)
from agents.cognition.deliberation import CommandPlanner
from simulation.runner_models import (
    CulturalFeatureUptakeCompose,
    example_cultural_feature_provenance_spec,
)
from tests.unit.test_durable_record_interpretation import (
    _futures,
    _intention,
    _loop_input,
)
from world.actions import EstablishRepository, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation, ObservedRepository

pytestmark = pytest.mark.unit
_LOG = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_disabled_mode_does_not_compile_repository_commands(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="agents.cognition.deliberation")
    injected = EstablishRepository(location_id=EntityId("loc-1"))
    with patch(
        "agents.cognition.deliberation._compile_command",
        return_value=injected,
    ):
        plan = await CommandPlanner().plan(
            _loop_input(),
            _intention(),
            _futures(),
            artifact_interpretation_mode=ArtifactInterpretationMode.DISABLED,
            knowledge_repositories_active=True,
        )
    assert type(plan.command) is Wait
    assert "compile_skip" in caplog.text


@pytest.mark.asyncio
async def test_deterministic_without_repository_channel_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="agents.cognition.deliberation")
    injected = EstablishRepository(location_id=EntityId("loc-1"))
    with patch(
        "agents.cognition.deliberation._compile_command",
        return_value=injected,
    ):
        plan = await CommandPlanner().plan(
            _loop_input(),
            _intention(),
            _futures(),
            artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
            knowledge_repositories_active=False,
        )
    assert type(plan.command) is Wait
    assert "knowledge_repositories_inactive" in caplog.text


@pytest.mark.asyncio
async def test_deterministic_and_repository_allows_establish() -> None:
    injected = EstablishRepository(location_id=EntityId("loc-1"))
    with patch(
        "agents.cognition.deliberation._compile_command",
        return_value=injected,
    ):
        plan = await CommandPlanner().plan(
            _loop_input(),
            _intention(),
            _futures(),
            artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
            knowledge_repositories_active=True,
        )
    assert type(plan.command) is EstablishRepository


def test_observation_repository_cues_never_use_cultural_labels() -> None:
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        repositories=(
            ObservedRepository(
                repository_id=EntityId("repo-1"),
                location_id=EntityId("loc-1"),
                status="intact",
                member_count=1,
                access_mode="open",
            ),
        ),
    )
    cues = collect_cultural_feature_public_cues(observation)
    repo_cues = [
        cue
        for cue in cues
        if "container:" in cue.content_key or "custody-practice:" in cue.content_key
    ]
    assert repo_cues
    joined = " ".join(
        f"{cue.content_key} {cue.content_fingerprint}" for cue in repo_cues
    )
    for forbidden in ("library", "archive", "sacred", "family_records", "trade_ledger"):
        assert forbidden not in joined
    assert any(
        cue.feature_kind is CulturalFeatureKindId.SYMBOLIC_ASSOCIATION
        for cue in repo_cues
    )
    _LOG.debug("repository_cues ok count=%s", len(repo_cues))


def test_uptake_compose_repositories_key_round_trip() -> None:
    from dataclasses import replace

    compose = CulturalFeatureUptakeCompose(repositories=True, artifacts=True)
    assert compose.repositories is True
    provenance = replace(
        example_cultural_feature_provenance_spec(),
        uptake_compose=compose,
    )
    encoded = provenance.canonical_payload()
    assert encoded["uptake_compose"]["repositories"] is True
    assert set(encoded["uptake_compose"]) == {
        "naming",
        "narrative",
        "norms",
        "conventions",
        "teaching",
        "artifacts",
        "mentorship",
        "repositories",
    }
