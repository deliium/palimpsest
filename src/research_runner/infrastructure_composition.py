"""Opt-in CLI producer for infrastructure-networks publications."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.infrastructure_publication import (
    infrastructure_networks_publication_document,
    publish_infrastructure_networks_snapshot,
)
from persistence.infrastructure_filesystem import (
    InfrastructureNetworksPublisherOptions,
    create_infrastructure_networks_publisher,
)

__all__ = [
    "INFRASTRUCTURE_NETWORKS_ROOT_ENV",
    "InfrastructureNetworksProducerOptions",
    "infrastructure_networks_producer_options_from_args",
    "publish_infrastructure_networks_harvest",
    "write_infrastructure_networks_receipt",
]

INFRASTRUCTURE_NETWORKS_ROOT_ENV: Final[str] = "PALIMPSEST_INFRASTRUCTURE_NETWORKS_ROOT"


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksProducerOptions:
    root: Path | None = None
    max_publications: int = 16
    max_bytes: int = 8_388_608

    @property
    def enabled(self) -> bool:
        return self.root is not None


def infrastructure_networks_producer_options_from_args(
    args: object,
) -> InfrastructureNetworksProducerOptions:
    return InfrastructureNetworksProducerOptions(
        root=(
            Path(args.infrastructure_networks_root)
            if getattr(args, "infrastructure_networks_root", None)
            else None
        ),
        max_publications=int(
            getattr(args, "infrastructure_networks_max_publications", 16)
        ),
        max_bytes=int(getattr(args, "infrastructure_networks_max_bytes", 8_388_608)),
    )


def publish_infrastructure_networks_harvest(
    runner_result: object,
    options: InfrastructureNetworksProducerOptions,
    *,
    committed_events: object,
    run_id: str,
) -> dict[str, object]:
    if not options.enabled:
        receipt = publish_infrastructure_networks_snapshot(
            runner_result,
            None,
            committed_events=committed_events,  # type: ignore[arg-type]
            run_id=run_id,
        )
        return infrastructure_networks_publication_document(receipt)
    publisher = create_infrastructure_networks_publisher(
        options.root,  # type: ignore[arg-type]
        InfrastructureNetworksPublisherOptions(
            max_publications=options.max_publications,
            max_bytes=options.max_bytes,
        ),
    )
    receipt = publish_infrastructure_networks_snapshot(
        runner_result,
        publisher,
        committed_events=committed_events,  # type: ignore[arg-type]
        run_id=run_id,
    )
    return infrastructure_networks_publication_document(receipt)


def write_infrastructure_networks_receipt(
    artifact_root: Path, run_id: str, receipt: dict[str, object]
) -> None:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise ValueError("infrastructure_networks_receipt_run_id")
    path = artifact_root / f"infrastructure-networks-publication-{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, sort_keys=True, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
