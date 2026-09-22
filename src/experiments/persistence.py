"""Experiment-specific persistence DTOs and ports (framework-free).

Concrete SQLAlchemy adapters live in ``persistence`` and may import these
contracts. The ``experiments`` package never imports SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from world.identifiers import require_stable_id

EXPERIMENT_RECORD_SCHEMA_VERSION = "experiment-record-v1"


@dataclass(frozen=True, slots=True)
class ExperimentDefinitionRecord:
    """Immutable persisted experiment definition envelope."""

    experiment_id: str
    schema_version: str
    payload_hash: str
    definition_fingerprint: str

    def __post_init__(self) -> None:
        require_stable_id("experiment_id", self.experiment_id)
        require_stable_id("schema_version", self.schema_version)
        require_stable_id("payload_hash", self.payload_hash)
        require_stable_id("definition_fingerprint", self.definition_fingerprint)


@dataclass(frozen=True, slots=True)
class ExperimentAssignmentRecord:
    """Immutable condition/seed/replicate assignment cell."""

    experiment_id: str
    condition_id: str
    seed_ordinal: int
    replicate_index: int
    run_id: str
    seed: int
    config_fingerprint: str

    def __post_init__(self) -> None:
        require_stable_id("experiment_id", self.experiment_id)
        require_stable_id("condition_id", self.condition_id)
        require_stable_id("run_id", self.run_id)
        require_stable_id("config_fingerprint", self.config_fingerprint)
        if type(self.seed_ordinal) is not int or self.seed_ordinal < 0:
            raise ValueError("seed_ordinal must be non-negative int")
        if type(self.replicate_index) is not int or self.replicate_index < 0:
            raise ValueError("replicate_index must be non-negative int")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be non-negative int")


@dataclass(frozen=True, slots=True)
class ExperimentResultRecord:
    """Immutable final result for one assigned run."""

    run_id: str
    experiment_id: str
    condition_id: str
    payload_hash: str
    stop_reason: str
    ticks_committed: int

    def __post_init__(self) -> None:
        require_stable_id("run_id", self.run_id)
        require_stable_id("experiment_id", self.experiment_id)
        require_stable_id("condition_id", self.condition_id)
        require_stable_id("payload_hash", self.payload_hash)
        require_stable_id("stop_reason", self.stop_reason)
        if type(self.ticks_committed) is not int or self.ticks_committed < 0:
            raise ValueError("ticks_committed must be non-negative int")


class ExperimentRecordRepository(Protocol):
    """Append-only experiment definition/assignment/result port."""

    async def append_definition(self, record: ExperimentDefinitionRecord) -> None: ...

    async def append_assignment(self, record: ExperimentAssignmentRecord) -> None: ...

    async def append_result(self, record: ExperimentResultRecord) -> None: ...

    async def get_definition(
        self, experiment_id: str
    ) -> ExperimentDefinitionRecord | None: ...

    async def list_assignments(
        self, experiment_id: str
    ) -> tuple[ExperimentAssignmentRecord, ...]: ...
