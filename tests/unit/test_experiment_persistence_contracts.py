"""Unit tests for experiment persistence contracts."""

from __future__ import annotations

import pytest

from experiments.memory_repository import InMemoryExperimentRecordRepository
from experiments.persistence import (
    ExperimentAssignmentRecord,
    ExperimentDefinitionRecord,
    ExperimentResultRecord,
)


@pytest.mark.asyncio
async def test_append_definition_idempotent_and_conflict() -> None:
    repo = InMemoryExperimentRecordRepository()
    record = ExperimentDefinitionRecord(
        experiment_id="exp-1",
        schema_version="experiment-record-v1",
        payload_hash="a" * 64,
        definition_fingerprint="b" * 64,
    )
    await repo.append_definition(record)
    await repo.append_definition(record)
    with pytest.raises(ValueError, match="conflict"):
        await repo.append_definition(
            ExperimentDefinitionRecord(
                experiment_id="exp-1",
                schema_version="experiment-record-v1",
                payload_hash="c" * 64,
                definition_fingerprint="b" * 64,
            )
        )
    loaded = await repo.get_definition("exp-1")
    assert loaded == record


@pytest.mark.asyncio
async def test_assignment_and_result_ordering() -> None:
    repo = InMemoryExperimentRecordRepository()
    await repo.append_definition(
        ExperimentDefinitionRecord(
            experiment_id="exp-1",
            schema_version="experiment-record-v1",
            payload_hash="a" * 64,
            definition_fingerprint="b" * 64,
        )
    )
    for seed_ordinal, condition_id in ((1, "c-b"), (0, "c-a"), (0, "c-b")):
        await repo.append_assignment(
            ExperimentAssignmentRecord(
                experiment_id="exp-1",
                condition_id=condition_id,
                seed_ordinal=seed_ordinal,
                replicate_index=0,
                run_id=f"run-{condition_id}-{seed_ordinal}",
                seed=seed_ordinal,
                config_fingerprint="d" * 64,
            )
        )
    listed = await repo.list_assignments("exp-1")
    assert [item.condition_id for item in listed] == ["c-a", "c-b", "c-b"]
    await repo.append_result(
        ExperimentResultRecord(
            run_id="run-c-a-0",
            experiment_id="exp-1",
            condition_id="c-a",
            payload_hash="e" * 64,
            stop_reason="max_ticks",
            ticks_committed=1,
        )
    )
