"""Read-only generational history composition without API or LLM imports."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

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
            snapshot = await self.snapshots.get_latest_at_or_before(
                target, Tick(0)
            )
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
        commit = await self.journal.get_tick_commit(
            target, Tick(boundary_tick - 1)
        )
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
            "historical_boundary_reference run_id=%s boundary=%s "
            "snapshot_next_tick=%s",
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


@dataclass(frozen=True, slots=True)
class PostgresCommunitySampleProvider:
    """Boundary-scoped detached community evidence from durable snapshots."""

    loader: object
    run_id: str
    owner_id: str
    window_ticks: int = 100
    input_revision: str = "generational-community-v1"

    async def _snapshot(self) -> object:
        load = getattr(self.loader, "load", None)
        if not callable(load):
            raise ValueError("analysis_evidence_loader_required")
        return await load(run_id=self.run_id, owner_id=self.owner_id)

    async def regional_input(self, boundary: object) -> object:
        from experiments.composition import regional_population_input_from_snapshot
        from simulation.generational_models import GenerationalBoundary

        if type(boundary) is not GenerationalBoundary:
            raise TypeError("boundary must be GenerationalBoundary")
        from typing import cast

        from experiments.persistence import PersistedAnalysisSnapshot

        snapshot = cast(PersistedAnalysisSnapshot, await self._snapshot())
        return regional_population_input_from_snapshot(
            snapshot,
            input_revision=self.input_revision,
            window_end=boundary.progress.boundary_tick,
            complete_through_boundary=boundary.progress.boundary_tick,
        )

    async def identities(self, boundary: object) -> object:
        from experiments.generational_sampling import SocietyIdentityRow
        from simulation.generational_models import GenerationalBoundary

        if type(boundary) is not GenerationalBoundary:
            raise TypeError("boundary must be GenerationalBoundary")
        snapshot = await self._snapshot()
        rows: list[SocietyIdentityRow] = []
        for event in getattr(snapshot, "events", ()):
            details = getattr(event, "details", None)
            if getattr(details, "kind", None) != "agent_created":
                continue
            body_id = getattr(details, "body_id", None)
            rows.append(
                SocietyIdentityRow(
                    body_id=str(getattr(body_id, "value", body_id)),
                    agent_id=str(getattr(details, "agent_id", "")),
                    generation_index=int(getattr(details, "generation_index", 0)),
                    cohort_id=str(getattr(details, "cohort_id", "")),
                )
            )
        return tuple(sorted(rows, key=lambda row: (row.body_id, row.agent_id)))

    async def sample(self, boundary: object) -> object:
        from experiments.generational_sampling import (
            GenerationalHistoricalSampler,
        )
        from simulation.generational_models import GenerationalBoundary

        if type(boundary) is not GenerationalBoundary:
            raise TypeError("boundary must be GenerationalBoundary")
        regional = await self.regional_input(boundary)
        if regional is None:
            return None
        identities = await self.identities(boundary)
        sampler = GenerationalHistoricalSampler(window_ticks=self.window_ticks)
        sample = sampler.sample(
            boundary=boundary,
            regional_input=regional,  # type: ignore[arg-type]
            identities=identities,  # type: ignore[arg-type]
        )
        return sample.canonical_payload()

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
