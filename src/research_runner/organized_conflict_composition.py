# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Opt-in CLI producer for organized-conflict publications."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.organized_conflict_publication import (
    build_organized_conflict_harvest_result,
    organized_conflict_publication_document,
    publish_organized_conflict_snapshot,
)
from persistence.organized_conflict_filesystem import (
    OrganizedConflictPublisherOptions,
    create_organized_conflict_publisher,
)

__all__ = [
    "ORGANIZED_CONFLICT_ROOT_ENV",
    "OrganizedConflictProducerOptions",
    "producer_options_from_args",
    "publish_organized_conflict_harvest",
    "write_organized_conflict_receipt",
]

ORGANIZED_CONFLICT_ROOT_ENV: Final[str] = "PALIMPSEST_ORGANIZED_CONFLICT_ROOT"


@dataclass(frozen=True, slots=True)
class OrganizedConflictProducerOptions:
    root: Path | None = None
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024

    @property
    def enabled(self) -> bool:
        return self.root is not None


def producer_options_from_args(args: object) -> OrganizedConflictProducerOptions:
    return OrganizedConflictProducerOptions(
        root=(
            Path(args.organized_conflict_root)
            if getattr(args, "organized_conflict_root", None)
            else None
        ),
        max_publications=int(getattr(args, "organized_conflict_max_publications", 16)),
        max_bytes=int(getattr(args, "organized_conflict_max_bytes", 8_388_608)),
    )


def publish_organized_conflict_harvest(
    runner_result: object,
    options: OrganizedConflictProducerOptions,
    *,
    committed_events: object,
    run_id: str,
) -> dict[str, object]:
    if not options.enabled:
        return organized_conflict_publication_document(
            build_organized_conflict_harvest_result(
                runner_result, committed_events, run_id=run_id
            )
        ).copy() | {"status": "disabled", "reason": "root_unset"}
    result = build_organized_conflict_harvest_result(
        runner_result, committed_events, run_id=run_id
    )
    if result.snapshot is not None:
        publisher = create_organized_conflict_publisher(
            options.root,  # type: ignore[arg-type]
            OrganizedConflictPublisherOptions(
                max_publications=options.max_publications,
                max_bytes=options.max_bytes,
            ),
        )
        result = publish_organized_conflict_snapshot(result, publisher)
    return organized_conflict_publication_document(result)


def write_organized_conflict_receipt(
    artifact_root: Path, run_id: str, receipt: dict[str, object]
) -> None:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise ValueError("organized_conflict_receipt_run_id")
    path = artifact_root / f"organized-conflict-publication-{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, sort_keys=True, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
