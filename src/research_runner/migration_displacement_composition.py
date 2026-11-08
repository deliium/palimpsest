"""Opt-in CLI producer for migration-displacement publications."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.migration_displacement_publication import (
    migration_displacement_publication_document,
    publish_migration_displacement_snapshot,
)
from persistence.migration_displacement_filesystem import (
    MigrationDisplacementPublisherOptions,
    create_migration_displacement_publisher,
)

__all__ = [
    "MIGRATION_DISPLACEMENT_ROOT_ENV",
    "MigrationDisplacementProducerOptions",
    "migration_displacement_producer_options_from_args",
    "publish_migration_displacement_harvest",
    "write_migration_displacement_receipt",
]

MIGRATION_DISPLACEMENT_ROOT_ENV: Final[str] = (
    "PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT"
)


@dataclass(frozen=True, slots=True)
class MigrationDisplacementProducerOptions:
    root: Path | None = None
    max_publications: int = 16
    max_bytes: int = 8_388_608

    @property
    def enabled(self) -> bool:
        return self.root is not None


def migration_displacement_producer_options_from_args(
    args: object,
) -> MigrationDisplacementProducerOptions:
    return MigrationDisplacementProducerOptions(
        root=(
            Path(args.migration_displacement_root)
            if getattr(args, "migration_displacement_root", None)
            else None
        ),
        max_publications=int(
            getattr(args, "migration_displacement_max_publications", 16)
        ),
        max_bytes=int(
            getattr(args, "migration_displacement_max_bytes", 8_388_608)
        ),
    )


def publish_migration_displacement_harvest(
    runner_result: object,
    options: MigrationDisplacementProducerOptions,
    *,
    committed_events: object,
    run_id: str,
) -> dict[str, object]:
    if not options.enabled:
        receipt = publish_migration_displacement_snapshot(
            runner_result,
            None,
            committed_events=committed_events,  # type: ignore[arg-type]
            run_id=run_id,
        )
        return migration_displacement_publication_document(receipt)
    publisher = create_migration_displacement_publisher(
        options.root,  # type: ignore[arg-type]
        MigrationDisplacementPublisherOptions(
            max_publications=options.max_publications,
            max_bytes=options.max_bytes,
        ),
    )
    receipt = publish_migration_displacement_snapshot(
        runner_result,
        publisher,
        committed_events=committed_events,  # type: ignore[arg-type]
        run_id=run_id,
    )
    return migration_displacement_publication_document(receipt)


def write_migration_displacement_receipt(
    artifact_root: Path, run_id: str, receipt: dict[str, object]
) -> None:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise ValueError("migration_displacement_receipt_run_id")
    path = artifact_root / f"migration-displacement-publication-{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, sort_keys=True, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
