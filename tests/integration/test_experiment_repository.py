"""PostgreSQL integration for experiment definition/assignment/result records."""

from __future__ import annotations

import uuid

import pytest

from experiments.persistence import (
    ExperimentAssignmentRecord,
    ExperimentDefinitionRecord,
    ExperimentResultRecord,
)
from infrastructure.database import DatabaseResources
from persistence import create_experiment_record_repository
from persistence.errors import PersistenceConflictError

pytestmark = pytest.mark.integration

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@pytest.mark.asyncio
async def test_experiment_record_idempotent_and_ordered(
    database_resources: DatabaseResources,
) -> None:
    repo = create_experiment_record_repository(database_resources.session_factory)
    experiment_id = _unique("exp")
    definition = ExperimentDefinitionRecord(
        experiment_id=experiment_id,
        schema_version="experiment-record-v1",
        payload_hash=_HASH_A,
        definition_fingerprint=_HASH_B,
    )
    await repo.append_definition(definition)
    await repo.append_definition(definition)

    with pytest.raises(PersistenceConflictError):
        await repo.append_definition(
            ExperimentDefinitionRecord(
                experiment_id=experiment_id,
                schema_version="experiment-record-v1",
                payload_hash=_HASH_C,
                definition_fingerprint=_HASH_B,
            )
        )

    assignments = [
        ExperimentAssignmentRecord(
            experiment_id=experiment_id,
            condition_id="c-b",
            seed_ordinal=1,
            replicate_index=0,
            run_id=_unique("run-b1"),
            seed=7,
            config_fingerprint=_HASH_A,
        ),
        ExperimentAssignmentRecord(
            experiment_id=experiment_id,
            condition_id="c-a",
            seed_ordinal=0,
            replicate_index=0,
            run_id=_unique("run-a0"),
            seed=3,
            config_fingerprint=_HASH_A,
        ),
        ExperimentAssignmentRecord(
            experiment_id=experiment_id,
            condition_id="c-b",
            seed_ordinal=0,
            replicate_index=0,
            run_id=_unique("run-b0"),
            seed=5,
            config_fingerprint=_HASH_A,
        ),
    ]
    for item in assignments:
        await repo.append_assignment(item)

    listed = await repo.list_assignments(experiment_id)
    assert [item.condition_id for item in listed] == ["c-a", "c-b", "c-b"]
    assert [item.seed_ordinal for item in listed] == [0, 0, 1]

    first = listed[0]
    await repo.append_result(
        ExperimentResultRecord(
            run_id=first.run_id,
            experiment_id=experiment_id,
            condition_id=first.condition_id,
            payload_hash=_HASH_C,
            stop_reason="max_ticks",
            ticks_committed=2,
        )
    )
    await repo.append_result(
        ExperimentResultRecord(
            run_id=first.run_id,
            experiment_id=experiment_id,
            condition_id=first.condition_id,
            payload_hash=_HASH_C,
            stop_reason="max_ticks",
            ticks_committed=2,
        )
    )
    with pytest.raises(PersistenceConflictError):
        await repo.append_result(
            ExperimentResultRecord(
                run_id=first.run_id,
                experiment_id=experiment_id,
                condition_id=first.condition_id,
                payload_hash=_HASH_A,
                stop_reason="max_ticks",
                ticks_committed=2,
            )
        )

    loaded = await repo.get_definition(experiment_id)
    assert loaded == definition
