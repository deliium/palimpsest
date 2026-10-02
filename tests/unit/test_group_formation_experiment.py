"""Analysis clusters and persistence stay outside cognition."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass

import pytest

from analysis.group_formation_metrics import (
    EMERGENT_GROUP_FORMATION_METRIC_VERSION,
    compute_emergent_group_candidates,
    compute_group_persistence,
)
from analysis.models import MetricAvailability, RelationshipEdgeRow
from analysis.specifications import MetricFamilyId, metric_specification
from experiments.catalog import experiment_w_emergent_groups
from experiments.group_formation_scenario import emergent_group_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V16,
    GroupFormationMode,
)
from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS
from world._state import _validate_topology, _validate_weather_coverage
from world.identifiers import EntityId

_LOGGER = "analysis.group_formation_metrics"


@dataclass(frozen=True, slots=True)
class _Action:
    kind: str
    actor_id: str
    other_entity_id: str


@dataclass(frozen=True, slots=True)
class _Belief:
    owner_id: str
    subject: str
    predicate: str
    object: str


@dataclass(frozen=True, slots=True)
class _Place:
    tick: int
    agent_id: str
    location_id: str


@dataclass(frozen=True, slots=True)
class _Trust:
    source_id: str
    target_id: str
    trust: float


def _repeat(kind: str, actor: str, other: str, count: int) -> tuple[_Action, ...]:
    return tuple(_Action(kind, actor, other) for _index in range(count))


def _full_rows() -> dict[str, object]:
    return {
        "interaction_rows": (
            *_repeat("help", "north_a", "north_b", 4),
            _Action("help", "north_b", "north_a"),
            _Action("give", "north_a", "north_b"),
            *_repeat("talk", "north_a", "north_b", 2),
            _Action("attack", "lone", "north_a"),
            _Action("attack", "lone", "north_b"),
        ),
        "belief_rows": (
            _Belief("north_a", "camp", "has", "water"),
            _Belief("north_b", "camp", "has", "water"),
        ),
        "location_rows": (
            _Place(1, "north_a", "north"),
            _Place(1, "north_b", "north"),
            _Place(2, "north_a", "north"),
            _Place(2, "north_b", "north"),
        ),
        "trust_rows": (
            _Trust("north_a", "north_b", 0.6),
            _Trust("north_b", "north_a", 0.6),
        ),
    }


def _candidates(**overrides: object):
    payload = _full_rows()
    payload.update(overrides)
    return compute_emergent_group_candidates(
        payload,
        run_id="run-groups",
        input_revision="rev-groups",
        tick=1,
    )


def test_eight_signals_and_shared_enemies_reading(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    document = _candidates()
    spec = metric_specification(MetricFamilyId.EMERGENT_GROUP_FORMATION)
    assert spec.version_identifier == EMERGENT_GROUP_FORMATION_METRIC_VERSION
    assert document.metric_family == "emergent_group_formation"
    assert document.algorithm_version == "1"
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["signal_count"] == 8
    assert document.values["cluster_count"] == 8
    assert document.values["shared_enemies"] == 1
    for signal in (
        "communication",
        "interaction_frequency",
        "mutual_assistance",
        "resource_exchange",
        "shared_beliefs",
        "shared_harm",
        "spatial_proximity",
        "trust_network",
    ):
        assert document.values[f"{signal}_availability"] == "present"
        assert document.values[f"{signal}_cluster_count"] == 1
    assert "north_a" in str(document.values["agent_clusters"])
    assert any(
        record.getMessage().startswith(
            "emergent_group_candidates signal_count=8 cluster_count=8 agent_count="
        )
        for record in caplog.records
    )
    assert all(
        "shared_enemies" not in record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.INFO
    )


def test_omitted_belief_triples_are_absent() -> None:
    document = _candidates(belief_rows=None)
    assert document.values["shared_beliefs_availability"] == "absent"
    assert document.values["shared_beliefs_cluster_count"] == 0
    assert document.values["interaction_frequency_availability"] == "present"
    assert document.values["shared_enemies"] == 1


def test_overlapping_cliques_stay_separate() -> None:
    rows = {
        "interaction_rows": (
            _Action("give", "north_a", "north_b"),
            _Action("give", "north_b", "lone"),
            _Action("give", "lone", "north_a"),
            _Action("give", "north_b", "south_a"),
        )
    }
    document = compute_emergent_group_candidates(
        rows,
        run_id="run-overlap",
        input_revision="rev-overlap",
    )
    encoded = str(document.values["resource_exchange_clusters"])
    assert encoded.count(";") == 1
    assert "lone,north_a,north_b" in encoded
    assert "north_b,south_a" in encoded


def test_signed_trust_rows_use_the_digraph() -> None:
    rows = {
        "trust_rows": (
            RelationshipEdgeRow(
                source_id="north_a",
                target_id="north_b",
                logical_tick=1,
                activation_state="active",
                trust=0.6,
            ),
            RelationshipEdgeRow(
                source_id="north_b",
                target_id="north_a",
                logical_tick=1,
                activation_state="active",
                trust=0.6,
            ),
        )
    }
    document = compute_emergent_group_candidates(
        rows,
        run_id="run-trust",
        input_revision="rev-trust",
    )
    assert document.values["trust_network_availability"] == "present"
    assert document.values["trust_network_cluster_count"] == 1
    assert document.values["shared_beliefs_availability"] == "absent"


def test_persistence_continuation_split_merge_and_divergence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    pair = {
        "interaction_rows": (_Action("give", "north_a", "north_b"),),
    }
    continued = compute_emergent_group_candidates(
        pair, run_id="run-p", input_revision="rev-p", tick=1
    )
    again = compute_emergent_group_candidates(
        pair, run_id="run-p", input_revision="rev-p", tick=2
    )
    stable = compute_group_persistence(
        (continued, again),
        run_id="run-p",
        input_revision="rev-p",
    )
    assert stable.availability is MetricAvailability.PRESENT
    assert stable.values["continued_links"] == 1
    assert stable.values["persistence_fraction"] == 1.0
    assert stable.values["split_count"] == 0
    assert stable.values["merge_count"] == 0

    triangle = compute_emergent_group_candidates(
        {
            "interaction_rows": (
                _Action("give", "north_a", "north_b"),
                _Action("give", "north_b", "lone"),
                _Action("give", "lone", "north_a"),
            )
        },
        run_id="run-p",
        input_revision="rev-p",
        tick=1,
    )
    opened = compute_emergent_group_candidates(
        {
            "interaction_rows": (
                _Action("give", "north_a", "north_b"),
                _Action("give", "north_a", "lone"),
            )
        },
        run_id="run-p",
        input_revision="rev-p",
        tick=2,
    )
    split = compute_group_persistence(
        (triangle, opened),
        run_id="run-p",
        input_revision="rev-p",
    )
    assert split.values["split_count"] == 1
    assert split.values["merge_count"] == 0
    merged = compute_group_persistence(
        (opened, triangle),
        run_id="run-p",
        input_revision="rev-p",
    )
    assert merged.values["merge_count"] == 1
    assert merged.values["split_count"] == 0

    empty = compute_emergent_group_candidates(
        {},
        run_id="run-p",
        input_revision="rev-p",
        tick=3,
    )
    unstable = compute_group_persistence(
        (continued, empty, empty, empty),
        run_id="run-p",
        input_revision="rev-p",
        window_length=4,
    )
    assert unstable.values["unstable_lineage_count"] == 1

    divergent = compute_group_persistence(
        (continued,),
        (
            (1, "north_a", "those_agents", ("south_a", "south_b"), "active"),
        ),
        run_id="run-p",
        input_revision="rev-p",
    )
    assert divergent.values["cluster_without_concept"] == 1
    assert divergent.values["concept_without_cluster"] == 1
    missing = compute_group_persistence(
        (),
        run_id="run-p",
        input_revision="rev-p",
    )
    assert missing.availability is MetricAvailability.ABSENT
    assert any(
        record.levelno == logging.WARNING
        and record.getMessage() == "group_persistence_empty reason=no_history"
        for record in caplog.records
    )


def test_group_community_value_keys_stay_unchanged() -> None:
    spec = metric_specification(MetricFamilyId.GROUP_COMMUNITY_STRUCTURE)
    assert spec.value_keys == (
        "community_count",
        "modularity",
        "largest_community_share",
        "node_count",
    )


def test_experiment_w_pairs_modes_off_the_v1_gate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    parameters = inspect.signature(emergent_group_scenario).parameters
    assert set(parameters) == {"seed", "max_ticks"}
    definition = experiment_w_emergent_groups()
    by_id = {item.condition_id: item for item in definition.conditions}
    disabled = by_id["w-disabled"].runner_config
    enabled = by_id["w-enabled"].runner_config
    assert disabled.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert enabled.schema_version == RUNNER_SCHEMA_VERSION_V16
    assert disabled.seed == enabled.seed
    assert disabled.stochastic_identity == enabled.stochastic_identity
    assert disabled.scenario is enabled.scenario
    scenario_fields = set(disabled.scenario.__dataclass_fields__)
    assert scenario_fields.isdisjoint(
        {"team", "faction", "culture", "roster", "member"}
    )
    places = {place.entity_id.value: place for place in disabled.scenario.locations}
    assert set(places) == {"north", "south"}
    assert places["north"].adjacent == (EntityId("south"),)
    assert places["south"].adjacent == (EntityId("north"),)
    location_index = {place.entity_id: place for place in disabled.scenario.locations}
    weather_index = {
        item.location_id: item for item in disabled.scenario.weather
    }
    _validate_topology(location_index)
    _validate_weather_coverage(location_index, weather_index)
    starts = {
        body.entity_id.value: body.location_id.value
        for body in disabled.scenario.bodies
    }
    assert starts == {
        "body-north-a": "north",
        "body-north-b": "north",
        "body-south-a": "south",
        "body-south-b": "south",
        "body-lone": "north",
    }
    bindings = {
        agent.agent_id.value: agent.entity_id.value for agent in disabled.agents
    }
    assert bindings == {
        "north_a": "body-north-a",
        "north_b": "body-north-b",
        "south_a": "body-south-a",
        "south_b": "body-south-b",
        "lone": "body-lone",
    }
    assert all(
        agent.cognition.group_formation_mode is GroupFormationMode.DISABLED
        for agent in disabled.agents
    )
    assert all(
        agent.cognition.group_formation_mode is GroupFormationMode.DETERMINISTIC
        for agent in enabled.agents
    )
    assert "experiment-w-emergent-groups" not in {
        item[0] for item in _CATALOG_BUILDERS
    }
    assert any(
        record.getMessage()
        == "experiment_w_built experiment_id=experiment-w-emergent-groups "
        "condition_ids=w-disabled,w-enabled"
        for record in caplog.records
    )
