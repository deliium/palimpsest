"""Opt-in collapse-recovery capture over finalized runs.

Trusted experiments wrapper only. Never installs an arbiter, stop selector,
observer mode, runtime callback, or runner-config sibling. Disasters are not
required.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from analysis.collapse_recovery_evidence import (
    MAX_COLLAPSE_CUMULATIVE_FRAME_ROWS,
    MAX_COLLAPSE_CUMULATIVE_RAW_EVENTS,
    MAX_COLLAPSE_CUMULATIVE_RECEIPTS,
    MAX_COLLAPSE_HORIZON,
    MAX_COLLAPSE_REGIONS,
    MAX_COLLAPSE_ROSTER,
    CollapseBatch,
    CollapseBodyRow,
    CollapseEvidence,
    CollapseEvidenceError,
    CollapseFrame,
    CollapseReceiptKind,
    CollapseReceiptRow,
    CollapseSourceCoverage,
    OwnerLaneState,
    count_collapse_frame_rows,
    validate_collapse_evidence,
)
from analysis.collapse_recovery_report import (
    CollapseRecoveryReport,
    build_collapse_recovery_report,
)
from analysis.collapse_recovery_report_codec import encode_collapse_recovery_report
from simulation.resilience_evidence import (
    ResilienceBoundaryFacts,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RunnerAttemptStatus,
    RunnerStopReasonCode,
    is_failure_stop_reason,
)

__all__ = [
    "CollapseCaptureResult",
    "CollapseSealedEvidence",
    "frame_from_resilience_boundary",
    "project_collapse_batch_events",
    "run_with_collapse_recovery_capture",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.collapse_recovery_capture")

CaptureStatus = Literal[
    "disabled",
    "unsupported",
    "captured",
    "sealed",
    "aborted",
    "report_failed",
]


@dataclass(frozen=True, slots=True)
class CollapseSealedEvidence:
    """In-process sealed prefix; never auto-persisted."""

    evidence: CollapseEvidence


@dataclass(frozen=True, slots=True)
class CollapseCaptureResult:
    """Original runner result plus closed capture status and optional report."""

    result: object
    status: CaptureStatus
    report: CollapseRecoveryReport | None
    evidence: CollapseSealedEvidence | None = None
    reason_code: str | None = None


def _location_regions(config: object) -> dict[str, str]:
    regions = getattr(config, "regions_migration", None)
    if regions is None:
        return {}
    memberships = getattr(regions, "location_regions", ())
    mapping: dict[str, str] = {}
    for row in memberships:
        location_id = getattr(row, "location_id", None)
        region_id = getattr(row, "region_id", None)
        if location_id is None or region_id is None:
            continue
        location_value = getattr(location_id, "value", location_id)
        region_value = getattr(region_id, "value", region_id)
        mapping[str(location_value)] = str(region_value)
    return mapping


def _configured_region_ids(location_regions: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(sorted(set(location_regions.values())))


def _production_enabled(config: object) -> bool:
    agents = getattr(config, "agents", ())
    if not agents:
        return False
    cognition = getattr(agents[0], "cognition", None)
    if cognition is None:
        return False
    catalog = getattr(cognition, "production_catalog", None)
    if catalog is None:
        return False
    count = getattr(catalog, "recipe_count", 0)
    return type(count) is int and not isinstance(count, bool) and count > 0


def _source_coverage(
    config: object, *, infrastructure_channel: OwnerLaneState
) -> CollapseSourceCoverage:
    return CollapseSourceCoverage(
        regions_migration=getattr(config, "regions_migration", None) is not None,
        resource_exchange=getattr(config, "resource_exchange_profile", None)
        is not None,
        production=_production_enabled(config),
        infrastructure=infrastructure_channel,
    )


def _capture_supported(runner: SimulationRunner) -> tuple[bool, str | None]:
    config = runner.config
    max_ticks = config.stop_policy.max_ticks
    if (
        type(max_ticks) is not int
        or isinstance(max_ticks, bool)
        or max_ticks < 1
        or max_ticks > MAX_COLLAPSE_HORIZON
    ):
        return False, "horizon_unsupported"
    if runner.ticks_committed != 0 or runner.engine.tick.value != 0:
        return False, "pre_start_required"
    if runner.engine.history_length != 0:
        return False, "history_not_empty"
    if len(runner.engine.ordered_registrations) > MAX_COLLAPSE_ROSTER:
        return False, "roster_overflow"
    location_regions = _location_regions(config)
    if len(_configured_region_ids(location_regions)) > MAX_COLLAPSE_REGIONS:
        return False, "region_overflow"
    return True, None


def frame_from_resilience_boundary(facts: ResilienceBoundaryFacts) -> CollapseFrame:
    """Drop stock rows and held-item counts from a resilience boundary export."""

    bodies = tuple(
        CollapseBodyRow(
            body_id=row.body_id,
            agent_id=row.agent_id,
            living=row.living,
            region_id=row.region_id,
        )
        for row in facts.bodies
    )
    return CollapseFrame(
        run_id=facts.run_id,
        config_fingerprint=facts.config_fingerprint,
        tick=facts.boundary_tick,
        revision=facts.revision,
        body_projection_hash=facts.body_projection_hash,
        history_length=facts.history_length,
        infrastructure_channel=facts.infrastructure_channel,
        bodies=bodies,
        infrastructure=facts.infrastructure,
        owners=facts.owners,
    )


def _site_from_occurrence(
    occurrence: object | None,
    *,
    location_regions: Mapping[str, str],
) -> tuple[str | None, str | None, bool]:
    """Return (site_location_id, site_region_id, unassigned)."""

    if occurrence is None:
        return None, None, False
    origin = getattr(occurrence, "origin_location_id", None)
    destination = getattr(occurrence, "destination_location_id", None)
    if origin is None:
        return None, None, False
    origin_value = getattr(origin, "value", origin)
    if origin_value is None:
        return None, None, False
    origin_id = str(origin_value)
    if destination is not None:
        destination_value = getattr(destination, "value", destination)
        if destination_value is not None and str(destination_value) != origin_id:
            return None, None, True
    region_id = location_regions.get(origin_id)
    return origin_id, region_id, False


def _resolve_body(
    candidate: object | None,
    *,
    registered: Mapping[str, str],
) -> tuple[str | None, bool]:
    if candidate is None:
        return None, True
    value = getattr(candidate, "value", candidate)
    if value is None:
        return None, True
    body_id = str(value)
    if body_id not in registered:
        return None, True
    return body_id, False


def _sort_key(row: CollapseReceiptRow) -> tuple[int, str, str, str]:
    return (
        row.sequence,
        row.event_id,
        row.kind.value,
        "" if row.participant_body_id is None else row.participant_body_id,
    )


def project_collapse_batch_events(
    events: Sequence[object],
    *,
    tick: int,
    resulting_revision: int,
    registered_bodies: Mapping[str, str],
    location_regions: Mapping[str, str],
) -> CollapseBatch:
    """Project allowlisted committed events from one tick batch."""

    from world.events import (
        Asked,
        Attacked,
        Died,
        ExchangeCompleted,
        Fed,
        Helped,
        ItemCrafted,
        JourneyArrived,
        ResourceHarvested,
        Talked,
        Told,
        WorldEvent,
    )

    receipts: list[CollapseReceiptRow] = []
    for event in events:
        if type(event) is not WorldEvent:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if event.tick != tick:
            raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
        event_revision = event.resulting_revision.value
        if event_revision != resulting_revision:
            raise CollapseEvidenceError("collapse_evidence_revision_gap")
        details = event.details
        event_id = event.event_id.value
        sequence = event.sequence
        occurrence = event.occurrence

        if type(details) is Died:
            body_id, gap = _resolve_body(details.body_id, registered=registered_bodies)
            site_location, site_region, unassigned = _site_from_occurrence(
                occurrence, location_regions=location_regions
            )
            receipts.append(
                CollapseReceiptRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=CollapseReceiptKind.DEATH,
                    participant_body_id=body_id,
                    counterpart_body_id=None,
                    origin_location_id=None,
                    destination_location_id=None,
                    origin_region_id=None,
                    destination_region_id=None,
                    site_location_id=None if unassigned else site_location,
                    site_region_id=None if unassigned else site_region,
                    attribution_gap=gap or unassigned,
                )
            )
        elif type(details) is JourneyArrived:
            origin_location = details.origin_location_id.value
            destination_location = details.destination_location_id.value
            origin_region = location_regions.get(origin_location)
            destination_region = location_regions.get(destination_location)
            if (
                origin_region is not None
                and destination_region is not None
                and origin_region == destination_region
            ):
                continue
            for participant in details.participant_body_ids:
                body_id, gap = _resolve_body(participant, registered=registered_bodies)
                receipts.append(
                    CollapseReceiptRow(
                        event_id=event_id,
                        tick=tick,
                        sequence=sequence,
                        kind=CollapseReceiptKind.JOURNEY_ARRIVAL,
                        participant_body_id=body_id,
                        counterpart_body_id=None,
                        origin_location_id=origin_location,
                        destination_location_id=destination_location,
                        origin_region_id=origin_region,
                        destination_region_id=destination_region,
                        site_location_id=None,
                        site_region_id=None,
                        attribution_gap=gap
                        or origin_region is None
                        or destination_region is None,
                    )
                )
        elif type(details) is ExchangeCompleted:
            site_location, site_region, unassigned = _site_from_occurrence(
                occurrence, location_regions=location_regions
            )
            actor_id, actor_gap = _resolve_body(
                details.actor_id, registered=registered_bodies
            )
            counter_id, counter_gap = _resolve_body(
                details.counterparty_id, registered=registered_bodies
            )
            gap = actor_gap or counter_gap or unassigned
            receipts.append(
                CollapseReceiptRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=CollapseReceiptKind.EXCHANGE,
                    participant_body_id=actor_id,
                    counterpart_body_id=counter_id,
                    origin_location_id=None,
                    destination_location_id=None,
                    origin_region_id=None,
                    destination_region_id=None,
                    site_location_id=None if unassigned else site_location,
                    site_region_id=None if unassigned else site_region,
                    attribution_gap=gap,
                )
            )
            receipts.append(
                CollapseReceiptRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=CollapseReceiptKind.EXCHANGE_CONTACT,
                    participant_body_id=actor_id,
                    counterpart_body_id=counter_id,
                    origin_location_id=None,
                    destination_location_id=None,
                    origin_region_id=None,
                    destination_region_id=None,
                    site_location_id=None if unassigned else site_location,
                    site_region_id=None if unassigned else site_region,
                    attribution_gap=gap,
                )
            )
        elif type(details) is ResourceHarvested:
            if details.success is not True:
                continue
            site_location, site_region, unassigned = _site_from_occurrence(
                occurrence, location_regions=location_regions
            )
            actor_id, gap = _resolve_body(event.actor_id, registered=registered_bodies)
            receipts.append(
                CollapseReceiptRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=CollapseReceiptKind.HARVEST,
                    participant_body_id=actor_id,
                    counterpart_body_id=None,
                    origin_location_id=None,
                    destination_location_id=None,
                    origin_region_id=None,
                    destination_region_id=None,
                    site_location_id=None if unassigned else site_location,
                    site_region_id=None if unassigned else site_region,
                    attribution_gap=gap or unassigned,
                )
            )
        elif type(details) is ItemCrafted:
            if details.success is not True:
                continue
            site_location, site_region, unassigned = _site_from_occurrence(
                occurrence, location_regions=location_regions
            )
            actor_id, gap = _resolve_body(event.actor_id, registered=registered_bodies)
            receipts.append(
                CollapseReceiptRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=CollapseReceiptKind.CRAFT,
                    participant_body_id=actor_id,
                    counterpart_body_id=None,
                    origin_location_id=None,
                    destination_location_id=None,
                    origin_region_id=None,
                    destination_region_id=None,
                    site_location_id=None if unassigned else site_location,
                    site_region_id=None if unassigned else site_region,
                    attribution_gap=gap or unassigned,
                )
            )
        elif type(details) is Attacked:
            site_location, site_region, unassigned = _site_from_occurrence(
                occurrence, location_regions=location_regions
            )
            actor_id, actor_gap = _resolve_body(
                event.actor_id, registered=registered_bodies
            )
            target_id, target_gap = _resolve_body(
                details.target_id, registered=registered_bodies
            )
            receipts.append(
                CollapseReceiptRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=CollapseReceiptKind.ATTACK,
                    participant_body_id=actor_id,
                    counterpart_body_id=target_id,
                    origin_location_id=None,
                    destination_location_id=None,
                    origin_region_id=None,
                    destination_region_id=None,
                    site_location_id=None if unassigned else site_location,
                    site_region_id=None if unassigned else site_region,
                    attribution_gap=actor_gap or target_gap or unassigned,
                )
            )
        elif isinstance(details, (Talked, Asked, Told)):
            recipient = details.recipient_id
            private_ids: tuple[str, ...] = ()
            if occurrence is not None:
                private_ids = tuple(
                    str(getattr(item, "value", item))
                    for item in getattr(occurrence, "private_recipient_ids", ())
                )
            if recipient.value not in set(private_ids):
                continue
            speaker_id, speaker_gap = _resolve_body(
                event.actor_id, registered=registered_bodies
            )
            listener_id, listener_gap = _resolve_body(
                recipient, registered=registered_bodies
            )
            receipts.append(
                CollapseReceiptRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=CollapseReceiptKind.SPEECH_CONTACT,
                    participant_body_id=speaker_id,
                    counterpart_body_id=listener_id,
                    origin_location_id=None,
                    destination_location_id=None,
                    origin_region_id=None,
                    destination_region_id=None,
                    site_location_id=None,
                    site_region_id=None,
                    attribution_gap=speaker_gap or listener_gap,
                )
            )
        elif type(details) is Helped:
            actor_id, actor_gap = _resolve_body(
                event.actor_id, registered=registered_bodies
            )
            target_id, target_gap = _resolve_body(
                details.target_id, registered=registered_bodies
            )
            receipts.append(
                CollapseReceiptRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=CollapseReceiptKind.HELP_CONTACT,
                    participant_body_id=actor_id,
                    counterpart_body_id=target_id,
                    origin_location_id=None,
                    destination_location_id=None,
                    origin_region_id=None,
                    destination_region_id=None,
                    site_location_id=None,
                    site_region_id=None,
                    attribution_gap=actor_gap or target_gap,
                )
            )
        elif type(details) is Fed:
            actor_id, actor_gap = _resolve_body(
                event.actor_id, registered=registered_bodies
            )
            target_id, target_gap = _resolve_body(
                details.target_id, registered=registered_bodies
            )
            receipts.append(
                CollapseReceiptRow(
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=CollapseReceiptKind.FEED_CONTACT,
                    participant_body_id=actor_id,
                    counterpart_body_id=target_id,
                    origin_location_id=None,
                    destination_location_id=None,
                    origin_region_id=None,
                    destination_region_id=None,
                    site_location_id=None,
                    site_region_id=None,
                    attribution_gap=actor_gap or target_gap,
                )
            )

    ordered = tuple(sorted(receipts, key=_sort_key))
    _LOG.debug(
        "collapse_batch_projected tick=%s raw_events=%s receipts=%s",
        tick,
        len(events),
        len(ordered),
    )
    return CollapseBatch(
        tick=tick,
        resulting_revision=resulting_revision,
        raw_event_count=len(events),
        receipts=ordered,
    )


class _Accumulator:
    """Bounded in-process prefix; seals before first overflow/mismatch."""

    def __init__(
        self,
        *,
        run_id: str,
        config_fingerprint: str,
        region_ids: tuple[str, ...],
        location_regions: Mapping[str, str],
        source_coverage: CollapseSourceCoverage,
    ) -> None:
        self.run_id = run_id
        self.config_fingerprint = config_fingerprint
        self.region_ids = region_ids
        self.location_regions = dict(location_regions)
        self.source_coverage = source_coverage
        self.frames: list[CollapseFrame] = []
        self.batches: list[CollapseBatch] = []
        self._event_count = 0
        self._receipt_count = 0
        self._row_count = 0
        self._prev_history_length = 0
        self.seal_reason: str | None = None
        self._seal_warned = False

    @property
    def sealed(self) -> bool:
        return self.seal_reason is not None

    def seal(self, reason: str, *, stage: str) -> None:
        if self.seal_reason is not None:
            return
        self.seal_reason = reason
        if not self._seal_warned:
            self._seal_warned = True
            _LOG.warning(
                "collapse_capture_sealed reason=%s stage=%s run_id=%s "
                "frames=%s events=%s",
                reason,
                stage,
                self.run_id,
                len(self.frames),
                self._event_count,
            )

    def accept_frame(
        self,
        frame: CollapseFrame,
        *,
        batch: CollapseBatch | None,
    ) -> bool:
        if self.sealed:
            return False
        if frame.run_id != self.run_id:
            self.seal("run_mismatch", stage="frame")
            return False
        if self.frames and frame.tick != self.frames[-1].tick + 1:
            if frame.tick == self.frames[-1].tick:
                return True
            self.seal("capture_gap", stage="frame")
            return False
        incoming_rows = count_collapse_frame_rows(
            bodies=frame.bodies,
            infrastructure=frame.infrastructure,
            owners=frame.owners,
        )
        incoming_events = 0 if batch is None else batch.raw_event_count
        incoming_receipts = 0 if batch is None else len(batch.receipts)
        if (
            self._event_count + incoming_events > MAX_COLLAPSE_CUMULATIVE_RAW_EVENTS
            or self._receipt_count + incoming_receipts
            > MAX_COLLAPSE_CUMULATIVE_RECEIPTS
            or self._row_count + incoming_rows > MAX_COLLAPSE_CUMULATIVE_FRAME_ROWS
        ):
            self.seal("capture_cap", stage="frame")
            return False
        if batch is not None:
            expected_history = self._prev_history_length + batch.raw_event_count
            if frame.history_length != expected_history:
                self.seal("history_append_mismatch", stage="frame")
                return False
            if batch.tick != frame.tick - 1:
                self.seal("batch_tick_mismatch", stage="frame")
                return False
            if batch.resulting_revision != frame.revision:
                self.seal("batch_revision_mismatch", stage="frame")
                return False
            self.batches.append(batch)
            self._event_count += batch.raw_event_count
            self._receipt_count += len(batch.receipts)
            self._prev_history_length = frame.history_length
        elif frame.tick == 0:
            if frame.history_length != 0:
                self.seal("history_append_mismatch", stage="baseline")
                return False
            self._prev_history_length = 0
        else:
            self.seal("batch_required", stage="frame")
            return False
        self.frames.append(frame)
        self._row_count += incoming_rows
        _LOG.debug(
            "collapse_boundary_accepted run_id=%s tick=%s row_count=%s",
            self.run_id,
            frame.tick,
            incoming_rows,
        )
        return True

    def build_evidence(self, *, committed_through: int) -> CollapseEvidence:
        captured_through = self.frames[-1].tick if self.frames else 0
        evidence = CollapseEvidence(
            run_id=self.run_id,
            config_fingerprint=self.config_fingerprint,
            captured_through=captured_through,
            committed_through=committed_through,
            seal_reason=self.seal_reason,
            region_ids=self.region_ids,
            location_regions=self.location_regions,
            source_coverage=self.source_coverage,
            frames=tuple(self.frames),
            batches=tuple(self.batches),
        )
        validate_collapse_evidence(evidence)
        return evidence


async def _sample_boundary(
    runner: SimulationRunner,
    *,
    accumulator: _Accumulator,
    expect_batch: bool,
) -> bool:
    resilience_frame = await runner.export_resilience_boundary()
    if type(resilience_frame) is not ResilienceBoundaryFacts:
        raise TypeError(
            "export_resilience_boundary must return ResilienceBoundaryFacts"
        )
    frame = frame_from_resilience_boundary(resilience_frame)
    registered = {row.body_id: row.agent_id for row in frame.bodies}
    batch: CollapseBatch | None = None
    if expect_batch:
        tick_result = runner.engine.last_tick_result
        if tick_result is None:
            accumulator.seal("batch_missing", stage="sample")
            return False
        if tick_result.tick.value + 1 != frame.tick:
            accumulator.seal("batch_tick_mismatch", stage="sample")
            return False
        if tick_result.resulting_revision.value != frame.revision:
            accumulator.seal("batch_revision_mismatch", stage="sample")
            return False
        if runner.ticks_committed != frame.tick:
            accumulator.seal("batch_tick_mismatch", stage="committed")
            return False
        remaining_raw = MAX_COLLAPSE_CUMULATIVE_RAW_EVENTS - accumulator._event_count
        if len(tick_result.events) > remaining_raw:
            accumulator.seal("capture_cap", stage="batch_budget")
            return False
        world_events = []
        seen_ids: set[str] = set()
        for record in tick_result.events:
            event = record.event
            if event.run_id != accumulator.run_id:
                accumulator.seal("run_mismatch", stage="event")
                return False
            if event.tick != tick_result.tick.value:
                accumulator.seal("batch_tick_mismatch", stage="event")
                return False
            if event.resulting_revision.value != tick_result.resulting_revision.value:
                accumulator.seal("batch_revision_mismatch", stage="event")
                return False
            if event.event_id.value in seen_ids:
                accumulator.seal("duplicate_event", stage="event")
                return False
            seen_ids.add(event.event_id.value)
            world_events.append(event)
        projected = project_collapse_batch_events(
            world_events,
            tick=tick_result.tick.value,
            resulting_revision=tick_result.resulting_revision.value,
            registered_bodies=registered,
            location_regions=accumulator.location_regions,
        )
        # Incremental receipt budget as multi-participant arrivals expand.
        if (
            accumulator._receipt_count + len(projected.receipts)
            > MAX_COLLAPSE_CUMULATIVE_RECEIPTS
        ):
            accumulator.seal("capture_cap", stage="receipt_budget")
            return False
        batch = projected
    return accumulator.accept_frame(frame, batch=batch)


async def run_with_collapse_recovery_capture(
    runner: SimulationRunner,
    *,
    capture: bool = False,
) -> CollapseCaptureResult:
    """Run once with optional finalized-boundary collapse-recovery capture."""

    from simulation.runner_serialization import runner_config_fingerprint

    if type(capture) is not bool:
        raise TypeError("capture must be an exact bool")

    if not capture:
        result = await runner.run()
        _LOG.info(
            "collapse_capture_disabled run_id=%s",
            result.run_id.value,
        )
        return CollapseCaptureResult(
            result=result,
            status="disabled",
            report=None,
            evidence=None,
            reason_code="capture_disabled",
        )

    supported, reason = _capture_supported(runner)
    if not supported:
        result = await runner.run()
        _LOG.info(
            "collapse_capture_unsupported run_id=%s reason=%s",
            result.run_id.value,
            reason,
        )
        return CollapseCaptureResult(
            result=result,
            status="unsupported",
            report=None,
            evidence=None,
            reason_code=reason,
        )

    await runner.initialize_finalized_boundary()
    location_regions = _location_regions(runner.config)
    region_ids = _configured_region_ids(location_regions)
    # Infrastructure availability is refreshed from the first accepted frame.
    provisional_coverage = _source_coverage(
        runner.config, infrastructure_channel=OwnerLaneState.OFF
    )
    accumulator = _Accumulator(
        run_id=runner.run_id.value,
        config_fingerprint=runner_config_fingerprint(runner.config),
        region_ids=region_ids,
        location_regions=location_regions,
        source_coverage=provisional_coverage,
    )
    status: CaptureStatus = "captured"
    aborted = False

    try:
        await _sample_boundary(runner, accumulator=accumulator, expect_batch=False)
        if accumulator.frames:
            accumulator.source_coverage = _source_coverage(
                runner.config,
                infrastructure_channel=accumulator.frames[0].infrastructure_channel,
            )
    except Exception:
        accumulator.seal("capture_failed", stage="baseline")
        status = "sealed"

    stop_reason: RunnerStopReasonCode | None = None
    while stop_reason is None:
        receipt = await runner.run_tick()
        if receipt.status is RunnerAttemptStatus.ABORTED:
            aborted = True
            stop_reason = (
                receipt.stop_reason
                if receipt.stop_reason is not None
                else RunnerStopReasonCode.AUTHORITY_FAILURE
            )
            break
        stop_reason = receipt.stop_reason
        if (
            stop_reason is None
            and runner.ticks_committed >= runner.config.stop_policy.max_ticks
        ):
            stop_reason = RunnerStopReasonCode.MAX_TICKS
        if accumulator.sealed or stop_reason is not None:
            continue
        try:
            accepted = await _sample_boundary(
                runner, accumulator=accumulator, expect_batch=True
            )
            if not accepted:
                status = "sealed"
        except Exception:
            accumulator.seal("capture_failed", stage="tick")
            status = "sealed"

    result = await runner.finish_run(stop_reason)
    result_stop = getattr(result, "stop_reason", None)
    if aborted or (
        type(result_stop) is RunnerStopReasonCode
        and is_failure_stop_reason(result_stop)
    ):
        _LOG.info(
            "collapse_capture_aborted run_id=%s frames=%s",
            result.run_id.value,
            len(accumulator.frames),
        )
        return CollapseCaptureResult(
            result=result,
            status="aborted",
            report=None,
            evidence=None,
            reason_code="scientific_abort",
        )

    if not accumulator.sealed:
        try:
            if (
                not accumulator.frames
                or accumulator.frames[-1].tick != result.ticks_committed
            ):
                accepted = await _sample_boundary(
                    runner, accumulator=accumulator, expect_batch=True
                )
                if not accepted:
                    status = "sealed"
        except Exception:
            accumulator.seal("capture_failed", stage="terminal")
            status = "sealed"

    try:
        evidence = accumulator.build_evidence(committed_through=result.ticks_committed)
    except Exception:
        accumulator.seal("evidence_invalid", stage="seal")
        _LOG.warning(
            "collapse_evidence_seal_failed run_id=%s",
            result.run_id.value,
        )
        return CollapseCaptureResult(
            result=result,
            status="sealed",
            report=None,
            evidence=None,
            reason_code=accumulator.seal_reason or "evidence_invalid",
        )

    if accumulator.sealed:
        status = "sealed"

    sealed = CollapseSealedEvidence(evidence=evidence)
    try:
        report = build_collapse_recovery_report(
            evidence,
            capture_reason=accumulator.seal_reason,
        )
        encode_collapse_recovery_report(report)
    except Exception:
        _LOG.warning(
            "collapse_report_failed run_id=%s",
            result.run_id.value,
        )
        return CollapseCaptureResult(
            result=result,
            status="report_failed",
            report=None,
            evidence=sealed,
            reason_code="report_failed",
        )
    _LOG.info(
        "collapse_capture_complete run_id=%s status=%s frames=%s events=%s "
        "receipts=%s windows=%s episodes=%s",
        result.run_id.value,
        status,
        len(evidence.frames),
        sum(batch.raw_event_count for batch in evidence.batches),
        sum(len(batch.receipts) for batch in evidence.batches),
        len(report.windows),
        len(report.episodes),
    )
    return CollapseCaptureResult(
        result=result,
        status=status,
        report=report,
        evidence=sealed,
        reason_code=accumulator.seal_reason,
    )
