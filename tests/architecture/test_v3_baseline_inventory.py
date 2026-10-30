"""Frozen V3 completion inventory for the V4 baseline.

V4 reservations must start from a trustworthy V3 surface. Every count, version,
and registry length below is a V3 completion pin: a later V4-01 task may extend
this mapping deliberately, but no task may drift one of these values silently.

`v3_capability_flags` is the only compatibility entry whose `write_version` is a
closed vocabulary key rather than a version identifier, so it is exempt from the
write-in-accepted-restore check by name instead of by heuristic.
"""

from __future__ import annotations

from typing import Final

from analysis.specifications import METRIC_FAMILY_COUNT
from experiments import (
    BENCHMARK_SCENARIO_COUNT,
    V3_BENCHMARK_SCENARIO_COUNT,
    get_benchmark_scenario,
    get_v3_benchmark_scenario,
    registered_benchmark_scenario_ids,
    registered_v3_benchmark_scenario_ids,
)
from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_TYPE_BY_KIND
from simulation.compatibility import (
    ALEMBIC_HEAD_REVISION,
    compatibility_entry,
    list_compatibility_ids,
)
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.runner_models import (
    RESULT_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION_V3,
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
)
from world.events import EVENT_SCHEMA_REPLAY_V21, EVENT_SCHEMA_REPLAY_V22

V3_BASELINE: Final[dict[str, object]] = {
    "default_runner_schema": "runner-config-v4",
    "latest_feature_runner_schema": "runner-config-v55",
    "accepted_scaffolding_runner_schema": "runner-config-v56",
    "default_result_schema": RESULT_SCHEMA_VERSION,
    "generational_result_schema": "runner-result-v3",
    "latest_event_schema": 22,
    "previous_event_schema": 21,
    "latest_codec": "v20",
    "next_codec": "v21",
    "metric_family_count": 144,
    "observer_semantic_type_count": 73,
    "observer_protocol": "observer-protocol-v1",
    "alembic_head": "0017",
    "v2_benchmark_scenarios": 16,
    "v3_benchmark_scenarios": 30,
}

# Closed-vocabulary compatibility entries are not version identifiers.
_CLOSED_VOCABULARY_ENTRIES: Final[frozenset[str]] = frozenset(
    {"v3_capability_flags", "v4_capability_flags"}
)


def test_v3_baseline_runner_and_result_pins() -> None:
    assert RUNNER_SCHEMA_VERSION == V3_BASELINE["default_runner_schema"]
    assert RUNNER_SCHEMA_VERSION_V4 == V3_BASELINE["default_runner_schema"]
    assert RUNNER_SCHEMA_VERSION_V55 == V3_BASELINE["latest_feature_runner_schema"]
    # V4-01 accepts runner-config-v56 for explicit scaffolding identity only:
    # it is never the default and no feature selects it automatically.
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RESULT_SCHEMA_VERSION_V3 == V3_BASELINE["generational_result_schema"]


def test_v3_baseline_event_and_codec_pins() -> None:
    assert EVENT_SCHEMA_REPLAY_V22 == V3_BASELINE["latest_event_schema"]
    assert EVENT_SCHEMA_REPLAY_V21 == V3_BASELINE["previous_event_schema"]
    assert EVENT_SCHEMA_REPLAY_V22 in ACCEPTED_EVENT_SCHEMA_VERSIONS
    assert V3_BASELINE["latest_codec"] in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert V3_BASELINE["next_codec"] not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS


def test_v3_baseline_catalog_and_presentation_pins() -> None:
    assert METRIC_FAMILY_COUNT == V3_BASELINE["metric_family_count"]
    assert len(SEMANTIC_TYPE_BY_KIND) == V3_BASELINE["observer_semantic_type_count"]
    assert OBSERVER_PROTOCOL_VERSION == V3_BASELINE["observer_protocol"]
    assert ALEMBIC_HEAD_REVISION == V3_BASELINE["alembic_head"]


def test_v3_baseline_benchmark_registries() -> None:
    assert BENCHMARK_SCENARIO_COUNT == V3_BASELINE["v2_benchmark_scenarios"]
    assert V3_BENCHMARK_SCENARIO_COUNT == V3_BASELINE["v3_benchmark_scenarios"]

    v2_ids = registered_benchmark_scenario_ids()
    assert len(v2_ids) == BENCHMARK_SCENARIO_COUNT
    assert len(set(v2_ids)) == len(v2_ids)
    for scenario_id in v2_ids:
        assert get_benchmark_scenario(scenario_id).scenario_id == scenario_id

    v3_ids = registered_v3_benchmark_scenario_ids()
    assert len(v3_ids) == V3_BENCHMARK_SCENARIO_COUNT
    assert len(set(v3_ids)) == len(v3_ids)
    for scenario_id in v3_ids:
        assert get_v3_benchmark_scenario(scenario_id).scenario_id == scenario_id


def test_compatibility_matrix_is_self_consistent() -> None:
    entry_ids = list_compatibility_ids()
    assert len(set(entry_ids)) == len(entry_ids)
    assert entry_ids
    for entry_id in entry_ids:
        entry = compatibility_entry(entry_id)
        assert entry.entry_id == entry_id
        assert entry.owner_package.strip() != ""
        assert entry.bump_trigger.strip() != ""
        assert entry.write_version != ""
        if entry_id not in _CLOSED_VOCABULARY_ENTRIES:
            assert entry.write_version in entry.accepted_restore, entry_id
