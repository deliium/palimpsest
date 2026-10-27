"""Read-only generational history composition without API or LLM imports."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final, cast

from experiments.generational_archive import (
    GenerationalArchiveSession,
    GenerationalExecutionRecipe,
    build_assignment_identity,
    build_environment_identity,
    build_manifest_payload,
    build_provider_identity,
    open_generational_archive,
)
from experiments.generational_artifacts import HistoricalBoundaryReference
from experiments.generational_sampling import SocietyIdentityRow
from experiments.persistence import PersistedAnalysisSnapshot
from simulation.generational_models import ExperimentCriterionSpec
from simulation.models import RunId
from simulation.persistence import (
    SimulationRunRepository,
    SnapshotRepository,
    TickJournalRepository,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.generational_composition"
)


@dataclass(frozen=True, slots=True)
class PostgresHistoricalBoundaryReader:
    """Read-only adapter over authoritative run/journal/snapshot repositories."""

    runs: SimulationRunRepository
    journal: TickJournalRepository
    snapshots: SnapshotRepository
    evidence: object | None = None

    async def reference(
        self, run_id: str, boundary_tick: int
    ) -> HistoricalBoundaryReference:
        from experiments.generational_artifacts import SnapshotReference
        from simulation.clock import Tick

        if isinstance(boundary_tick, bool) or not isinstance(boundary_tick, int):
            raise TypeError("boundary_tick must be int")
        if boundary_tick < 0:
            raise ValueError("boundary_tick must be >= 0")
        target = RunId(run_id)
        get_run = getattr(self.runs, "get_run", None)
        if callable(get_run):
            manifest = await get_run(target)
            if manifest is None:
                raise ValueError("historical_run_missing")
        if boundary_tick == 0:
            snapshot = await self.snapshots.get_latest_at_or_before(target, Tick(0))
            if snapshot is None:
                raise ValueError("historical_snapshot_missing")
            return HistoricalBoundaryReference(
                revision=0,
                objective_commit_hash="0" * 64,
                snapshot_ref=SnapshotReference(
                    snapshot_id=str(snapshot.snapshot_id.value),
                    integrity_hash=str(snapshot.integrity_hash.value),
                    next_tick=snapshot.next_tick.value,
                ),
            )
        commit = await self.journal.get_tick_commit(target, Tick(boundary_tick - 1))
        if commit is None:
            raise ValueError("historical_commit_missing")
        if commit.resulting_tick.value != boundary_tick:
            raise ValueError("historical_commit_boundary_mismatch")
        snapshot = await self.snapshots.get_latest_at_or_before(
            target, Tick(boundary_tick)
        )
        if snapshot is None:
            raise ValueError("historical_snapshot_missing")
        if snapshot.next_tick.value > boundary_tick:
            raise ValueError("historical_snapshot_after_boundary")
        _LOG.debug(
            "historical_boundary_reference run_id=%s boundary=%s snapshot_next_tick=%s",
            run_id,
            boundary_tick,
            snapshot.next_tick.value,
        )
        evidence_ref = None
        if self.evidence is not None:
            get_manifest = getattr(self.evidence, "get_manifest", None)
            if callable(get_manifest):
                manifest = await get_manifest(run_id=run_id)
                if manifest is not None:
                    from simulation.evidence import (
                        encode_evidence_manifest_payload,
                    )

                    evidence_ref = json.loads(
                        encode_evidence_manifest_payload(manifest)
                    )
                    evidence_ref["manifest_hash"] = manifest.manifest_hash
        return HistoricalBoundaryReference(
            revision=commit.resulting_revision.value,
            objective_commit_hash=str(commit.commit_hash.value),
            snapshot_ref=SnapshotReference(
                snapshot_id=str(snapshot.snapshot_id.value),
                integrity_hash=str(snapshot.integrity_hash.value),
                next_tick=snapshot.next_tick.value,
            ),
            evidence_ref=evidence_ref,
        )


__all__ = [
    "GenerationalArchiveSession",
    "GenerationalExecutionRecipe",
    "PostgresCommunitySampleProvider",
    "PostgresHistoricalBoundaryReader",
    "build_assignment_identity",
    "build_environment_identity",
    "build_manifest_payload",
    "build_provider_identity",
    "open_generational_archive",
]


def _event_key(event: object) -> tuple[int, int]:
    tick = getattr(event, "tick", 0)
    tick_value = getattr(tick, "value", tick)
    sequence = getattr(event, "sequence", -1)
    sequence_value = getattr(sequence, "value", sequence)
    return (
        int(tick_value) if type(tick_value) is int else 0,
        int(sequence_value) if type(sequence_value) is int else -1,
    )


def _merge_sorted_identity_rows(
    existing: list[tuple[int, SocietyIdentityRow]],
    added: list[tuple[int, SocietyIdentityRow]],
) -> list[tuple[int, SocietyIdentityRow]]:
    merged: list[tuple[int, SocietyIdentityRow]] = []
    left = right = 0
    while left < len(existing) and right < len(added):
        existing_key = (
            existing[left][0],
            existing[left][1].body_id,
            existing[left][1].agent_id,
        )
        added_key = (added[right][0], added[right][1].body_id, added[right][1].agent_id)
        if existing_key <= added_key:
            merged.append(existing[left])
            left += 1
        else:
            merged.append(added[right])
            right += 1
    merged.extend(existing[left:])
    merged.extend(added[right:])
    return merged


@dataclass(slots=True)
class PostgresCommunitySampleProvider:
    """Boundary-scoped detached community evidence from durable snapshots.

    One boundary sample reuses a single loader snapshot for regional input and
    identity projection. Results are cached per exact boundary tick (bounded,
    immutable payloads only); identity rows are extended only through the next
    verified snapshot high-water, so earlier admissions stay queryable after
    death while later events are excluded.
    """

    loader: object
    run_id: str
    owner_id: str
    window_ticks: int = 100
    input_revision: str = "generational-community-v1"
    page_limit: int = 1_000
    _sample_cache: dict[tuple[int, str], object] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _identity_rows: tuple[tuple[int, SocietyIdentityRow], ...] = field(
        default=(), init=False, repr=False, compare=False
    )
    _identity_high_water: int | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _identity_event_count: int = field(default=0, init=False, repr=False, compare=False)
    _identity_last_key: tuple[int, int] | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _cache_limit: int = field(default=8, init=False, repr=False, compare=False)
    _sample_cache_bytes: dict[tuple[int, str], int] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _cache_byte_limit: int = field(
        default=8 * 1024 * 1024, init=False, repr=False, compare=False
    )

    async def _snapshot(self) -> PersistedAnalysisSnapshot:
        from experiments.composition import load_paged_analysis_snapshot

        if not callable(getattr(self.loader, "load", None)) and not callable(
            getattr(self.loader, "load_objective_event_page", None)
        ):
            raise ValueError("analysis_evidence_loader_required")
        return await load_paged_analysis_snapshot(
            self.loader,
            run_id=self.run_id,
            owner_id=self.owner_id,
            page_limit=self.page_limit,
            include_subjective=False,
        )

    async def regional_input(
        self, boundary: object, *, snapshot: object | None = None
    ) -> object:
        from experiments.composition import regional_population_input_from_snapshot
        from simulation.generational_models import GenerationalBoundary

        if type(boundary) is not GenerationalBoundary:
            raise TypeError("boundary must be GenerationalBoundary")
        from typing import cast

        resolved = cast(
            PersistedAnalysisSnapshot,
            await self._snapshot() if snapshot is None else snapshot,
        )
        return regional_population_input_from_snapshot(
            resolved,
            input_revision=self.input_revision,
            window_end=boundary.progress.boundary_tick,
            complete_through_boundary=boundary.progress.boundary_tick,
        )

    def identities(
        self, boundary: object, *, snapshot: object | None = None
    ) -> tuple[SocietyIdentityRow, ...]:
        from simulation.generational_models import GenerationalBoundary

        if type(boundary) is not GenerationalBoundary:
            raise TypeError("boundary must be GenerationalBoundary")
        high_water = getattr(snapshot, "objective_complete_through_boundary", None)
        if high_water is None:
            high_water = boundary.progress.boundary_tick
        if self._identity_high_water != high_water:
            self._identity_rows = self._extend_identity_rows(snapshot)
            self._identity_high_water = high_water
            _LOG.debug(
                "community_identity_index_built run_id=%s owner_id=%s "
                "high_water=%s rows=%s events=%s",
                self.run_id,
                self.owner_id,
                high_water,
                len(self._identity_rows),
                self._identity_event_count,
            )
        boundary_tick = boundary.progress.boundary_tick
        return tuple(row for tick, row in self._identity_rows if tick <= boundary_tick)

    def _extend_identity_rows(
        self, snapshot: object | None
    ) -> tuple[tuple[int, SocietyIdentityRow], ...]:
        if snapshot is None:
            return ()
        events = cast(Sequence[object], getattr(snapshot, "events", ()))
        existing = list(self._identity_rows)
        prefix_intact = (
            existing
            and self._identity_last_key is not None
            and self._identity_event_count > 0
            and len(events) >= self._identity_event_count
            and _event_key(events[self._identity_event_count - 1])
            == self._identity_last_key
        )
        start = self._identity_event_count if prefix_intact else 0
        if not prefix_intact:
            existing = []
        added: list[tuple[int, SocietyIdentityRow]] = []
        for event in events[start:]:
            details = getattr(event, "details", None)
            if getattr(details, "kind", None) != "agent_created":
                continue
            tick = getattr(event, "tick", None)
            tick_value = getattr(tick, "value", tick)
            if type(tick_value) is not int or tick_value < 0:
                tick_value = 0
            body_id = getattr(details, "body_id", None)
            added.append(
                (
                    tick_value,
                    SocietyIdentityRow(
                        body_id=str(getattr(body_id, "value", body_id)),
                        agent_id=str(getattr(details, "agent_id", "")),
                        generation_index=int(getattr(details, "generation_index", 0)),
                        cohort_id=str(getattr(details, "cohort_id", "")),
                    ),
                )
            )
        self._identity_event_count = len(events)
        self._identity_last_key = _event_key(events[-1]) if len(events) else None
        if not added:
            return tuple(existing)
        added.sort(key=lambda item: (item[0], item[1].body_id, item[1].agent_id))
        if not existing:
            return tuple(added)
        return tuple(_merge_sorted_identity_rows(existing, added))

    def _cache_sample(self, boundary_tick: int, payload: object) -> None:
        cache_key = (boundary_tick, self.input_revision)
        if cache_key in self._sample_cache:
            return
        size = len(
            json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        if size > self._cache_byte_limit:
            _LOG.debug(
                "community_sample_cache_skipped run_id=%s boundary_tick=%s "
                "byte_count=%s reason_code=item_too_large",
                self.run_id,
                boundary_tick,
                size,
            )
            return
        while self._sample_cache and (
            len(self._sample_cache) >= self._cache_limit
            or sum(self._sample_cache_bytes.values()) + size > self._cache_byte_limit
        ):
            oldest = next(iter(self._sample_cache))
            self._sample_cache.pop(oldest, None)
            self._sample_cache_bytes.pop(oldest, None)
        self._sample_cache[cache_key] = payload
        self._sample_cache_bytes[cache_key] = size

    async def sample(self, boundary: object) -> object:
        from experiments.generational_sampling import (
            GenerationalHistoricalSampler,
        )
        from simulation.generational_models import GenerationalBoundary

        if type(boundary) is not GenerationalBoundary:
            raise TypeError("boundary must be GenerationalBoundary")
        boundary_tick = boundary.progress.boundary_tick
        cache_key = (boundary_tick, self.input_revision)
        cached = self._sample_cache.get(cache_key)
        if cached is not None:
            _LOG.debug(
                "community_sample_cache_hit run_id=%s owner_id=%s boundary_tick=%s",
                self.run_id,
                self.owner_id,
                boundary_tick,
            )
            return cached
        snapshot = await self._snapshot()
        regional = await self.regional_input(boundary, snapshot=snapshot)
        if regional is None:
            return None
        identities = self.identities(boundary, snapshot=snapshot)
        sampler = GenerationalHistoricalSampler(window_ticks=self.window_ticks)
        sample = sampler.sample(
            boundary=boundary,
            regional_input=regional,  # type: ignore[arg-type]
            identities=identities,
        )
        payload = sample.canonical_payload()
        self._cache_sample(boundary_tick, payload)
        _LOG.debug(
            "community_sample_built run_id=%s owner_id=%s boundary_tick=%s",
            self.run_id,
            self.owner_id,
            boundary_tick,
        )
        return payload

    def criterion_factory(
        self,
    ) -> Callable[[ExperimentCriterionSpec], object]:
        from experiments.generational_sampling import (
            build_live_community_criterion_factory,
        )

        return build_live_community_criterion_factory(
            regional_input_provider=self.regional_input,
            identities_provider=self.identities,
        )
