"""Trusted research-runner composition for optional lineage capture."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from analysis.institution_lineage import compute_institution_lineage
from analysis.institutional_decay import institution_decay_rows_from_ledgers
from analysis.institutional_decay_metrics import encode_institution_lineage_graph
from experiments.lineage_publication import (
    CompletedLineageHarvest,
    LineageCaptureStatusDocument,
    publish_completed_lineage,
)
from persistence.lineage_filesystem import (
    create_lineage_publisher,
    create_lineage_reader,
)
from simulation.lineage_capture import LineageCaptureOptions, LineageCaptureSession
from simulation.lineage_ports import NarrativeVariantSource

__all__ = [
    "LineageProducerOptions",
    "build_completed_lineage_harvest",
    "create_lineage_capture",
    "finalize_lineage_capture",
    "install_lineage_capture",
]


class _RunnerSink(Protocol):
    def set_lineage_boundary_sink(self, sink: object) -> None: ...


_LOG = logging.getLogger("research_runner.lineage_composition")


@dataclass(frozen=True, slots=True)
class LineageProducerOptions:
    root: Path
    capture: LineageCaptureOptions
    artifact_root: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path):
            raise TypeError("root must be Path")
        if type(self.capture) is not LineageCaptureOptions:
            raise TypeError("capture must be LineageCaptureOptions")
        if self.artifact_root is not None and not isinstance(self.artifact_root, Path):
            raise TypeError("artifact_root must be Path or None")


def create_lineage_capture(
    options: LineageProducerOptions,
) -> LineageCaptureSession:
    """Create the neutral session over separate filesystem capabilities."""
    reader = create_lineage_reader(options.root)
    publisher = create_lineage_publisher(
        options.root,
        max_publications=options.capture.max_publications,
        max_artifact_bytes=options.capture.max_artifact_bytes,
    )
    return LineageCaptureSession(
        reader=reader,
        publisher=publisher,
        options=options.capture,
    )


def install_lineage_capture(
    runner: _RunnerSink, options: LineageProducerOptions
) -> LineageCaptureSession:
    """Create the session first, then bind its sink as the final action."""
    session = create_lineage_capture(options)
    runner.set_lineage_boundary_sink(session)
    _LOG.debug("lineage_capture_installed active=%s", session.status.active)
    return session


def build_completed_lineage_harvest(
    arm: object,
    *,
    boundary_tick: int,
    source_revision: str,
) -> CompletedLineageHarvest:
    """Build the detached analytical harvest from one completed arm."""
    runner_result = getattr(arm, "runner_result", None)
    if runner_result is None:
        raise TypeError("arm.runner_result is required")
    run_id = getattr(runner_result, "run_id", None)
    if run_id is None:
        raise TypeError("arm.runner_result.run_id is required")
    return CompletedLineageHarvest(
        run_id=run_id,
        boundary_tick=boundary_tick,
        source_revision=source_revision,
        practical_knowledge_audits=tuple(
            getattr(runner_result, "practical_knowledge_audits", ()) or ()
        ),
        narrative_variants=_narrative_variants(runner_result),
        institution_payload=_institution_payload(runner_result, boundary_tick),
    )


def _narrative_variants(
    runner_result: object,
) -> tuple[tuple[str, NarrativeVariantSource], ...]:
    variants: list[tuple[str, NarrativeVariantSource]] = []
    for ledger in getattr(runner_result, "cultural_narrative_ledgers", ()) or ():
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        if not isinstance(owner, str):
            continue
        for variant in getattr(ledger, "variants", ()) or ():
            source_loss = getattr(variant, "source_loss", None)
            variants.append(
                (
                    owner,
                    NarrativeVariantSource(
                        variant_id=variant.variant_id,
                        origin=variant.origin.value,
                        status=variant.status.value,
                        strength=variant.strength,
                        first_tick=variant.first_tick,
                        last_tick=variant.last_tick,
                        repetition_count=variant.repetition_count,
                        mutation_generation=variant.mutation_generation,
                        parent_variant_ids=tuple(variant.parent_variant_ids),
                        merged_into_id=variant.merged_into_id,
                        competing_variant_ids=tuple(
                            variant.competing_variant_ids
                        ),
                        source_event_id=variant.source_event_id,
                        source_memory_id=variant.source_memory_id,
                        reconstruction_id=variant.reconstruction_id,
                        transmission_root_id=variant.transmission_root_id,
                        source_loss_state=(
                            "unknown"
                            if source_loss is None
                            else source_loss.state.value
                        ),
                        source_loss_reason=(
                            None if source_loss is None else source_loss.reason.value
                        ),
                        source_loss_tick=(
                            None if source_loss is None else source_loss.tick
                        ),
                        known_witness_count=(
                            0
                            if source_loss is None
                            else source_loss.known_witness_count
                        ),
                        dead_witness_count=(
                            0 if source_loss is None else source_loss.dead_witness_count
                        ),
                        record_backed=(
                            False if source_loss is None else source_loss.record_backed
                        ),
                    ),
                )
            )
    return tuple(variants)


def _institution_payload(
    runner_result: object, boundary_tick: int
) -> str | None:
    ledgers = tuple(
        getattr(runner_result, "institutional_decay_ledgers", ()) or ()
    )
    if not ledgers:
        return None
    rows = institution_decay_rows_from_ledgers(ledgers)
    if not rows:
        return None
    lineage = compute_institution_lineage(rows, as_of_tick=boundary_tick)
    return encode_institution_lineage_graph(lineage)


async def finalize_lineage_capture(
    arm: object,
    session: LineageCaptureSession,
    options: LineageProducerOptions,
) -> LineageCaptureStatusDocument:
    """Publish detached analytical families after scientific completion."""
    receipts = session.receipts
    receipt_boundaries = [item.boundary_tick for item in receipts]
    runner_result = getattr(arm, "runner_result", None)
    if runner_result is None:
        raise TypeError("arm.runner_result is required")
    if not receipt_boundaries:
        status = LineageCaptureStatusDocument(
            run_id=runner_result.run_id,
            boundary_tick=0,
            published=(),
            unavailable=(
                ("mentorship", "lineage_capture_unavailable"),
                ("knowledge", "lineage_capture_unavailable"),
                ("technology", "lineage_capture_unavailable"),
                ("narrative", "lineage_capture_unavailable"),
                ("institution", "lineage_capture_unavailable"),
            ),
            receipt_count=0,
        )
        session_status = session.status
        if session_status.failure_code is not None:
            status = replace(status, failure_code=session_status.failure_code)
        if options.artifact_root is not None:
            _write_status_document(options.artifact_root, status)
        return status
    boundary = max(receipt_boundaries)
    harvest = build_completed_lineage_harvest(
        arm,
        boundary_tick=boundary,
        source_revision=f"captured-boundary-{boundary}",
    )
    publisher = create_lineage_publisher(
        options.root,
        max_publications=options.capture.max_publications,
        max_artifact_bytes=options.capture.max_artifact_bytes,
    )
    try:
        status = await publish_completed_lineage(
            harvest,
            receipts=receipts,
            reader=create_lineage_reader(options.root),
            options=options.capture,
            publisher=publisher,
        )
    except Exception:
        _LOG.warning(
            "lineage_finalization_failed run_id=%s reason_code=%s",
            status_run_id(harvest),
            "lineage_finalization_failed",
        )
        status = LineageCaptureStatusDocument(
            run_id=harvest.run_id,
            boundary_tick=boundary,
            published=(),
            unavailable=(("analytical", "lineage_finalization_failed"),),
            receipt_count=len(receipts),
            failure_code="lineage_finalization_failed",
        )
    session_status = session.status
    if session_status.failure_code is not None:
        status = replace(status, failure_code=session_status.failure_code)
    if options.artifact_root is not None:
        _write_status_document(options.artifact_root, status)
    return status


def status_run_id(harvest: CompletedLineageHarvest) -> str:
    return harvest.run_id.value


def _write_status_document(
    artifact_root: Path, status: LineageCaptureStatusDocument
) -> None:
    artifact_root.mkdir(parents=True, exist_ok=True)
    target = artifact_root / f"lineage-capture-status-{status.run_id.value}.json"
    payload = json.dumps(
        status.payload(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
