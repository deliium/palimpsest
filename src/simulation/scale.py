"""Deterministic V4 population-scale contracts.

Partition assignment is a pure function of ``(namespace, agent_id)`` and the
partition count: no ``hash()``, no process state, no wall clock, no randomness.
Budgets are declarative; V4-01 does not enforce them at runtime and claims no
capacity.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, NoReturn

from world.identifiers import AgentId

SCALE_CONTRACT_VERSION: Final[str] = "v4-scale-contract-v1"
SCALE_PARTITION_NAMESPACE: Final[str] = "palimpsest-scale-partition-v1"
SCALE_MAX_PARTITIONS: Final[int] = 4096
SCALE_MAX_POPULATION: Final[int] = 100_000


def _fail(code: str) -> NoReturn:
    raise ValueError(code)


@dataclass(frozen=True, slots=True)
class ScaleBudget:
    """Declarative per-run scale limits; never enforced by V4-01."""

    max_population: int
    max_commands_per_tick: int
    max_observer_rows: int

    def __post_init__(self) -> None:
        for name in ("max_population", "max_commands_per_tick", "max_observer_rows"):
            value = getattr(self, name)
            if type(value) is not int:
                _fail(f"scale_budget_not_int:{name}")
            if value <= 0:
                _fail(f"scale_budget_not_positive:{name}")
        if self.max_population > SCALE_MAX_POPULATION:
            _fail("scale_budget_population_limit")


def _partition_index(agent_id: AgentId, *, partitions: int, namespace: str) -> int:
    digest = hashlib.blake2b(
        f"{namespace}\x00{agent_id.value}".encode(),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "big") % partitions


def stable_partition(
    agent_ids: Iterable[AgentId],
    *,
    partitions: int,
    namespace: str = SCALE_PARTITION_NAMESPACE,
) -> tuple[tuple[AgentId, ...], ...]:
    """Order-preserving deterministic partition of ``agent_ids``."""
    if type(partitions) is not int or not 1 <= partitions <= SCALE_MAX_PARTITIONS:
        _fail("scale_partitions_invalid")
    materialized = tuple(agent_ids)
    if len(set(materialized)) != len(materialized):
        _fail("duplicate_agent_id")

    buckets: list[list[AgentId]] = [[] for _ in range(partitions)]
    for agent_id in materialized:
        bucket = _partition_index(agent_id, partitions=partitions, namespace=namespace)
        buckets[bucket].append(agent_id)
    return tuple(tuple(bucket) for bucket in buckets)


def partition_balance(partitions: tuple[tuple[AgentId, ...], ...]) -> float:
    """``max_size / mean_size`` across partitions; ``0.0`` when empty."""
    total = sum(len(partition) for partition in partitions)
    if total == 0 or not partitions:
        return 0.0
    largest = max(len(partition) for partition in partitions)
    return largest / (total / len(partitions))


def validate_scale_budget(budget: ScaleBudget, population: int) -> None:
    """Fail closed when ``population`` exceeds the declared budget."""
    if type(budget) is not ScaleBudget:
        raise TypeError("validate_scale_budget requires ScaleBudget")
    if type(population) is not int or population < 0:
        _fail("scale_population_invalid")
    if population > budget.max_population:
        _fail("scale_budget_exceeded")


def scale_contract_payload() -> dict[str, object]:
    """JSON-safe contract identity and limits for docs and tests."""
    return {
        "contract_version": SCALE_CONTRACT_VERSION,
        "partition_namespace": SCALE_PARTITION_NAMESPACE,
        "max_partitions": SCALE_MAX_PARTITIONS,
        "max_population": SCALE_MAX_POPULATION,
    }


__all__ = [
    "SCALE_CONTRACT_VERSION",
    "SCALE_MAX_PARTITIONS",
    "SCALE_MAX_POPULATION",
    "SCALE_PARTITION_NAMESPACE",
    "ScaleBudget",
    "partition_balance",
    "scale_contract_payload",
    "stable_partition",
    "validate_scale_budget",
]
