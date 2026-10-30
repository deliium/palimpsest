"""Opt-in V4 scale-contract measurement lane.

This lane measures partition mapping only. It is not a capacity claim, it writes
no artifact, and it is not a required release gate. Set ``PALIMPSEST_V4_SCALE_IDS``
to a positive integer (maximum 100000) to run it.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time

import pytest

from simulation.scale import partition_balance, stable_partition
from world.identifiers import AgentId

pytestmark = pytest.mark.unit

_LOG = logging.getLogger("tests.benchmarks.v4_scale_contract")
_ENV_VAR = "PALIMPSEST_V4_SCALE_IDS"
_MAX_IDS = 100_000
_PARTITIONS = 16


def _requested_ids() -> int:
    raw = os.environ.get(_ENV_VAR, "").strip()
    if not raw:
        pytest.skip(f"{_ENV_VAR} unset")
    try:
        count = int(raw)
    except ValueError:
        pytest.fail(f"{_ENV_VAR} must be an integer, got {raw!r}")
    if not 1 <= count <= _MAX_IDS:
        pytest.fail(f"{_ENV_VAR} must be between 1 and {_MAX_IDS}, got {count}")
    return count


def _digest(partitions: tuple[tuple[AgentId, ...], ...]) -> str:
    indexes = sorted(
        (agent_id.value, str(index))
        for index, partition in enumerate(partitions)
        for agent_id in partition
    )
    encoded = "\n".join(f"{value}:{index}" for value, index in indexes).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_v4_scale_contract_partition_mapping() -> None:
    count = _requested_ids()
    agent_ids = [AgentId(f"scale-agent-{index:06d}") for index in range(count)]

    started = time.perf_counter()
    partitions = stable_partition(agent_ids, partitions=_PARTITIONS)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

    flattened = [agent_id for partition in partitions for agent_id in partition]
    assert len(flattened) == count
    assert len(set(flattened)) == count
    assert set(flattened) == set(agent_ids)

    assignment = {
        agent_id: index
        for index, partition in enumerate(partitions)
        for agent_id in partition
    }
    for agent_id in agent_ids[:: max(1, count // 64)]:
        (single,) = [
            index
            for index, bucket in enumerate(
                stable_partition([agent_id], partitions=_PARTITIONS)
            )
            if bucket
        ]
        assert assignment[agent_id] == single

    first = _digest(partitions)
    second = _digest(stable_partition(agent_ids, partitions=_PARTITIONS))
    assert first == second

    _LOG.info(
        "v4_scale_contract_measured id_count=%s partition_count=%s elapsed_ms=%s "
        "partition_balance=%.4f index_digest_prefix=%s",
        count,
        _PARTITIONS,
        elapsed_ms,
        partition_balance(partitions),
        first[:12],
    )
