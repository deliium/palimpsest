# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Opt-in CLI producer for border publications."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Final

from experiments.borders_publication import (
    borders_publication_document,
    publish_borders_snapshot,
)
from persistence.borders_filesystem import (
    BordersPublisherOptions,
    create_borders_publisher,
)

__all__ = [
    "BORDERS_ROOT_ENV",
    "BordersProducerOptions",
    "borders_producer_options_from_args",
    "publish_borders_harvest",
    "write_borders_receipt",
]

BORDERS_ROOT_ENV: Final[str] = "PALIMPSEST_BORDERS_ROOT"


@dataclass(frozen=True, slots=True)
class BordersProducerOptions:
    root: Path | None = None
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024

    @property
    def enabled(self) -> bool:
        return self.root is not None


def borders_producer_options_from_args(args: object) -> BordersProducerOptions:
    return BordersProducerOptions(
        root=(
            Path(args.borders_root)
            if getattr(args, "borders_root", None)
            else None
        ),
        max_publications=int(getattr(args, "borders_max_publications", 16)),
        max_bytes=int(getattr(args, "borders_max_bytes", 8_388_608)),
    )


def publish_borders_harvest(
    runner_result: object,
    options: BordersProducerOptions,
    *,
    committed_events: object,
    run_id: str,
) -> dict[str, object]:
    if not options.enabled:
        receipt = publish_borders_snapshot(
            runner_result,
            SimpleNamespace(publisher=None),
            committed_events,
            run_id,
        )
        document = borders_publication_document(receipt)
        if document["status"] == "disabled":
            document["reason"] = "root_unset"
        return document
    publisher = create_borders_publisher(
        options.root,  # type: ignore[arg-type]
        BordersPublisherOptions(
            max_publications=options.max_publications,
            max_bytes=options.max_bytes,
        ),
    )
    receipt = publish_borders_snapshot(
        runner_result,
        SimpleNamespace(publisher=publisher),
        committed_events,
        run_id,
    )
    return borders_publication_document(receipt)


def write_borders_receipt(
    artifact_root: Path, run_id: str, receipt: dict[str, object]
) -> None:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise ValueError("borders_receipt_run_id")
    path = artifact_root / f"borders-publication-{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, sort_keys=True, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
