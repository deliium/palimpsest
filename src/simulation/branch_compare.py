"""Detached research-branch timeline comparison (single-fold journal reads).

Compares two run journals that share a fork relationship. Never loads two live
engines and never imports ``analysis`` / ``experiments`` / ``api``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from typing import Final

from simulation.branching import (
    BranchError,
    BranchLineage,
    BranchTimelineCompareRequest,
    BranchTimelineCompareResult,
)
from simulation.clock import Tick
from simulation.journal import hash_tick_payload
from simulation.persistence import BranchLineageRepository, TickJournalRepository
from world.events import WorldEvent

__all__ = [
    "JournalBranchCompare",
    "compare_branch_timelines",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.branching")


def _event_fingerprint(event: WorldEvent) -> tuple[object, ...]:
    """Payload-equivalent identity ignoring run_id (commit hashes may differ)."""
    return (
        event.tick,
        event.sequence,
        type(event.details).__name__,
        event.actor_id.value if event.actor_id is not None else None,
        event.target_id.value if event.target_id is not None else None,
        hash_tick_payload((replace(event, run_id="compare"),)).value,
    )


def _kind_counts(events: Sequence[WorldEvent]) -> dict[str, int]:
    counter: Counter[str] = Counter(type(event.details).__name__ for event in events)
    return dict(sorted(counter.items()))


def _post_fork_hash(events: Sequence[WorldEvent], *, fork_tick: int) -> str:
    post = [event for event in events if event.tick >= fork_tick]
    document = {
        "mode": "branch-post-fork-replica",
        "fork_tick": fork_tick,
        "events": [
            {
                "tick": event.tick,
                "sequence": event.sequence,
                "kind": type(event.details).__name__,
                "payload_hash": hash_tick_payload(
                    (replace(event, run_id="compare"),)
                ).value,
            }
            for event in post
        ],
    }
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


async def compare_branch_timelines(
    request: BranchTimelineCompareRequest,
    *,
    journal: TickJournalRepository,
    lineage: BranchLineageRepository | None = None,
) -> BranchTimelineCompareResult:
    """Compare two journals; prefer replica-normalized post-fork hashes."""
    if type(request) is not BranchTimelineCompareRequest:
        raise TypeError("request must be BranchTimelineCompareRequest")
    fork_tick = request.fork_tick
    if fork_tick is None:
        if lineage is None:
            raise BranchError("invalid_intervention", "fork_tick_required")
        left_lineage = await lineage.get_lineage(child_run_id=request.left_run_id)
        right_lineage = await lineage.get_lineage(child_run_id=request.right_run_id)
        resolved: BranchLineage | None = None
        for candidate in (left_lineage, right_lineage):
            if candidate is not None and type(candidate) is BranchLineage:
                resolved = candidate
                break
        if resolved is None:
            raise BranchError("branch_root", "fork_tick_unresolved")
        fork_tick = resolved.fork_tick

    left_events = tuple(
        await journal.list_events(
            request.left_run_id,
            from_tick=Tick(0),
            to_tick=None,
            limit=10_000_000,
            offset=0,
        )
    )
    right_events = tuple(
        await journal.list_events(
            request.right_run_id,
            from_tick=Tick(0),
            to_tick=None,
            limit=10_000_000,
            offset=0,
        )
    )
    left_prefix = [e for e in left_events if e.tick < fork_tick]
    right_prefix = [e for e in right_events if e.tick < fork_tick]
    prefix_equivalent = True
    diverge_tick: int | None = None
    diverge_sequence: int | None = None
    reason_code: str | None = None

    max_prefix = max(len(left_prefix), len(right_prefix))
    for index in range(max_prefix):
        if index >= len(left_prefix) or index >= len(right_prefix):
            prefix_equivalent = False
            longer = right_prefix if index >= len(left_prefix) else left_prefix
            event = longer[index]
            diverge_tick = event.tick
            diverge_sequence = event.sequence
            reason_code = "prefix_length_mismatch"
            break
        left = left_prefix[index]
        right = right_prefix[index]
        if _event_fingerprint(left) != _event_fingerprint(right):
            prefix_equivalent = False
            diverge_tick = left.tick
            diverge_sequence = left.sequence
            reason_code = "prefix_payload_mismatch"
            break

    if prefix_equivalent:
        left_post = [e for e in left_events if e.tick >= fork_tick]
        right_post = [e for e in right_events if e.tick >= fork_tick]
        max_post = max(len(left_post), len(right_post))
        for index in range(max_post):
            if index >= len(left_post) or index >= len(right_post):
                longer = right_post if index >= len(left_post) else left_post
                event = longer[index]
                diverge_tick = event.tick
                diverge_sequence = event.sequence
                reason_code = "post_fork_length_mismatch"
                break
            left = left_post[index]
            right = right_post[index]
            if _event_fingerprint(left) != _event_fingerprint(right):
                diverge_tick = left.tick
                diverge_sequence = left.sequence
                reason_code = "post_fork_payload_mismatch"
                break

    left_hash = _post_fork_hash(left_events, fork_tick=fork_tick)
    right_hash = _post_fork_hash(right_events, fork_tick=fork_tick)
    counts = None
    if request.include_event_kind_counts:
        counts = {
            "left": _kind_counts(left_events),
            "right": _kind_counts(right_events),
        }

    _LOG.info(
        "branch_timeline_compare parent=%s child=%s diverge_tick=%s "
        "diverge_sequence=%s",
        request.left_run_id.value,
        request.right_run_id.value,
        diverge_tick,
        diverge_sequence,
    )
    return BranchTimelineCompareResult(
        left_run_id=request.left_run_id,
        right_run_id=request.right_run_id,
        fork_tick=fork_tick,
        prefix_equivalent=prefix_equivalent,
        diverge_tick=diverge_tick,
        diverge_sequence=diverge_sequence,
        reason_code=reason_code,
        left_post_fork_trajectory_hash=left_hash,
        right_post_fork_trajectory_hash=right_hash,
        event_kind_counts=counts,
    )


class JournalBranchCompare:
    """Adapter implementing the API ``BranchComparePort`` protocol."""

    __slots__ = ("_journal", "_lineage")

    def __init__(
        self,
        journal: TickJournalRepository,
        lineage: BranchLineageRepository | None = None,
    ) -> None:
        self._journal = journal
        self._lineage = lineage

    async def compare(
        self, request: BranchTimelineCompareRequest
    ) -> BranchTimelineCompareResult:
        return await compare_branch_timelines(
            request, journal=self._journal, lineage=self._lineage
        )
