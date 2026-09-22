"""In-memory experiment record repository for unit tests."""

from __future__ import annotations

from experiments.persistence import (
    ExperimentAssignmentRecord,
    ExperimentDefinitionRecord,
    ExperimentResultRecord,
)


class InMemoryExperimentRecordRepository:
    """Copy-on-write in-memory append-only experiment records."""

    __slots__ = ("_assignments", "_definitions", "_results")

    def __init__(self) -> None:
        self._definitions: dict[str, ExperimentDefinitionRecord] = {}
        self._assignments: dict[
            tuple[str, str, int, int], ExperimentAssignmentRecord
        ] = {}
        self._results: dict[str, ExperimentResultRecord] = {}

    async def append_definition(self, record: ExperimentDefinitionRecord) -> None:
        existing = self._definitions.get(record.experiment_id)
        if existing is not None:
            if existing != record:
                raise ValueError("definition conflict")
            return
        self._definitions[record.experiment_id] = record

    async def append_assignment(self, record: ExperimentAssignmentRecord) -> None:
        key = (
            record.experiment_id,
            record.condition_id,
            record.seed_ordinal,
            record.replicate_index,
        )
        existing = self._assignments.get(key)
        if existing is not None:
            if existing != record:
                raise ValueError("assignment conflict")
            return
        self._assignments[key] = record

    async def append_result(self, record: ExperimentResultRecord) -> None:
        existing = self._results.get(record.run_id)
        if existing is not None:
            if existing != record:
                raise ValueError("result conflict")
            return
        self._results[record.run_id] = record

    async def get_definition(
        self, experiment_id: str
    ) -> ExperimentDefinitionRecord | None:
        return self._definitions.get(experiment_id)

    async def list_assignments(
        self, experiment_id: str
    ) -> tuple[ExperimentAssignmentRecord, ...]:
        items = [
            record
            for key, record in self._assignments.items()
            if key[0] == experiment_id
        ]
        items.sort(
            key=lambda item: (
                item.condition_id,
                item.seed_ordinal,
                item.replicate_index,
            )
        )
        return tuple(items)

    async def get_membership(
        self, *, experiment_id: str, run_id: str
    ):
        from experiments.persistence import ExperimentMembership

        for record in self._assignments.values():
            if record.experiment_id == experiment_id and record.run_id == run_id:
                return ExperimentMembership(
                    experiment_id=record.experiment_id,
                    run_id=record.run_id,
                    source="assignment",
                    condition_id=record.condition_id,
                )
        return None

    async def get_membership_for_run(self, *, run_id: str):
        from experiments.persistence import ExperimentMembership

        for record in self._assignments.values():
            if record.run_id == run_id:
                return ExperimentMembership(
                    experiment_id=record.experiment_id,
                    run_id=record.run_id,
                    source="assignment",
                    condition_id=record.condition_id,
                )
        return None
