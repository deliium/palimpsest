"""Durable prepare → persist → finalize coordination for WorldEngine.

``PersistentSimulationService`` prepares a detached candidate, awaits one
repository append, then publishes only after a successful commit. Adapter
failure leaves the live engine unchanged. Ambiguous commit outcomes fence the
instance instead of blind retry. Prepared candidates are not part of the
public facade.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Final

from simulation.clock import Tick
from simulation.engine import WorldEngine, _PreparedTickCandidate
from simulation.identifiers import derive_scoped_id
from simulation.journal import (
    bind_snapshot_commit_hash,
    compute_commit_hash,
    hash_snapshot,
    hash_tick_events,
    hash_tick_payload,
)
from simulation.lifecycle import (
    ActionSubmission,
    EngineDiagnosticCode,
    require_action_submission,
)
from simulation.models import DERIVATION_VERSION
from simulation.persistence import (
    PROJECTOR_VERSION,
    CommitHash,
    PayloadHash,
    SnapshotExtensions,
    SnapshotId,
    TickAppendRequest,
    TickCommit,
    TickJournalRepository,
    WorldSnapshot,
    checkpoint_schema_for_production,
)
from simulation.randomness import StreamScope
from world.identifiers import require_stable_id

_LOGGER = logging.getLogger("simulation.service")

__all__ = [
    "DurableCommitAmbiguity",
    "PersistentSimulationService",
]


class DurableCommitAmbiguity(RuntimeError):
    """Commit outcome is unknown; the durable service must fence and reload."""


def _snapshot_content_equal(left: WorldSnapshot, right: WorldSnapshot) -> bool:
    """Compare objective checkpoint content ignoring integrity/predecessor."""
    from dataclasses import fields

    for field in fields(WorldSnapshot):
        if field.name in {"integrity_hash", "predecessor_commit_hash"}:
            continue
        if getattr(left, field.name) != getattr(right, field.name):
            return False
    return True


class PersistentSimulationService:
    """Application service that persists each tick before publishing in-memory."""

    __slots__ = (
        "_engine",
        "_fenced",
        "_journal",
        "_predecessor_commit_hash",
    )

    def __init__(
        self,
        engine: WorldEngine,
        journal: TickJournalRepository,
        *,
        predecessor_commit_hash: CommitHash | None = None,
    ) -> None:
        if type(engine) is not WorldEngine:
            raise TypeError("PersistentSimulationService requires WorldEngine")
        self._engine = engine
        self._journal = journal
        if (
            predecessor_commit_hash is not None
            and type(predecessor_commit_hash) is not CommitHash
        ):
            raise TypeError("predecessor_commit_hash must be CommitHash or None")
        self._predecessor_commit_hash = predecessor_commit_hash
        self._fenced = False

    @property
    def engine(self) -> WorldEngine:
        return self._engine

    @property
    def fenced(self) -> bool:
        return self._fenced

    @property
    def predecessor_commit_hash(self) -> CommitHash | None:
        return self._predecessor_commit_hash

    def draft_checkpoint_from_candidate(
        self,
        candidate: _PreparedTickCandidate,
        *,
        snapshot_id: SnapshotId,
    ) -> WorldSnapshot:
        """Build an unbound checkpoint from a prepared candidate's next state."""
        if type(candidate) is not _PreparedTickCandidate:
            raise TypeError("candidate must be _PreparedTickCandidate")
        if type(snapshot_id) is not SnapshotId:
            raise TypeError("snapshot_id must be SnapshotId")
        next_snap = candidate.next_snapshot
        state = next_snap.world.state
        derivation = self._engine._config.derivation_version or DERIVATION_VERSION
        schema_version, codec_version = checkpoint_schema_for_production(
            production_active=self._engine._production_catalog is not None,
            dynamics_active=self._engine._environmental_dynamics is not None,
            artifacts_active=self._engine._artifacts_enabled,
            lifecycle_active=self._engine.lifecycle_channel_active,
            new_agent_provenance_active=self._engine.new_agent_provenance_active,
            kinship_active=self._engine.kinship_channel_active,
            dependency_care_active=self._engine.dependency_care_channel_active,
            durable_records_active=self._engine.durable_records_channel_active,
            knowledge_repositories_active=(
                self._engine.knowledge_repositories_channel_active
            ),
            bounded_experimentation_active=self._engine.bounded_experimentation_active,
            possession_succession_active=self._engine.possession_succession_active,
            structured_commitments_active=self._engine.structured_commitments_active,
            subjective_valuation_active=self._engine.subjective_valuation_active,
            resource_exchange_profile_active=self._engine.resource_exchange_profile_active,
            collective_projects_active=self._engine.collective_projects_active,
            public_goods_active=self._engine.public_goods_active,
            regions_migration_active=state.regions_migration is not None,
            cultural_contact_active=self._engine.cultural_contact_active,
            infrastructure_networks_active=(
                self._engine.infrastructure_networks_active
            ),
            travel_network_active=self._engine.travel_network_active,
            measurement_active=bool(state.instrument_states),
            disease_active=self._engine._disease_mechanics is not None,
            ecological_feedback_active=(
                self._engine._ecological_resources is not None
            ),
            overexploitation_active=self._engine._overexploitation_active,
            disasters_active=self._engine._disasters is not None,
        )
        if codec_version == "v24":
            from dataclasses import replace as _dc_replace

            from simulation.disasters_checkpoint import build_v24_checkpoint_extensions
            from world.kinship import KinshipGraph

            graph = self._engine.kinship_graph
            kinship_edges = graph.edges if type(graph) is KinshipGraph else ()
            assert self._engine._environmental_dynamics is not None
            v24_rows = build_v24_checkpoint_extensions(
                state=state,
                lifecycle_records=tuple(self._engine.lifecycle_records),
                kinship_edges=kinship_edges,
                dependency_need_registers=tuple(
                    self._engine._dependency_need_registers.values()
                ),
                environmental_dynamics=self._engine._environmental_dynamics,
                disease_spec=self._engine._disease_mechanics,
                travel_network_active=self._engine.travel_network_active,
                infrastructure_networks_active=(
                    self._engine.infrastructure_networks_active
                ),
                measurement_active=bool(state.instrument_states),
            )
            draft = WorldSnapshot(
                snapshot_id=snapshot_id,
                run_id=self._engine.run_id,
                world_id=self._engine.world_id,
                seed=self._engine._config.seed,
                config=self._engine._config,
                registrations=self._engine._registrations,
                locations=tuple(state.locations.values()),
                bodies=tuple(state.bodies.values()),
                items=tuple(state.items.values()),
                resources=tuple(state.resources.values()),
                weather=tuple(state.weather.values()),
                next_tick=next_snap.tick,
                revision=candidate.resulting_revision,
                event_schema_version=schema_version,
                projector_version=PROJECTOR_VERSION,
                persistence_codec_version=codec_version,
                derivation_version=derivation,
                integrity_hash=PayloadHash("a" * 64),
                predecessor_commit_hash=None,
                **v24_rows,
            )
            return _dc_replace(draft, integrity_hash=hash_snapshot(draft))
        if codec_version == "v27":
            from dataclasses import replace as _dc_replace

            from simulation.overexploitation_checkpoint import (
                build_v27_checkpoint_extensions,
            )
            from world.kinship import KinshipGraph

            graph = self._engine.kinship_graph
            kinship_edges = graph.edges if type(graph) is KinshipGraph else ()
            assert self._engine._environmental_dynamics is not None
            v27_rows = build_v27_checkpoint_extensions(
                state=state,
                lifecycle_records=tuple(self._engine.lifecycle_records),
                kinship_edges=kinship_edges,
                dependency_need_registers=tuple(
                    self._engine._dependency_need_registers.values()
                ),
                environmental_dynamics=self._engine._environmental_dynamics,
                disease_spec=self._engine._disease_mechanics,
                travel_network_active=self._engine.travel_network_active,
            )
            draft = WorldSnapshot(
                snapshot_id=snapshot_id,
                run_id=self._engine.run_id,
                world_id=self._engine.world_id,
                seed=self._engine._config.seed,
                config=self._engine._config,
                registrations=self._engine._registrations,
                locations=tuple(state.locations.values()),
                bodies=tuple(state.bodies.values()),
                items=tuple(state.items.values()),
                resources=tuple(state.resources.values()),
                weather=tuple(state.weather.values()),
                next_tick=next_snap.tick,
                revision=candidate.resulting_revision,
                event_schema_version=schema_version,
                projector_version=PROJECTOR_VERSION,
                persistence_codec_version=codec_version,
                derivation_version=derivation,
                integrity_hash=PayloadHash("a" * 64),
                predecessor_commit_hash=None,
                **v27_rows,
            )
            return _dc_replace(draft, integrity_hash=hash_snapshot(draft))
        production_rows: SnapshotExtensions = {}
        if codec_version in {
            "v3",
            "v4",
            "v5",
            "v6",
            "v7",
            "v8",
            "v9",
            "v10",
            "v11",
            "v12",
            "v13",
            "v14",
            "v15",
            "v16",
            "v17",
            "v18",
            "v19",
            "v20",
            "v21",
            "v22",
            "v23",
            "v25",
        }:
            production_rows = {
                "structures": tuple(state.structures.values()),
                "production_jobs": tuple(state.production_jobs.values()),
                "tool_marks": tuple(state.tool_marks.values()),
            }
        if codec_version in {
            "v4",
            "v5",
            "v6",
            "v7",
            "v8",
            "v9",
            "v10",
            "v11",
            "v12",
            "v13",
            "v14",
            "v15",
            "v16",
            "v17",
            "v18",
            "v19",
            "v20",
            "v21",
            "v22",
            "v23",
            "v25",
        }:
            production_rows["active_hazards"] = tuple(state.active_hazards)
        if codec_version in {
            "v5",
            "v6",
            "v7",
            "v8",
            "v9",
            "v10",
            "v11",
            "v12",
            "v13",
            "v14",
            "v15",
            "v16",
            "v17",
            "v18",
            "v19",
            "v20",
            "v21",
            "v22",
            "v23",
            "v25",
        }:
            production_rows["artifacts"] = tuple(state.artifacts.values())
        if codec_version in {
            "v6",
            "v7",
            "v8",
            "v9",
            "v10",
            "v11",
            "v12",
            "v13",
            "v14",
            "v15",
            "v16",
            "v17",
            "v18",
            "v19",
            "v20",
            "v21",
            "v22",
            "v23",
            "v25",
        }:
            production_rows["lifecycle_records"] = tuple(self._engine.lifecycle_records)
        if codec_version in {
            "v8",
            "v9",
            "v10",
            "v11",
            "v12",
            "v13",
            "v14",
            "v15",
            "v16",
            "v17",
            "v18",
            "v19",
            "v20",
            "v21",
            "v22",
            "v23",
            "v25",
        }:
            graph = self._engine.kinship_graph
            from world.kinship import KinshipGraph

            if type(graph) is KinshipGraph:
                production_rows["kinship_edges"] = graph.edges
        if codec_version in {
            "v9",
            "v10",
            "v11",
            "v12",
            "v13",
            "v14",
            "v15",
            "v16",
            "v17",
            "v18",
            "v19",
            "v20",
            "v21",
            "v22",
            "v23",
            "v25",
        }:
            production_rows["dependency_need_registers"] = tuple(
                self._engine._dependency_need_registers.values()
            )
        if codec_version in {
            "v11",
            "v12",
            "v13",
            "v14",
            "v15",
            "v16",
            "v17",
            "v18",
            "v19",
            "v20",
            "v21",
            "v22",
            "v23",
            "v25",
        }:
            production_rows["repositories"] = tuple(state.repositories.values())
        if codec_version in {
            "v13",
            "v14",
            "v15",
            "v16",
            "v17",
            "v18",
            "v19",
            "v20",
            "v21",
            "v22",
            "v23",
            "v25",
        }:
            production_rows["corpse_custody_item_ids"] = tuple(
                sorted(state.corpse_custody_item_ids, key=lambda item: item.value)
            )
        if codec_version in {"v15", "v16", "v17", "v18", "v19", "v20", "v21", "v25"}:
            production_rows["exchange_offers"] = tuple(state.exchange_offers)
        if codec_version in {"v17", "v18", "v19", "v20", "v21", "v25"}:
            production_rows["collective_projects"] = tuple(
                state.collective_projects.values()
            )
        if codec_version in {"v19", "v20", "v21", "v25"}:
            production_rows["regions_migration"] = state.regions_migration
            production_rows["journeys"] = (
                None if state.journeys is None else tuple(state.journeys.values())
            )
        if codec_version in {"v21", "v25"}:
            production_rows["infrastructure"] = tuple(
                state.infrastructure.values()
                if state.infrastructure is not None
                else ()
            )
        if codec_version in {"v25", "v26"}:
            production_rows["travel_network"] = tuple(state.travel_network)
        if codec_version == "v26":
            production_rows["instrument_states"] = tuple(
                sorted(
                    state.instrument_states.values(),
                    key=lambda row: row.item_id.value,
                )
            )
            production_rows["measurement_references"] = tuple(
                sorted(
                    state.measurement_references.values(),
                    key=lambda row: row.item_id.value,
                )
            )
        if codec_version == "v22" or (
            codec_version == "v23" and self._engine._disease_mechanics is not None
        ):
            from simulation.disease_checkpoint import (
                DiseaseCheckpointRow,
                DiseaseCheckpointSection,
                policy_sha256_for_spec,
            )

            spec = self._engine._disease_mechanics
            assert spec is not None
            rows = state.disease_state or {}
            checkpoint_rows = tuple(
                DiseaseCheckpointRow(
                    body_id=entity_id,
                    phase=row.phase.value,
                    due_tick=row.due_tick,
                    symptomatic=row.symptomatic,
                )
                for entity_id, row in sorted(
                    rows.items(), key=lambda item: item[0].value
                )
            )
            production_rows["disease_mechanics"] = DiseaseCheckpointSection(
                rows=checkpoint_rows,
                policy_sha256=policy_sha256_for_spec(spec),
            )
            if state.instrument_states:
                production_rows["instrument_states"] = tuple(
                    sorted(
                        state.instrument_states.values(),
                        key=lambda row: row.item_id.value,
                    )
                )
                production_rows["measurement_references"] = tuple(
                    sorted(
                        state.measurement_references.values(),
                        key=lambda row: row.item_id.value,
                    )
                )
        if codec_version == "v23":
            from simulation.ecological_resources_checkpoint import (
                checkpoint_section_from_rows,
            )

            ecology_spec = self._engine._ecological_resources
            assert ecology_spec is not None
            assert state.ecological_resources is not None
            assert state.ecological_policy_digest is not None
            assert self._engine._environmental_dynamics is not None
            production_rows["ecological_resources"] = checkpoint_section_from_rows(
                policy_sha256=state.ecological_policy_digest,
                rows=tuple(
                    (
                        row.resource_id,
                        row.minimum_capacity_tenths,
                        row.damage_tenths,
                    )
                    for row in state.ecological_resources.values()
                ),
            )
            production_rows["environmental_dynamics"] = (
                self._engine._environmental_dynamics
            )
        draft = WorldSnapshot(
            snapshot_id=snapshot_id,
            run_id=self._engine.run_id,
            world_id=self._engine.world_id,
            seed=self._engine._config.seed,
            config=self._engine._config,
            registrations=self._engine._registrations,
            locations=tuple(state.locations.values()),
            bodies=tuple(state.bodies.values()),
            items=tuple(state.items.values()),
            resources=tuple(state.resources.values()),
            weather=tuple(state.weather.values()),
            next_tick=next_snap.tick,
            revision=candidate.resulting_revision,
            event_schema_version=schema_version,
            projector_version=PROJECTOR_VERSION,
            persistence_codec_version=codec_version,
            derivation_version=derivation,
            integrity_hash=PayloadHash("a" * 64),
            predecessor_commit_hash=None,
            **production_rows,
        )
        from dataclasses import replace as _dc_replace_final

        return _dc_replace_final(draft, integrity_hash=hash_snapshot(draft))

    async def resolve_tick(
        self,
        submissions: Sequence[ActionSubmission],
        *,
        idempotency_key: str | None = None,
        snapshot: WorldSnapshot | None = None,
        checkpoint_id: SnapshotId | None = None,
    ) -> TickCommit:
        """Prepare, persist, then finalize one tick.

        Empty and event-only ticks are persisted. Repository failure before
        finalize leaves the engine snapshot unchanged.

        Checkpoints are candidate-owned. Prefer ``checkpoint_id`` (builds from
        ``_PreparedTickCandidate.next_snapshot``). A caller-supplied
        ``snapshot`` must match that candidate content exactly before binding.
        """
        if self._fenced:
            _LOGGER.warning(
                "%s reason=already_fenced run_id=%s tick=%s",
                EngineDiagnosticCode.DURABLE_FENCED.value,
                self._engine.run_id.value,
                self._engine.tick.value,
            )
            raise RuntimeError("PersistentSimulationService is fenced")
        if isinstance(submissions, (set, frozenset)) or not isinstance(
            submissions, Sequence
        ):
            raise TypeError("submissions must be an ordered sequence")
        if snapshot is not None and checkpoint_id is not None:
            raise ValueError("pass snapshot or checkpoint_id, not both")

        typed = tuple(require_action_submission(item) for item in submissions)
        live_before = self._engine._snapshot
        candidate = self._engine._prepare_tick_candidate(typed)
        if self._engine._snapshot is not live_before:
            self._engine._snapshot = live_before
            _LOGGER.error(
                "%s code=prepare_mutated_live run_id=%s tick=%s",
                EngineDiagnosticCode.DURABLE_FAILED.value,
                self._engine.run_id.value,
                candidate.tick.value,
            )
            raise RuntimeError("prepare must not mutate the live engine")

        key = self._resolve_idempotency_key(candidate.tick, idempotency_key)
        event_hashes = hash_tick_events(candidate.events)
        tick_payload = hash_tick_payload(candidate.events)
        expected_commit = compute_commit_hash(
            predecessor_commit_hash=self._predecessor_commit_hash,
            run_id=self._engine.run_id,
            tick=candidate.tick,
            base_revision=candidate.base_revision,
            resulting_revision=candidate.resulting_revision,
            event_hashes=event_hashes,
            payload_hash=tick_payload,
        )
        bound_snapshot: WorldSnapshot | None = None
        if checkpoint_id is not None:
            if type(checkpoint_id) is not SnapshotId:
                raise TypeError("checkpoint_id must be SnapshotId or None")
            candidate_owned = self.draft_checkpoint_from_candidate(
                candidate, snapshot_id=checkpoint_id
            )
            _LOGGER.debug(
                "%s source=candidate run_id=%s tick=%s snapshot_id=%s "
                "revision=%s hash_prefix=%s",
                EngineDiagnosticCode.CHECKPOINT_RESTORE.value,
                self._engine.run_id.value,
                candidate.tick.value,
                candidate_owned.snapshot_id.value,
                candidate_owned.revision.value,
                candidate_owned.integrity_hash.value[:8],
            )
            bound_snapshot = bind_snapshot_commit_hash(candidate_owned, expected_commit)
        elif snapshot is not None:
            if type(snapshot) is not WorldSnapshot:
                raise TypeError("snapshot must be WorldSnapshot or None")
            if hash_snapshot(snapshot) != snapshot.integrity_hash:
                _LOGGER.error(
                    "%s code=checkpoint_integrity_mismatch run_id=%s snapshot_id=%s",
                    EngineDiagnosticCode.CHECKPOINT_CORRUPT.value,
                    self._engine.run_id.value,
                    snapshot.snapshot_id.value,
                )
                raise ValueError("checkpoint_integrity_mismatch")
            candidate_owned = self.draft_checkpoint_from_candidate(
                candidate, snapshot_id=snapshot.snapshot_id
            )
            from dataclasses import replace as _dc_replace_caller

            caller_normalized = _dc_replace_caller(
                snapshot,
                integrity_hash=candidate_owned.integrity_hash,
                predecessor_commit_hash=None,
            )
            if not _snapshot_content_equal(caller_normalized, candidate_owned):
                _LOGGER.error(
                    "%s code=checkpoint_candidate_mismatch run_id=%s tick=%s",
                    EngineDiagnosticCode.DURABLE_FAILED.value,
                    self._engine.run_id.value,
                    candidate.tick.value,
                )
                raise ValueError("checkpoint_candidate_mismatch")
            _LOGGER.debug(
                "%s source=caller_verified run_id=%s tick=%s snapshot_id=%s "
                "hash_prefix=%s",
                EngineDiagnosticCode.CHECKPOINT_RESTORE.value,
                self._engine.run_id.value,
                candidate.tick.value,
                candidate_owned.snapshot_id.value,
                candidate_owned.integrity_hash.value[:8],
            )
            bound_snapshot = bind_snapshot_commit_hash(candidate_owned, expected_commit)
        request = TickAppendRequest(
            run_id=self._engine.run_id,
            tick=candidate.tick,
            expected_base_revision=candidate.base_revision,
            expected_predecessor_commit_hash=self._predecessor_commit_hash,
            idempotency_key=key,
            events=candidate.events,
            snapshot=bound_snapshot,
        )
        _LOGGER.debug(
            "%s run_id=%s tick=%s events=%s hash_prefix=%s",
            EngineDiagnosticCode.DURABLE_APPEND.value,
            self._engine.run_id.value,
            candidate.tick.value,
            len(candidate.events),
            expected_commit.value[:8],
        )
        existing: TickCommit | None = None
        append_started = time.perf_counter()
        try:
            existing = await self._journal.get_tick_commit(
                self._engine.run_id, candidate.tick
            )
            commit = await self._journal.append_tick(request)
        except DurableCommitAmbiguity:
            self._fence(candidate.tick, reason="ambiguous_commit")
            raise
        except Exception:
            _LOGGER.error(
                "%s code=append_failed run_id=%s tick=%s",
                EngineDiagnosticCode.DURABLE_FAILED.value,
                self._engine.run_id.value,
                candidate.tick.value,
            )
            if self._engine._snapshot is not live_before:
                self._engine._snapshot = live_before
            raise
        append_ms = (time.perf_counter() - append_started) * 1000.0
        if bound_snapshot is not None:
            _LOGGER.debug(
                "[scale.profile] component=persistence operation=snapshot_write "
                "duration_ms=%.3f count=%s",
                append_ms,
                1,
            )
        else:
            _LOGGER.debug(
                "[scale.profile] component=persistence operation=tick_append "
                "duration_ms=%.3f count=%s",
                append_ms,
                len(candidate.events),
            )

        if type(commit) is not TickCommit:
            self._fence(candidate.tick, reason="invalid_commit_type")
            raise TypeError("append_tick must return TickCommit")
        if (
            commit.run_id != self._engine.run_id
            or commit.tick != candidate.tick
            or commit.resulting_tick != candidate.result.resulting_tick
            or commit.base_revision != candidate.base_revision
            or commit.resulting_revision != candidate.resulting_revision
            or commit.event_count != len(candidate.events)
            or commit.payload_hash != tick_payload
            or commit.commit_hash != expected_commit
            or commit.predecessor_commit_hash != self._predecessor_commit_hash
        ):
            self._fence(candidate.tick, reason="divergent_commit")
            raise ValueError("durable commit content conflict")
        if existing is not None and existing.commit_hash == commit.commit_hash:
            _LOGGER.warning(
                "%s run_id=%s tick=%s hash_prefix=%s",
                EngineDiagnosticCode.DURABLE_IDEMPOTENT.value,
                self._engine.run_id.value,
                candidate.tick.value,
                commit.commit_hash.value[:8],
            )

        if self._engine._snapshot is not live_before:
            self._engine._snapshot = live_before
            self._fence(candidate.tick, reason="live_mutated_before_finalize")
            raise RuntimeError("live engine mutated before finalize")

        self._engine._finalize_tick_candidate(candidate)
        self._predecessor_commit_hash = commit.commit_hash
        _LOGGER.info(
            "%s run_id=%s tick=%s resulting_tick=%s events=%s "
            "base_revision=%s resulting_revision=%s hash_prefix=%s",
            EngineDiagnosticCode.DURABLE_COMMITTED.value,
            commit.run_id.value,
            commit.tick.value,
            commit.resulting_tick.value,
            commit.event_count,
            commit.base_revision.value,
            commit.resulting_revision.value,
            commit.commit_hash.value[:8],
        )
        return commit

    def _resolve_idempotency_key(self, tick: Tick, provided: str | None) -> str:
        if provided is not None:
            return require_stable_id("idempotency_key", provided)
        return derive_scoped_id(
            self._engine._config,
            StreamScope(
                namespace="tick-idempotency",
                names=(
                    self._engine.run_id.value,
                    self._engine.world_id.value,
                    f"tick:{tick.value}",
                ),
            ),
        )

    def _fence(self, tick: Tick, *, reason: str) -> None:
        self._fenced = True
        _LOGGER.warning(
            "%s reason=%s run_id=%s tick=%s",
            EngineDiagnosticCode.DURABLE_FENCED.value,
            reason,
            self._engine.run_id.value,
            tick.value,
        )


# Keep private candidate type referenced so accidental public re-export is obvious.
_PRIVATE_CANDIDATE_TYPE: Final[type] = _PreparedTickCandidate
