"""Ordered V4 migration intent: no revision is created in V4-01.

A stage is a prerequisite record, not an approved migration. Each migrating
stage names the evidence that must be proven first, the flags it depends on,
its owner package, and its authority impact. Alembic head stays ``0017``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NoReturn

from simulation.compatibility import ALEMBIC_HEAD_REVISION, V4_CAPABILITY_FLAG_NAMES

V4_MIGRATION_PLAN_SCHEMA: Final[str] = "v4-migration-sequence-v1"

_MIGRATION_FILE_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{4})_.*\.py$")
_KNOWN_FLAGS: Final[frozenset[str]] = frozenset(V4_CAPABILITY_FLAG_NAMES)


@dataclass(frozen=True, slots=True)
class MigrationStage:
    """One ordered migration stage; ``requires_migration`` is intent only."""

    order: int
    stage_id: str
    requires_migration: bool
    trigger: str
    prerequisite_flags: tuple[str, ...]
    owner_package: str
    authority_impact: str


V4_MIGRATION_SEQUENCE: Final[tuple[MigrationStage, ...]] = (
    MigrationStage(
        order=1,
        stage_id="v4-m01-capability-scaffolding",
        requires_migration=False,
        trigger="V4-01 flags and version acceptance only",
        prerequisite_flags=(),
        owner_package="simulation",
        authority_impact="none",
    ),
    MigrationStage(
        order=2,
        stage_id="v4-m02-objective-network-state",
        requires_migration=True,
        trigger=(
            "proven indexed inspection need for network topology, capacity, or "
            "condition across runs"
        ),
        prerequisite_flags=("infrastructure_networks", "supply_chains"),
        owner_package="persistence",
        authority_impact="additive objective tables/indexes only",
    ),
    MigrationStage(
        order=3,
        stage_id="v4-m03-epidemic-host-state",
        requires_migration=True,
        trigger="proven indexed need for host/transmission history",
        prerequisite_flags=("epidemics",),
        owner_package="persistence",
        authority_impact="additive objective tables/indexes only",
    ),
    MigrationStage(
        order=4,
        stage_id="v4-m04-ecological-state",
        requires_migration=True,
        trigger="proven indexed need for regeneration/depletion history",
        prerequisite_flags=("ecological_feedback",),
        owner_package="persistence",
        authority_impact="additive objective tables/indexes only",
    ),
    MigrationStage(
        order=5,
        stage_id="v4-m05-disaster-state",
        requires_migration=True,
        trigger="proven indexed need for multi-location hazard history",
        prerequisite_flags=("disasters",),
        owner_package="persistence",
        authority_impact="additive objective tables/indexes only",
    ),
    MigrationStage(
        order=6,
        stage_id="v4-m06-resilience-read-model",
        requires_migration=True,
        trigger="detached resilience queries exceed bounded in-memory aggregation",
        prerequisite_flags=(),
        owner_package="persistence",
        authority_impact="read-model indexes only; no cognition or world authority",
    ),
)


def _fail(code: str) -> NoReturn:
    raise ValueError(code)


def validate_migration_sequence(
    current_head: str = ALEMBIC_HEAD_REVISION,
    stages: Sequence[MigrationStage] = V4_MIGRATION_SEQUENCE,
) -> None:
    """Validate stage order, ids, flags, and the pinned head."""
    if current_head != ALEMBIC_HEAD_REVISION:
        _fail("v4_migration_head_mismatch")

    stage_ids = [stage.stage_id for stage in stages]
    if len(set(stage_ids)) != len(stage_ids):
        _fail("v4_migration_duplicate_stage")
    if not all(stage_id.startswith("v4-m") for stage_id in stage_ids):
        _fail("v4_migration_stage_prefix")

    if [stage.order for stage in stages] != list(range(1, len(stages) + 1)):
        _fail("v4_migration_order")

    migrating_seen = False
    for stage in stages:
        if stage.requires_migration:
            migrating_seen = True
        elif migrating_seen:
            _fail("v4_migration_gap_after_migration")
        if not set(stage.prerequisite_flags) <= _KNOWN_FLAGS:
            _fail("v4_migration_unknown_flag")


def next_revision(current_head: str = ALEMBIC_HEAD_REVISION) -> str:
    """Zero-padded four-digit successor of ``current_head``."""
    return f"{int(current_head) + 1:04d}"


def unapplied_stages(
    current_head: str = ALEMBIC_HEAD_REVISION,
) -> tuple[MigrationStage, ...]:
    """Migrating stages that the current head has not applied yet."""
    if current_head != ALEMBIC_HEAD_REVISION:
        return ()
    return tuple(stage for stage in V4_MIGRATION_SEQUENCE if stage.requires_migration)


def future_migration_files(
    directory: Path, current_head: str = ALEMBIC_HEAD_REVISION
) -> tuple[Path, ...]:
    """Revision files in ``directory`` whose numeric prefix exceeds the head."""
    head = int(current_head)
    found: list[Path] = []
    for path in sorted(directory.glob("*.py")):
        match = _MIGRATION_FILE_RE.match(path.name)
        if match is None:
            continue
        if int(match.group(1)) > head:
            found.append(path)
    return tuple(found)


__all__ = [
    "V4_MIGRATION_PLAN_SCHEMA",
    "V4_MIGRATION_SEQUENCE",
    "MigrationStage",
    "future_migration_files",
    "next_revision",
    "unapplied_stages",
    "validate_migration_sequence",
]
