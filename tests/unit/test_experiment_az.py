"""Experiment AZ is off-gate, deterministic, and yields analytical societies."""

from __future__ import annotations

import pytest

from analysis.society_divergence import SOCIETY_DIMENSIONS, SocietyDigestRow
from analysis.society_emergence import SocietyResidenceRow
from analysis.society_isolation import SocietyEvidenceEdge, SocietyJourneyRow
from experiments.catalog import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_az_multiple_societies,
)
from experiments.composition import (
    society_emission_inputs_from_context,
    society_interaction_edges_from_events,
)
from experiments.coordinator import ExperimentCoordinator
from experiments.multiple_societies_scenario import (
    multiple_societies_arbiter,
    multiple_societies_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V44,
    ArtifactInterpretationMode,
    CulturalNarrativeMode,
    SemanticNamingMode,
    SocialConventionMode,
    SocialNormMode,
)


def _conditions(max_ticks: int = 8):
    definition = multiple_societies_scenario(seed=23, max_ticks=max_ticks)
    return {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }


def test_experiment_az_is_off_gate_and_has_region_separated_arms() -> None:
    definition = multiple_societies_scenario(seed=23, max_ticks=8)
    assert definition.experiment_id == "multiple_societies@1"
    assert definition.experiment_id in OFF_GATE_MATRIX_EXPERIMENT_IDS
    conditions = _conditions()
    assert set(conditions) == {"az-channel-off", "az-isolated", "az-contact"}
    assert conditions["az-channel-off"].schema_version == RUNNER_SCHEMA_VERSION_V4
    assert conditions["az-isolated"].schema_version == RUNNER_SCHEMA_VERSION_V44
    assert conditions["az-isolated"].regions_migration is not None
    assert len(conditions["az-isolated"].regions_migration.regions) == 2
    off = conditions["az-channel-off"]
    enabled = conditions["az-isolated"]
    assert all(
        agent.cognition.semantic_naming_mode is SemanticNamingMode.DISABLED
        for agent in off.agents
    )
    assert all(
        agent.cognition.semantic_naming_mode is SemanticNamingMode.DETERMINISTIC
        and agent.cognition.social_norm_mode is SocialNormMode.DETERMINISTIC
        and agent.cognition.social_convention_mode is SocialConventionMode.DETERMINISTIC
        and agent.cognition.cultural_narrative_mode
        is CulturalNarrativeMode.DETERMINISTIC
        and agent.cognition.artifact_interpretation_mode
        is ArtifactInterpretationMode.DETERMINISTIC
        for agent in enabled.agents
    )
    assert enabled.subjective_valuation is not None
    assert enabled.resource_exchange_profile is not None
    assert enabled.collective_projects is not None
    assert enabled.public_goods is not None
    assert off.subjective_valuation is None
    assert off.resource_exchange_profile is None
    assert off.collective_projects is None
    assert off.public_goods is None
    assert (
        multiple_societies_arbiter("az-channel-off", conditions["az-isolated"]) is None
    )
    assert (
        multiple_societies_arbiter("az-isolated", conditions["az-isolated"]) is not None
    )


def test_experiment_az_catalog_registration_is_stable() -> None:
    base = _conditions()["az-isolated"]
    definition = experiment_az_multiple_societies(base, max_ticks=8)
    assert definition.experiment_id == "multiple_societies@1"
    assert len(definition.conditions) == 3


@pytest.mark.asyncio
async def test_isolated_arm_detects_two_candidate_communities() -> None:
    definition = multiple_societies_scenario(seed=23, max_ticks=3)
    results = await ExperimentCoordinator(definition).run_all()
    arm = next(
        item for item in results if item.assignment.condition_id == "az-isolated"
    )
    events = tuple(arm.committed_events or ())
    residence = (
        SocietyResidenceRow("body-a", "north", 0, 3),
        SocietyResidenceRow("body-b", "north", 0, 3),
        SocietyResidenceRow("body-e", "north", 0, 3),
        SocietyResidenceRow("body-c", "south", 0, 3),
        SocietyResidenceRow("body-d", "south", 0, 3),
    )
    dimension_rows = tuple(
        SocietyDigestRow(
            dimension=dimension,
            person_id=row.person_id,
            token=f"{row.region_id}-{dimension}",
        )
        for dimension in SOCIETY_DIMENSIONS
        for row in residence
    )
    inputs = society_emission_inputs_from_context(
        run_id="az-isolated-run",
        input_revision="rev-az-isolated",
        tick=3,
        living_person_ids=tuple(row.person_id for row in residence),
        residence_rows=residence,
        interaction_edges=society_interaction_edges_from_events(events),
        dimension_rows=dimension_rows,
    )
    assert len(inputs.emission.communities) >= 2
    assert inputs.isolation.unexplained_count == 0
    assert set(inputs.divergence.dimensions_present) == set(SOCIETY_DIMENSIONS)
    assert inputs.divergence.dimensions_absent == ()


@pytest.mark.asyncio
async def test_contact_arm_journey_explains_cross_edge() -> None:
    from world.events import JourneyArrived

    definition = multiple_societies_scenario(seed=23, max_ticks=8)
    results = await ExperimentCoordinator(definition).run_all()
    arm = next(item for item in results if item.assignment.condition_id == "az-contact")
    events = tuple(arm.committed_events or ())
    journeys: list[SocietyJourneyRow] = []
    for event in events:
        details = getattr(event, "details", None)
        if type(details) is not JourneyArrived:
            continue
        for body_id in details.participant_body_ids:
            journeys.append(
                SocietyJourneyRow(
                    person_id=body_id.value,
                    origin_region_id="north",
                    destination_region_id="south",
                    arrival_tick=event.tick,
                )
            )
    residence = (
        SocietyResidenceRow("body-a", "north", 0, 8),
        SocietyResidenceRow("body-b", "north", 0, 8),
        SocietyResidenceRow("body-e", "north", 0, 8),
        SocietyResidenceRow("body-c", "south", 0, 8),
        SocietyResidenceRow("body-d", "south", 0, 8),
    )
    interaction_edges = society_interaction_edges_from_events(events)
    evidence_edges = (
        *(
            SocietyEvidenceEdge(
                edge_id=f"az-edge-{index}",
                kind="communication",
                source_person_id=edge.source_person_id,
                target_person_id=edge.target_person_id,
                tick=edge.tick,
            )
            for index, edge in enumerate(interaction_edges)
        ),
        SocietyEvidenceEdge(
            edge_id="az-cross-evidence",
            kind="testimony",
            source_person_id="body-b",
            target_person_id="body-c",
            tick=7,
        ),
    )
    inputs = society_emission_inputs_from_context(
        run_id="az-contact-run",
        input_revision="rev-az-contact",
        tick=8,
        living_person_ids=tuple(row.person_id for row in residence),
        residence_rows=residence,
        interaction_edges=interaction_edges,
        evidence_edges=evidence_edges,
        journeys=journeys,
    )
    assert journeys
    assert len(inputs.emission.communities) >= 2
    assert inputs.isolation.rows
    assert inputs.isolation.unexplained_count == 0
