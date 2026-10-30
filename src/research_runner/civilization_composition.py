"""Trusted research-runner composition for optional civilization publication."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from experiments.civilization_capture import (
    CivilizationEvidenceRecorder,
    CivilizationPublicationReceipt,
)
from experiments.civilization_publication import (
    compose_civilization_boundary_from_source,
)
from persistence.civilization_filesystem import (
    create_civilization_publisher,
    create_civilization_reader,
)
from simulation.civilization_boundaries import CivilizationCaptureSink
from simulation.civilization_capture import CivilizationCaptureOptions
from simulation.civilization_models import CivilizationPublicationRef
from simulation.civilization_ports import CivilizationReadBudget

__all__ = [
    "CivilizationProducerOptions",
    "finalize_civilization_capture",
    "install_civilization_capture",
]

_LOG = logging.getLogger("research_runner.civilization_composition")


class _RunnerSink(Protocol):
    def set_civilization_boundary_sink(
        self, sink: CivilizationCaptureSink | None
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class CivilizationProducerOptions:
    root: Path
    capture: CivilizationCaptureOptions
    status_root: Path | None = None
    spool: object | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path):
            raise TypeError("root must be Path")
        if type(self.capture) is not CivilizationCaptureOptions:
            raise TypeError("capture must be CivilizationCaptureOptions")
        if self.status_root is not None and not isinstance(self.status_root, Path):
            raise TypeError("status_root must be Path or None")


def install_civilization_capture(
    runner: _RunnerSink, options: CivilizationProducerOptions
) -> CivilizationEvidenceRecorder:
    recorder = CivilizationEvidenceRecorder(
        options.capture,
        spool=options.spool,  # type: ignore[arg-type]
    )
    runner.set_civilization_boundary_sink(recorder)
    _LOG.debug("civilization_capture_installed active=%s", options.capture.enabled)
    return recorder


async def finalize_civilization_capture(
    arm: object,
    recorder: CivilizationEvidenceRecorder,
    options: CivilizationProducerOptions,
) -> CivilizationPublicationReceipt:
    runner_result = getattr(arm, "runner_result", None)
    run_id = getattr(runner_result, "run_id", None)
    if run_id is None:
        raise TypeError("arm.runner_result.run_id is required")
    source = recorder.source()
    ticks = source.boundary_ticks()
    if not ticks:
        status = CivilizationPublicationReceipt(
            str(run_id),
            0,
            None,
            0,
            "civilization_capture_unavailable",
        )
        _write_status(options.status_root, status)
        return status
    publication_id = (
        f"civilization-{run_id.value if hasattr(run_id, 'value') else run_id}"
    )
    publication: CivilizationPublicationRef | None = None
    published = 0
    try:
        publisher = create_civilization_publisher(options.root)
        for tick in ticks:
            boundary = compose_civilization_boundary_from_source(source, tick)
            await publisher.publish_boundary(publication_id, boundary)
            published += 1
        publication = await publisher.seal_catalogue(source.run_id, publication_id)
        # Read back the committed reference through the read-only capability.
        reader = create_civilization_reader(options.root)
        await reader.catalogue(
            source.run_id,
            after_boundary=None,
            publication=publication,
            budget=CivilizationReadBudget(),
        )
        status = CivilizationPublicationReceipt(
            source.run_id,
            ticks[-1],
            publication,
            published,
            None,
        )
    except Exception:
        _LOG.warning(
            "civilization_publication_failed run_id=%s reason_code=%s",
            source.run_id,
            "civilization_publication_failed",
        )
        status = CivilizationPublicationReceipt(
            source.run_id,
            ticks[-1],
            None,
            published,
            "civilization_publication_failed",
        )
    _write_status(options.status_root, status)
    return status


def _write_status(root: Path | None, receipt: CivilizationPublicationReceipt) -> None:
    if root is None:
        return
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"civilization-status-{receipt.run_id}.json"
    payload = json.dumps(
        {
            "run_id": receipt.run_id,
            "boundary_tick": receipt.boundary_tick,
            "publication": (
                None
                if receipt.publication is None
                else {
                    "publication_id": receipt.publication.publication_id,
                    "digest": receipt.publication.digest,
                    "policy_version": receipt.publication.policy_version,
                }
            ),
            "published_boundaries": receipt.published_boundaries,
            "scientific_status": "completed",
            "publication_status": (
                "ready" if receipt.failure_code is None else "failed"
            ),
            "failure_code": receipt.failure_code,
        },
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
