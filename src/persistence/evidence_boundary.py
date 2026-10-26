"""Shared run-scoped objective evidence boundary resolution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final
from unicodedata import category

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.errors import PersistenceAdapterError, PersistenceNotFoundError
from persistence.orm import SimulationRunOrm, TickCommitOrm, WorldSnapshotOrm
from persistence.readers import snapshot_from_canonical_payload
from simulation.clock import Tick
from simulation.evidence import EvidenceManifest

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.evidence_boundary"
)


def _require_stable_id(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a str")
    length = len(value)
    if length < 1 or length > 128:
        raise ValueError(f"{name} must be between 1 and 128 Unicode code points")
    if value != value.strip():
        raise ValueError(f"{name} must not have leading or trailing whitespace")
    if any(category(char) == "Cc" for char in value):
        raise ValueError(f"{name} must not contain control characters")
    return value


@dataclass(frozen=True, slots=True)
class ObjectiveEvidenceBoundary:
    """Whole-commit objective high-water for one manifest or latest head."""

    run_id: str
    boundary_tick: Tick
    through_tick: Tick | None
    bootstrap_only: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "run_id", _require_stable_id("run_id", self.run_id)
        )
        if type(self.boundary_tick) is not Tick:
            raise TypeError("boundary_tick must be Tick")
        if self.through_tick is not None and type(self.through_tick) is not Tick:
            raise TypeError("through_tick must be Tick or None")
        if self.bootstrap_only and self.through_tick is not None:
            raise ValueError("bootstrap-only boundary cannot have a commit tick")
        if type(self.bootstrap_only) is not bool:
            raise TypeError("bootstrap_only must be bool")


async def resolve_objective_evidence_boundary(
    session: AsyncSession,
    *,
    run_id: str,
    manifest: EvidenceManifest | None,
) -> ObjectiveEvidenceBoundary:
    """Resolve a manifest anchor to a whole-commit bound, or latest head."""
    if not isinstance(session, AsyncSession):
        raise TypeError("session must be AsyncSession")
    run_id = _require_stable_id("run_id", run_id)
    if manifest is not None and type(manifest) is not EvidenceManifest:
        raise TypeError("manifest must be EvidenceManifest or None")
    if manifest is not None and manifest.run_id != run_id:
        raise PersistenceAdapterError(
            "manifest_run_scope_mismatch", operation="resolve_evidence_boundary"
        )
    run_row = await session.get(SimulationRunOrm, run_id)
    if run_row is None:
        raise PersistenceNotFoundError(
            "run_not_found", operation="resolve_evidence_boundary"
        )
    if manifest is None:
        latest = (
            await session.execute(
                select(TickCommitOrm)
                .where(TickCommitOrm.run_id == run_id)
                .order_by(TickCommitOrm.tick.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is None:
            return ObjectiveEvidenceBoundary(
                run_id=run_id,
                boundary_tick=Tick(0),
                through_tick=None,
                bootstrap_only=True,
            )
        return ObjectiveEvidenceBoundary(
            run_id=run_id,
            boundary_tick=Tick(latest.resulting_tick),
            through_tick=Tick(latest.tick),
            bootstrap_only=False,
        )
    bootstrap_row = await session.get(
        WorldSnapshotOrm, run_row.bootstrap_snapshot_id
    )
    if bootstrap_row is None:
        raise PersistenceNotFoundError(
            "bootstrap_snapshot_not_found",
            operation="resolve_evidence_boundary",
        )
    bootstrap = snapshot_from_canonical_payload(
        bootstrap_row.canonical_payload,
        expected_integrity_hash=bootstrap_row.integrity_hash,
    )
    high_water = (
        await session.execute(
            select(TickCommitOrm).where(
                TickCommitOrm.run_id == run_id,
                TickCommitOrm.commit_hash == manifest.objective_commit_hash,
            )
        )
    ).scalar_one_or_none()
    if high_water is not None:
        boundary = ObjectiveEvidenceBoundary(
            run_id=run_id,
            boundary_tick=Tick(high_water.resulting_tick),
            through_tick=Tick(high_water.tick),
            bootstrap_only=False,
        )
    elif manifest.objective_commit_hash == bootstrap.integrity_hash.value:
        boundary = ObjectiveEvidenceBoundary(
            run_id=run_id,
            boundary_tick=Tick(0),
            through_tick=None,
            bootstrap_only=True,
        )
    else:
        raise PersistenceAdapterError(
            "manifest_objective_commit_not_found",
            operation="resolve_evidence_boundary",
        )
    _LOG.debug(
        "objective_evidence_boundary_resolved run_id=%s boundary_tick=%s "
        "through_tick=%s bootstrap_only=%s",
        run_id,
        boundary.boundary_tick.value,
        None if boundary.through_tick is None else boundary.through_tick.value,
        boundary.bootstrap_only,
    )
    return boundary


__all__ = [
    "ObjectiveEvidenceBoundary",
    "resolve_objective_evidence_boundary",
]
