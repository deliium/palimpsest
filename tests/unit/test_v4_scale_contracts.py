"""Deterministic V4 scale contract: partitioning and declarative budgets."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from simulation.scale import (
    SCALE_CONTRACT_VERSION,
    SCALE_MAX_PARTITIONS,
    SCALE_MAX_POPULATION,
    SCALE_PARTITION_NAMESPACE,
    ScaleBudget,
    partition_balance,
    scale_contract_payload,
    stable_partition,
    validate_scale_budget,
)
from world.identifiers import AgentId

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.unit

_agent_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=20
).map(AgentId)


def _ids(count: int) -> list[AgentId]:
    return [AgentId(f"scale-agent-{index:06d}") for index in range(count)]


def _index_of(partitions: tuple[tuple[AgentId, ...], ...]) -> dict[AgentId, int]:
    return {
        agent_id: index
        for index, partition in enumerate(partitions)
        for agent_id in partition
    }


@settings(max_examples=200, deadline=None)
@given(st.lists(_agent_id_strategy, unique=True, max_size=40), st.integers(1, 17))
def test_partition_is_lossless_and_matches_single_id_calls(
    agent_ids: list[AgentId], partitions: int
) -> None:
    result = stable_partition(agent_ids, partitions=partitions)
    assert len(result) == partitions
    flattened = [agent_id for partition in result for agent_id in partition]
    assert sorted(agent_id.value for agent_id in flattened) == sorted(
        agent_id.value for agent_id in agent_ids
    )
    for partition in result:
        assert len(set(partition)) == len(partition)
    for agent_id in agent_ids:
        (single,) = [
            index
            for index, bucket in enumerate(
                stable_partition([agent_id], partitions=partitions)
            )
            if bucket
        ]
        assert _index_of(result)[agent_id] == single


def test_order_is_preserved_inside_each_partition() -> None:
    agent_ids = _ids(200)
    result = stable_partition(agent_ids, partitions=16)
    for partition in result:
        positions = [agent_ids.index(agent_id) for agent_id in partition]
        assert positions == sorted(positions)


def test_reversing_input_keeps_membership_and_index() -> None:
    agent_ids = _ids(300)
    forward = stable_partition(agent_ids, partitions=8)
    backward = stable_partition(list(reversed(agent_ids)), partitions=8)
    assert _index_of(forward) == _index_of(backward)
    assert sorted(
        agent_id.value for bucket in forward for agent_id in bucket
    ) == sorted(agent_id.value for bucket in backward for agent_id in bucket)


def test_invalid_inputs_fail_closed() -> None:
    agent_ids = _ids(4)
    with pytest.raises(ValueError, match="duplicate_agent_id"):
        stable_partition([agent_ids[0], agent_ids[0]], partitions=4)
    with pytest.raises(ValueError, match="scale_partitions_invalid"):
        stable_partition(agent_ids, partitions=0)
    with pytest.raises(ValueError, match="scale_partitions_invalid"):
        stable_partition(agent_ids, partitions=SCALE_MAX_PARTITIONS + 1)


def test_ten_thousand_ids_balance_under_sixteen_partitions() -> None:
    result = stable_partition(_ids(10_000), partitions=16)
    assert sum(len(partition) for partition in result) == 10_000
    assert partition_balance(result) < 1.25


def test_partition_is_stable_across_processes() -> None:
    script = (
        "from simulation.scale import stable_partition\n"
        "from world.identifiers import AgentId\n"
        "partitions = stable_partition(\n"
        "    [AgentId('scale-agent-000042')], partitions=16\n"
        ")\n"
        "print([index for index, bucket in enumerate(partitions) if bucket][0])\n"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    outputs = {
        subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            check=True,
            env=environment,
            text=True,
        ).stdout.strip()
        for _ in range(2)
    }
    expected = _index_of(
        stable_partition([AgentId("scale-agent-000042")], partitions=16)
    )[AgentId("scale-agent-000042")]
    assert outputs == {str(expected)}


def test_budget_rejects_invalid_limits() -> None:
    assert ScaleBudget(max_population=1, max_commands_per_tick=1, max_observer_rows=1)
    for kwargs in (
        {"max_population": 0},
        {"max_population": -1},
        {"max_population": True},
        {"max_commands_per_tick": 0},
        {"max_observer_rows": 0},
    ):
        base = {
            "max_population": 10,
            "max_commands_per_tick": 10,
            "max_observer_rows": 10,
        }
        with pytest.raises(ValueError):
            ScaleBudget(**{**base, **kwargs})
    with pytest.raises(ValueError, match="scale_budget_population_limit"):
        ScaleBudget(
            max_population=SCALE_MAX_POPULATION + 1,
            max_commands_per_tick=10,
            max_observer_rows=10,
        )


def test_budget_validation_exceeds_population() -> None:
    budget = ScaleBudget(
        max_population=100, max_commands_per_tick=10, max_observer_rows=10
    )
    validate_scale_budget(budget, 100)
    with pytest.raises(ValueError, match="scale_budget_exceeded"):
        validate_scale_budget(budget, 101)


def test_contract_payload_names_the_versioned_namespace() -> None:
    payload = scale_contract_payload()
    assert payload["contract_version"] == SCALE_CONTRACT_VERSION
    assert payload["partition_namespace"] == SCALE_PARTITION_NAMESPACE
    assert payload["max_partitions"] == SCALE_MAX_PARTITIONS


def test_import_opens_no_resources_and_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import importlib

    import simulation.scale

    with caplog.at_level(logging.DEBUG):
        importlib.reload(simulation.scale)
    assert caplog.records == []
