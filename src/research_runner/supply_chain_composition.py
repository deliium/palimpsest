"""Opt-in CLI producer for supply-chain publications."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.supply_chain_publication import (
    SupplyChainHarvest,
    publish_supply_chain_snapshot,
)
from persistence.supply_chain_filesystem import (
    SupplyChainPublisherOptions,
    create_supply_chain_publisher,
)

__all__ = [
    "SUPPLY_CHAINS_ROOT_ENV",
    "SupplyChainProducerOptions",
    "publish_supply_chain_harvest",
    "supply_chain_producer_options_from_args",
    "write_supply_chain_receipt",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.supply_chain_composition"
)

SUPPLY_CHAINS_ROOT_ENV: Final[str] = "PALIMPSEST_SUPPLY_CHAINS_ROOT"


@dataclass(frozen=True, slots=True)
class SupplyChainProducerOptions:
    root: Path | None = None
    max_publications: int = 16
    max_bytes: int = 8_388_608

    @property
    def enabled(self) -> bool:
        return self.root is not None


def supply_chain_producer_options_from_args(
    args: object,
) -> SupplyChainProducerOptions:
    root_value = getattr(args, "supply_chains_root", None)
    return SupplyChainProducerOptions(
        root=Path(root_value) if root_value else None,
        max_publications=int(getattr(args, "supply_chains_max_publications", 16)),
        max_bytes=int(getattr(args, "supply_chains_max_bytes", 8_388_608)),
    )


def publish_supply_chain_harvest(
    harvest: SupplyChainHarvest | None,
    *,
    options: SupplyChainProducerOptions,
) -> tuple[bool, str]:
    if not options.enabled or harvest is None:
        return (False, "supply_chain_publication_disabled")
    publisher = create_supply_chain_publisher(
        options.root,  # type: ignore[arg-type]
        SupplyChainPublisherOptions(
            max_publications=options.max_publications,
            max_bytes=options.max_bytes,
        ),
    )
    try:
        receipt = publish_supply_chain_snapshot(harvest, publisher)
    except Exception as exc:
        _LOG.error(
            "supply_chain_publication_failed code=%s",
            getattr(exc, "reason_code", type(exc).__name__),
        )
        return (False, "supply_chain_publication_failed")
    if receipt.stored:
        _LOG.info(
            "supply_chain_publication_stored publications=%s",
            1,
        )
    return (receipt.stored, receipt.reason)


def write_supply_chain_receipt(
    artifact_root: Path, run_id: str, receipt: dict[str, object]
) -> None:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise ValueError("supply_chain_receipt_run_id")
    path = artifact_root / f"supply-chains-publication-{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
