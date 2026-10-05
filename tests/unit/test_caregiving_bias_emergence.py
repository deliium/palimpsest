"""Caregiving cognition bias emerges without parent hardcoding."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.cognition.caregiving import (
    CAREGIVING_BIAS_POLICY_VERSION,
    caregiving_future_biases,
    caregiving_mode_active,
)
from agents.cognition.models import (
    ActionDirection,
    ImaginedFuture,
    SituationClaimCode,
)
from agents.models import AgentId, DriveKind
from social.models import RelationshipId
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipConfidence,
    RelationshipDimension,
    RelationshipDimensionState,
    RelationshipPolicyRef,
    RelationshipRevisionId,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservedDependencyNeed,
    ObservedDependencyNeeds,
    ObservedSelf,
    VisibleBody,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.unit

_LOG = logging.getLogger("tests.caregiving_bias_emergence")
_OWNER = AgentId("caregiver")
_TARGET = AgentId("ward")


def _future(
    future_id: str,
    direction: ActionDirection,
    *,
    target_entity: str | None = "body-ward",
    target_agent: AgentId | None = _TARGET,
) -> ImaginedFuture:
    return ImaginedFuture(
        future_id=future_id,
        claim_codes=(SituationClaimCode.SOCIAL_SIGNAL,),
        confidence=0.5,
        direction=direction,
        target_entity_id=target_entity,
        target_agent_id=target_agent,
        horizon_ticks=1,
    )


def _profile(
    *, affection: float, dependency: float = 0.0
) -> DirectedRelationshipProfile:
    policy = RelationshipPolicyRef(policy_id="rel-v1", version="1")
    confidence = RelationshipConfidence(
        confidence=1.0, support_mass=1.0, contradiction_mass=0.0
    )
    dims = [
        RelationshipDimensionState(
            dimension=RelationshipDimension.AFFECTION,
            value=affection,
            confidence=confidence,
            evidence=(),
            logical_tick=1,
            policy=policy,
        )
    ]
    if dependency != 0.0:
        dims.append(
            RelationshipDimensionState(
                dimension=RelationshipDimension.DEPENDENCY,
                value=dependency,
                confidence=confidence,
                evidence=(),
                logical_tick=1,
                policy=policy,
            )
        )
    return DirectedRelationshipProfile(
        relationship_id=RelationshipId("rel-care"),
        source_id=_OWNER,
        target_id=_TARGET,
        dimensions=tuple(dims),
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId("rrev-care"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=policy,
    )


def _observation(*, with_needs: bool = False) -> Observation:
    needs = None
    if with_needs:
        needs = ObservedDependencyNeeds(
            needs=(
                ObservedDependencyNeed(need_id="safety", deficit=0.8, critical=True),
            )
        )
    self_body = ObservedSelf(
        entity_id=EntityId("body-care"),
        location_id=EntityId("loc-1"),
        life_status=LifeStatus.ALIVE,
        hunger=Hunger(10.0),
        thirst=Thirst(10.0),
        fatigue=Fatigue(10.0),
        health=Health(90.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        carry_capacity=CarryCapacity(10),
    )
    other = VisibleBody(
        entity_id=EntityId("body-ward"),
        life_status=LifeStatus.ALIVE,
        coarse_health=CoarseHealth.STABLE,
        dependency_needs=needs,
    )
    return Observation(
        observer_id=EntityId("body-care"),
        world_id=WorldId("world-1"),
        revision=WorldRevision(1),
        tick=1,
        self_body=self_body,
        visible_bodies=(other,),
    )


def test_disabled_mode_is_passthrough() -> None:
    assert caregiving_mode_active("disabled") is False
    assert caregiving_mode_active(None) is False
    biases = caregiving_future_biases(
        owner_id=_OWNER,
        mode="disabled",
        futures=(_future("help-0", ActionDirection.HELP),),
        relationships=(_profile(affection=1.0),),
        observation=_observation(with_needs=True),
        active_drive_kinds=(DriveKind.BELONGING,),
    )
    assert biases == {}


def test_non_kin_high_affection_boosts_help(caplog: pytest.LogCaptureFixture) -> None:
    """Affection alone (no objective kinship import) can elevate care."""
    with caplog.at_level(logging.DEBUG):
        biases = caregiving_future_biases(
            owner_id=_OWNER,
            mode="deterministic",
            futures=(
                _future("help-0", ActionDirection.HELP),
                _future(
                    "wait",
                    ActionDirection.WAIT,
                    target_entity=None,
                    target_agent=None,
                ),
            ),
            relationships=(_profile(affection=0.9),),
            observation=_observation(with_needs=True),
            active_drive_kinds=(DriveKind.BELONGING, DriveKind.SAFETY),
        )
    assert biases["help-0"] > 0.0
    assert "wait" not in biases
    assert "caregiving_candidate_score" in caplog.text
    assert CAREGIVING_BIAS_POLICY_VERSION.startswith("caregiving-bias")
    _LOG.debug("non_kin_bias=%s", biases["help-0"])


def test_objective_parent_edge_alone_does_not_force_care() -> None:
    """Bias module never consults world.kinship; zero relationships => neglect."""
    biases = caregiving_future_biases(
        owner_id=_OWNER,
        mode="deterministic",
        futures=(_future("help-0", ActionDirection.HELP),),
        relationships=(),
        observation=_observation(with_needs=False),
        active_drive_kinds=(),
    )
    assert biases == {}


def test_shared_caregiving_no_exclusive_lock() -> None:
    """Two caregivers may both receive positive bias toward the same ward."""
    other_owner = AgentId("caregiver-b")
    futures = (_future("help-0", ActionDirection.HELP),)
    profile_a = _profile(affection=0.8)
    profile_b = DirectedRelationshipProfile(
        relationship_id=RelationshipId("rel-care-b"),
        source_id=other_owner,
        target_id=_TARGET,
        dimensions=profile_a.dimensions,
        activation_state=profile_a.activation_state,
        current_revision_id=RelationshipRevisionId("rrev-care-b"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=profile_a.policy,
    )
    obs = _observation(with_needs=True)
    bias_a = caregiving_future_biases(
        owner_id=_OWNER,
        mode="deterministic",
        futures=futures,
        relationships=(profile_a,),
        observation=obs,
        active_drive_kinds=(DriveKind.BELONGING,),
    )
    bias_b = caregiving_future_biases(
        owner_id=other_owner,
        mode="deterministic",
        futures=futures,
        relationships=(profile_b,),
        observation=obs,
        active_drive_kinds=(DriveKind.BELONGING,),
    )
    assert bias_a["help-0"] > 0.0
    assert bias_b["help-0"] > 0.0


def test_module_does_not_import_world_kinship() -> None:
    import agents.cognition.caregiving as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from world.kinship" not in source
    assert "import world.kinship" not in source
    assert "from world import kinship" not in source
    # Runtime import table must not bind kinship either.
    assert "kinship" not in mod.__dict__
