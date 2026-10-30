"""Persist objective bootstrap rows for API tests with custom tick executors."""

from dataclasses import replace

from tests.simulation_helpers import hashed_bootstrap_snapshot

from infrastructure.database import DatabaseResources
from persistence import create_run_repository
from simulation.journal import hash_snapshot
from simulation.models import RunId
from simulation.persistence import RunCreateRequest, SnapshotId


async def seed_api_run(resources: DatabaseResources, run_id: str) -> None:
    """Custom executors bypass the production runner's bootstrap persistence."""
    draft = replace(
        hashed_bootstrap_snapshot(run_id=run_id),
        snapshot_id=SnapshotId(f"snap-{run_id}"),
    )
    bootstrap = replace(draft, integrity_hash=hash_snapshot(draft))
    await create_run_repository(resources.session_factory).create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=bootstrap.world_id,
            seed=bootstrap.seed,
            config=bootstrap.config,
            bootstrap=bootstrap,
        )
    )
