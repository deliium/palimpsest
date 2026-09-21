"""Read-only social transmission and cross-hop distortion analysis.

Joins communication events with communicated memory traces after the fact.
Never feeds results back into live cognition. Domain payloads stay out of logs.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from typing import Final

from analysis.contracts import MemoryEvidenceSource, ObjectiveEventSource
from analysis.models import (
    SOCIAL_TRANSMISSION_METRIC_VERSION,
    SocialTransmissionReport,
    TransmissionDistortion,
    TransmissionHopRecord,
)
from memory.models import MemorySourceKind, MemoryTrace
from world.events import Asked, Talked, Told, WorldEvent
from world.identifiers import require_stable_id

__all__ = [
    "SOCIAL_TRANSMISSION_METRIC_VERSION",
    "SocialTransmissionAnalysisService",
    "build_social_transmission_report",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_transmission")
_COMM_DETAILS = (Talked, Asked, Told)


def _action_kind(details: object) -> str:
    if type(details) is Talked:
        return "talk"
    if type(details) is Asked:
        return "ask"
    if type(details) is Told:
        return "tell"
    raise TypeError("unsupported communication details")


def _communication_events(events: Sequence[WorldEvent]) -> tuple[WorldEvent, ...]:
    return tuple(
        event for event in events if type(event.details) in _COMM_DETAILS
    )


def _hop_from_event(event: WorldEvent) -> TransmissionHopRecord:
    details = event.details
    assert type(details) in _COMM_DETAILS
    declared = details.utterance.declared
    content = details.utterance.content
    root = (
        declared.communication_id.value
        if declared.hop_count == 0
        else (
            declared.parent_communication_id.value
            if declared.parent_communication_id is not None
            and declared.hop_count == 1
            else declared.communication_id.value
        )
    )
    return TransmissionHopRecord(
        communication_id=declared.communication_id.value,
        event_id=event.event_id.value,
        speaker_id=declared.immediate_source_id.value,
        listener_id=None if event.target_id is None else event.target_id.value,
        action_kind=_action_kind(details),
        hop_count=declared.hop_count,
        tick=event.tick,
        sender_confidence=declared.sender_confidence,
        receiver_confidence=None,
        transmission_root_id=root,
        concept_count=len(content.concepts),
        relation_count=len(content.relations),
    )


def _hop_from_trace(trace: MemoryTrace) -> TransmissionHopRecord | None:
    meta = trace.provenance.transmission
    if meta is None or trace.provenance.kind is not MemorySourceKind.COMMUNICATED:
        return None
    return TransmissionHopRecord(
        communication_id=meta.communication_id,
        event_id=(
            None
            if trace.provenance.observed_source_id is None
            else trace.provenance.observed_source_id.value
        ),
        speaker_id=(
            "unknown"
            if trace.provenance.speaker_id is None
            else trace.provenance.speaker_id.value
        ),
        listener_id=trace.owner_id.value,
        action_kind=meta.action_kind,
        hop_count=meta.hop_count,
        tick=trace.source_tick,
        sender_confidence=meta.sender_confidence,
        receiver_confidence=meta.receiver_confidence,
        transmission_root_id=meta.transmission_root_id or meta.communication_id,
        concept_count=len(
            [
                c
                for c in trace.concepts
                if c.mention_id.value.startswith("c-")
                and not c.mention_id.value.startswith("c-rel-")
            ]
        ),
        relation_count=len(trace.relations),
    )


def _distortions(
    hops: Sequence[TransmissionHopRecord],
) -> tuple[TransmissionDistortion, ...]:
    by_id = {hop.communication_id: hop for hop in hops}
    # Parent is prior hop when hop_count increases along shared root.
    by_root: dict[str, list[TransmissionHopRecord]] = defaultdict(list)
    for hop in hops:
        by_root[hop.transmission_root_id].append(hop)
    results: list[TransmissionDistortion] = []
    for root_hops in by_root.values():
        ordered = sorted(root_hops, key=lambda item: (item.hop_count, item.tick))
        for index in range(1, len(ordered)):
            prior = ordered[index - 1]
            current = ordered[index]
            if current.hop_count <= prior.hop_count:
                continue
            concepts_added = max(0, current.concept_count - prior.concept_count)
            concepts_removed = max(0, prior.concept_count - current.concept_count)
            relations_added = max(0, current.relation_count - prior.relation_count)
            relations_removed = max(0, prior.relation_count - current.relation_count)
            results.append(
                TransmissionDistortion(
                    from_communication_id=prior.communication_id,
                    to_communication_id=current.communication_id,
                    concepts_added=concepts_added,
                    concepts_removed=concepts_removed,
                    relations_added=relations_added,
                    relations_removed=relations_removed,
                    cumulative_change=(
                        concepts_added
                        + concepts_removed
                        + relations_added
                        + relations_removed
                    ),
                )
            )
    results.sort(
        key=lambda item: (item.from_communication_id, item.to_communication_id)
    )
    _ = by_id
    return tuple(results)


def build_social_transmission_report(
    *,
    experiment_id: str,
    run_id: str,
    events: Sequence[WorldEvent],
    traces: Sequence[MemoryTrace],
    transmission_root_id: str | None = None,
) -> SocialTransmissionReport:
    """Build a transmission report from detached events and communicated traces."""
    experiment_id = require_stable_id("experiment_id", experiment_id)
    run_id = require_stable_id("run_id", run_id)
    hops: list[TransmissionHopRecord] = []
    for event in _communication_events(events):
        hops.append(_hop_from_event(event))
    for trace in traces:
        hop = _hop_from_trace(trace)
        if hop is not None:
            hops.append(hop)
    # Deduplicate by communication_id preferring trace (has receiver confidence).
    merged: dict[str, TransmissionHopRecord] = {}
    for hop in sorted(hops, key=lambda item: (item.communication_id, item.tick)):
        existing = merged.get(hop.communication_id)
        if existing is None:
            merged[hop.communication_id] = hop
            continue
        if existing.receiver_confidence is None and hop.receiver_confidence is not None:
            merged[hop.communication_id] = hop
    hop_list = tuple(
        sorted(
            merged.values(),
            key=lambda item: (item.hop_count, item.tick, item.communication_id),
        )
    )
    if transmission_root_id is None:
        roots = sorted({hop.transmission_root_id for hop in hop_list})
        transmission_root_id = roots[0] if roots else "none"
    else:
        transmission_root_id = require_stable_id(
            "transmission_root_id", transmission_root_id
        )
        hop_list = tuple(
            hop
            for hop in hop_list
            if hop.transmission_root_id == transmission_root_id
        )
    agents: set[str] = set()
    for hop in hop_list:
        agents.add(hop.speaker_id)
        if hop.listener_id is not None:
            agents.add(hop.listener_id)
    children: dict[str, int] = defaultdict(int)
    for hop in hop_list:
        if hop.hop_count > 0:
            children[hop.transmission_root_id] += 1
    fan_out = max(children.values()) if children else 0
    branch_count = sum(1 for count in children.values() if count > 1)
    unresolved = sum(1 for hop in hop_list if hop.event_id is None)
    max_hop = max((hop.hop_count for hop in hop_list), default=0)
    return SocialTransmissionReport(
        experiment_id=experiment_id,
        run_id=run_id,
        metric_version=SOCIAL_TRANSMISSION_METRIC_VERSION,
        transmission_root_id=transmission_root_id,
        hops=hop_list,
        distortions=_distortions(hop_list),
        unique_agent_count=len(agents),
        branch_count=branch_count,
        fan_out_count=fan_out,
        max_hop_count=max_hop,
        unresolved_link_count=unresolved,
        event_count=len(_communication_events(events)),
        trace_count=sum(
            1
            for trace in traces
            if trace.provenance.kind is MemorySourceKind.COMMUNICATED
        ),
    )


class SocialTransmissionAnalysisService:
    """Experiment-only join of communication events and communicated traces."""

    __slots__ = ("_events", "_memory")

    def __init__(
        self,
        *,
        memory: MemoryEvidenceSource,
        events: ObjectiveEventSource,
    ) -> None:
        self._memory = memory
        self._events = events

    def analyze_social_transmission(
        self,
        *,
        experiment_id: str,
        run_id: str,
        owner_ids: Sequence[str],
        transmission_root_id: str | None = None,
    ) -> SocialTransmissionReport:
        experiment_id = require_stable_id("experiment_id", experiment_id)
        run_id = require_stable_id("run_id", run_id)
        _LOG.debug(
            "social_transmission_analysis_start",
            extra={
                "operation": "analyze_social_transmission",
                "experiment_id": experiment_id,
                "run_id": run_id,
                "owner_count": len(owner_ids),
                "metric_version": SOCIAL_TRANSMISSION_METRIC_VERSION,
            },
        )
        events = self._events.events_for_run(run_id)
        traces: list[MemoryTrace] = []
        for owner_id in owner_ids:
            traces.extend(self._memory.traces(run_id=run_id, owner_id=owner_id))
        report = build_social_transmission_report(
            experiment_id=experiment_id,
            run_id=run_id,
            events=events,
            traces=traces,
            transmission_root_id=transmission_root_id,
        )
        _LOG.info(
            "social_transmission_analysis_complete",
            extra={
                "operation": "analyze_social_transmission",
                "experiment_id": experiment_id,
                "run_id": run_id,
                "event_count": report.event_count,
                "trace_count": report.trace_count,
                "hop_count": len(report.hops),
                "max_hop": report.max_hop_count,
                "unresolved_link_count": report.unresolved_link_count,
                "metric_version": report.metric_version,
            },
        )
        return report
