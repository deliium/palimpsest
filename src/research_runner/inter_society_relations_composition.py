# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Opt-in CLI producer for inter-society-relations publications."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.inter_society_relations_publication import (
    inter_society_relations_publication_document,
    publish_inter_society_relations_snapshot,
)
from persistence.inter_society_relations_filesystem import (
    InterSocietyRelationsPublisherOptions,
    create_inter_society_relations_publisher,
)

__all__ = [
    "INTER_SOCIETY_RELATIONS_ROOT_ENV",
    "InterSocietyRelationsProducerOptions",
    "inter_society_relations_producer_options_from_args",
    "publish_inter_society_relations_harvest",
    "write_inter_society_relations_receipt",
]

INTER_SOCIETY_RELATIONS_ROOT_ENV: Final[str] = "PALIMPSEST_INTER_SOCIETY_RELATIONS_ROOT"


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsProducerOptions:
    root: Path | None = None
    max_publications: int = 16
    max_bytes: int = 8_388_608

    @property
    def enabled(self) -> bool:
        return self.root is not None


def inter_society_relations_producer_options_from_args(
    args: object,
) -> InterSocietyRelationsProducerOptions:
    return InterSocietyRelationsProducerOptions(
        root=(
            Path(args.inter_society_relations_root)
            if getattr(args, "inter_society_relations_root", None)
            else None
        ),
        max_publications=int(
            getattr(args, "inter_society_relations_max_publications", 16)
        ),
        max_bytes=int(getattr(args, "inter_society_relations_max_bytes", 8_388_608)),
    )


def publish_inter_society_relations_harvest(
    runner_result: object,
    options: InterSocietyRelationsProducerOptions,
    *,
    committed_events: object,
    run_id: str,
) -> dict[str, object]:
    if not options.enabled:
        receipt = publish_inter_society_relations_snapshot(
            runner_result,
            None,
            committed_events=committed_events,  # type: ignore[arg-type]
            run_id=run_id,
        )
        return inter_society_relations_publication_document(receipt)
    publisher = create_inter_society_relations_publisher(
        options.root,  # type: ignore[arg-type]
        InterSocietyRelationsPublisherOptions(
            max_publications=options.max_publications,
            max_bytes=options.max_bytes,
        ),
    )
    receipt = publish_inter_society_relations_snapshot(
        runner_result,
        publisher,
        committed_events=committed_events,  # type: ignore[arg-type]
        run_id=run_id,
    )
    return inter_society_relations_publication_document(receipt)


def write_inter_society_relations_receipt(
    artifact_root: Path, run_id: str, receipt: dict[str, object]
) -> None:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise ValueError("inter_society_relations_receipt_run_id")
    path = artifact_root / f"inter-society-relations-publication-{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, sort_keys=True, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
