"""Trusted projection of finalized science evidence into neutral diffusion rows.

This module is composition code: it reads a finalized research boundary and its
detached objective inventory while both are in hand, then retains only typed,
non-authoritative rows. It never writes a command, mutates a ledger, or keeps a
full checkpoint or event stream across boundaries.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from analysis.science_diffusion_contract import (
    DiffusionError,
    DiffusionLane,
    DiffusionReason,
    EvidenceKind,
    EvidenceRef,
    HypothesisDescriptor,
    LaneCoverage,
    LaneCoverageState,
    ModelDescriptor,
    ScienceKind,
    ScienceVersion,
    ScienceVersionKey,
    canonical_fingerprint,
)
from simulation import (
    ObjectiveFacts,
    SimulationRunnerConfig,
    hash_world_event,
    runner_config_fingerprint,
)
from simulation.fork_checkpoint import (
    FinalizedResearchBoundary,
    FinalizedResearchOwnerSnapshot,
)
from world.artifacts import InformationArtifact
from world.events import ExperimentResolved, WorldEvent

__all__ = [
    "ArtifactSnapshot",
    "CanonicalEventPrefix",
    "ScienceBoundarySample",
    "ScienceProjection",
    "artifact_revision_observed",
    "canonical_event_prefix",
    "project_artifacts",
    "project_science_versions",
    "validate_boundary_identity",
    "verify_prefix_extension",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.science_diffusion_projection"
)

_GENERIC_OBSERVATION_TOKENS: Final[frozenset[str]] = frozenset(
    {"observation", "observed", "memory", "remembered", "none", ""}
)


@dataclass(frozen=True, slots=True)
class ArtifactSnapshot:
    """Bounded physical carrier row; never a content payload."""

    artifact_id: str
    kind: str
    author_id: str
    created_tick: int
    content_revision: int
    integrity: str
    location_id: str | None
    holder_id: str | None
    parent_artifact_id: str | None
    source_artifact_id: str | None
    copy_generation: int
    custodian_repository_id: str | None

    def __post_init__(self) -> None:
        for name in (
            "artifact_id",
            "kind",
            "author_id",
            "integrity",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
        for name in (
            "created_tick",
            "content_revision",
            "copy_generation",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
        for name in (
            "location_id",
            "holder_id",
            "parent_artifact_id",
            "source_artifact_id",
            "custodian_repository_id",
        ):
            value = getattr(self, name)
            if value is not None and (type(value) is not str or not value):
                raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)

    def key(self) -> tuple[str, int]:
        return (self.artifact_id, self.content_revision)


@dataclass(frozen=True, slots=True)
class CanonicalEventPrefix:
    """Commitment to the exact ordered committed event prefix."""

    run_id: str
    config_fingerprint: str
    boundary_tick: int
    event_count: int
    digest: str
    last_event_id: str | None

    def __post_init__(self) -> None:
        for name in ("run_id", "config_fingerprint", "digest"):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
        for name in ("boundary_tick", "event_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
        if self.last_event_id is not None and (
            type(self.last_event_id) is not str or not self.last_event_id
        ):
            raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)


@dataclass(frozen=True, slots=True)
class ScienceBoundarySample:
    """Normalized rows retained after one boundary; no event stream is kept."""

    boundary_tick: int
    boundary_revision: int
    config_fingerprint: str
    owner_ids: tuple[str, ...]
    versions: tuple[ScienceVersion, ...]
    artifacts: tuple[ArtifactSnapshot, ...]
    science_state: LaneCoverageState
    science_reason: DiffusionReason | None

    def __post_init__(self) -> None:
        for name in ("boundary_tick", "boundary_revision"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
        object.__setattr__(
            self, "owner_ids", tuple(sorted(set(self.owner_ids)))
        )


@dataclass(frozen=True, slots=True)
class ScienceProjection:
    """Science-lane projection for one finalized boundary."""

    run_id: str
    observed_boundary: int
    versions: tuple[ScienceVersion, ...]
    artifacts: tuple[ArtifactSnapshot, ...]
    coverage: LaneCoverage
    owner_ids: tuple[str, ...]
    owner_entities: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "versions",
            tuple(sorted(self.versions, key=lambda item: item.key.as_tuple())),
        )
        object.__setattr__(
            self,
            "artifacts",
            tuple(sorted(self.artifacts, key=lambda item: item.key())),
        )
        object.__setattr__(
            self,
            "owner_entities",
            tuple(sorted(self.owner_entities)),
        )

    def artifact_at(
        self, artifact_id: str, content_revision: int
    ) -> ArtifactSnapshot | None:
        for row in self.artifacts:
            if (
                row.artifact_id == artifact_id
                and row.content_revision == content_revision
            ):
                return row
        return None


def _event_hash(event: WorldEvent) -> str:
    try:
        return hash_world_event(event).value
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value) from exc


def canonical_event_prefix(
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    config_fingerprint: str,
    boundary_tick: int,
) -> CanonicalEventPrefix:
    """Hash one ordered committed prefix, including baseline events."""

    digest = hashlib.sha256(b"science-diffusion-prefix.v1\x1f")
    last_key: tuple[int, int] | None = None
    last_event_id: str | None = None
    seen: set[str] = set()
    for event in events:
        if type(event) is not WorldEvent:
            raise DiffusionError(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        if event.run_id != run_id:
            raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
        if event.tick >= boundary_tick:
            raise DiffusionError(DiffusionReason.SOURCE_NOT_PRIOR.value)
        key = (event.tick, event.sequence)
        if last_key is not None and key <= last_key:
            raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
        if event.event_id.value in seen:
            raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
        seen.add(event.event_id.value)
        last_key = key
        last_event_id = event.event_id.value
        digest.update(_event_hash(event).encode("ascii"))
        digest.update(b"\x1e")
    return CanonicalEventPrefix(
        run_id=run_id,
        config_fingerprint=config_fingerprint,
        boundary_tick=boundary_tick,
        event_count=len(events),
        digest=digest.hexdigest(),
        last_event_id=last_event_id,
    )


def verify_prefix_extension(
    prior: CanonicalEventPrefix,
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    config_fingerprint: str,
    boundary_tick: int,
) -> CanonicalEventPrefix:
    """Require the new prefix to extend the prior one without rewriting it."""

    if prior.run_id != run_id or prior.config_fingerprint != config_fingerprint:
        raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
    if boundary_tick <= prior.boundary_tick:
        raise DiffusionError(DiffusionReason.SOURCE_NOT_PRIOR.value)
    if boundary_tick > prior.boundary_tick + 1:
        raise DiffusionError(DiffusionReason.COVERAGE_GAP.value)
    if len(events) < prior.event_count:
        raise DiffusionError(DiffusionReason.COVERAGE_GAP.value)
    recomputed = canonical_event_prefix(
        events[: prior.event_count],
        run_id=run_id,
        config_fingerprint=config_fingerprint,
        boundary_tick=prior.boundary_tick,
    )
    if (
        recomputed.event_count != prior.event_count
        or recomputed.digest != prior.digest
    ):
        raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
    current = canonical_event_prefix(
        events,
        run_id=run_id,
        config_fingerprint=config_fingerprint,
        boundary_tick=boundary_tick,
    )
    if prior.last_event_id is not None and current.last_event_id is None:
        raise DiffusionError(DiffusionReason.COVERAGE_GAP.value)
    return current


def _owner_maps(
    boundary: FinalizedResearchBoundary, inventory: ObjectiveFacts
) -> tuple[
    tuple[FinalizedResearchOwnerSnapshot, ...],
    tuple[tuple[str, str], ...],
]:
    if boundary.run_id.value != inventory.run_id:
        raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
    if boundary.boundary_tick.value != inventory.tick:
        raise DiffusionError(DiffusionReason.COVERAGE_GAP.value)
    if boundary.boundary_revision.value != inventory.revision:
        raise DiffusionError(DiffusionReason.COVERAGE_GAP.value)
    owners = tuple(sorted(boundary.owners, key=lambda row: row.owner_id.value))
    if len({row.owner_id for row in owners}) != len(owners):
        raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
    registrations = tuple(
        sorted(inventory.registrations, key=lambda row: row.agent_id.value)
    )
    if len(registrations) != len(owners):
        raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
    by_owner = {row.owner_id.value: row for row in owners}
    entities: list[tuple[str, str]] = []
    seen_entities: set[str] = set()
    for registration in registrations:
        owner = by_owner.get(registration.agent_id.value)
        if owner is None or owner.entity_id != registration.entity_id:
            raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
        entity = registration.entity_id.value
        if entity in seen_entities:
            raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
        seen_entities.add(entity)
        entities.append((registration.agent_id.value, entity))
    return owners, tuple(entities)


def validate_boundary_identity(
    boundary: FinalizedResearchBoundary,
    inventory: ObjectiveFacts,
    config: SimulationRunnerConfig,
) -> tuple[tuple[FinalizedResearchOwnerSnapshot, ...], tuple[tuple[str, str], ...]]:
    """Validate one boundary/inventory pairing against the runner config."""

    if type(boundary) is not FinalizedResearchBoundary:
        raise DiffusionError(DiffusionReason.UNSUPPORTED_SCHEMA.value)
    if type(inventory) is not ObjectiveFacts:
        raise DiffusionError(DiffusionReason.UNSUPPORTED_SCHEMA.value)
    if type(config) is not SimulationRunnerConfig:
        raise DiffusionError(DiffusionReason.UNSUPPORTED_SCHEMA.value)
    if boundary.config_fingerprint != runner_config_fingerprint(config):
        raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
    return _owner_maps(boundary, inventory)


def project_artifacts(inventory: ObjectiveFacts) -> tuple[ArtifactSnapshot, ...]:
    """Project exact physical carrier revisions from one detached inventory."""

    rows: list[ArtifactSnapshot] = []
    for artifact in inventory.artifacts:
        if type(artifact) is not InformationArtifact:
            raise DiffusionError(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        rows.append(
            ArtifactSnapshot(
                artifact_id=artifact.artifact_id.value,
                kind=artifact.kind.value,
                author_id=artifact.author_id.value,
                created_tick=artifact.created_tick,
                content_revision=artifact.content_revision,
                integrity=artifact.integrity.value,
                location_id=(
                    artifact.location_id.value
                    if artifact.location_id is not None
                    else None
                ),
                holder_id=(
                    artifact.holder_id.value
                    if artifact.holder_id is not None
                    else None
                ),
                parent_artifact_id=(
                    artifact.parent_artifact_id.value
                    if artifact.parent_artifact_id is not None
                    else None
                ),
                source_artifact_id=(
                    artifact.source_artifact_id.value
                    if artifact.source_artifact_id is not None
                    else None
                ),
                copy_generation=artifact.copy_generation,
                custodian_repository_id=(
                    artifact.custodian_repository_id.value
                    if artifact.custodian_repository_id is not None
                    else None
                ),
            )
        )
    return tuple(sorted(rows, key=lambda item: item.key()))


def artifact_revision_observed(
    artifacts: Iterable[ArtifactSnapshot],
    artifact_id: str,
    content_revision: int,
) -> bool:
    """Return whether the exact declared revision is visible at this boundary."""

    return any(
        row.artifact_id == artifact_id and row.content_revision == content_revision
        for row in artifacts
    )


def _entity_kinds(inventory: ObjectiveFacts) -> dict[str, str]:
    kinds: dict[str, str] = {}
    for resource in inventory.resources:
        kinds[resource.entity_id.value] = "resource"
    for item in inventory.items:
        kinds[item.entity_id.value] = "item"
    for artifact in inventory.artifacts:
        kinds[artifact.artifact_id.value] = "artifact"
    for structure in inventory.structures:
        kinds[structure.entity_id.value] = "structure"
    for registration in inventory.registrations:
        kinds[registration.entity_id.value] = "agent"
    return kinds


def _typed_entity_ref(value: str, kinds: Mapping[str, str]) -> str:
    kind = kinds.get(value)
    if kind is None:
        return f"entity:{value}"
    return f"{kind}:{value}"


def _deliberate_trials(
    ledger: Any,
) -> dict[str, tuple[tuple[int, str], ...]]:
    trials: dict[str, list[tuple[int, str]]] = {}
    for trial in ledger.trials:
        if trial.discovery_mode != "deliberate" or not trial.hypothesis_id:
            continue
        trials.setdefault(trial.hypothesis_id, []).append(
            (trial.tick, trial.event_id)
        )
    return {
        key: tuple(sorted(values)) for key, values in sorted(trials.items())
    }


def _hypothesis_root(
    hypothesis: Any,
    revision: Any,
    *,
    trials: Mapping[str, tuple[tuple[int, str], ...]],
) -> tuple[str, str]:
    explicit = trials.get(hypothesis.hypothesis_id, ())
    for tick, event_id in explicit:
        if tick <= revision.tick:
            return ("experiment", event_id)
    source_kind = hypothesis.source_kind
    token = hypothesis.source_token
    if (
        getattr(source_kind, "value", source_kind) == "communicated"
        and token.startswith("evt:")
    ):
        return ("communicated", token)
    if (
        getattr(source_kind, "value", source_kind) == "recorded"
        and token not in _GENERIC_OBSERVATION_TOKENS
    ):
        return ("recorded", token)
    if (
        getattr(source_kind, "value", source_kind) == "observed"
        and token not in _GENERIC_OBSERVATION_TOKENS
    ):
        return ("observation", token)
    if (
        getattr(source_kind, "value", source_kind) == "self_formulated"
        and getattr(revision.reason, "value", revision.reason) == "formulated"
    ):
        return ("self_formulated", f"hypothesis:{hypothesis.hypothesis_id}")
    return ("", "")


def _hypothesis_descriptor(
    hypothesis: Any,
    revision: Any,
    *,
    kinds: Mapping[str, str],
) -> HypothesisDescriptor:
    conditions = revision.conditions or hypothesis.conditions
    operands = [_typed_entity_ref(revision.claim.operand_a_id, kinds)]
    if revision.claim.operand_b_id is not None:
        operands.append(_typed_entity_ref(revision.claim.operand_b_id, kinds))
    return HypothesisDescriptor(
        operator=revision.claim.operator.value,
        operand_refs=tuple(operands),
        process=revision.claim.process_token.value,
        predicted_outcome=(
            revision.claim.predicted_outcome.value
            if revision.claim.predicted_outcome is not None
            else None
        ),
        conditions=tuple(
            sorted(
                (condition.slot.value, condition.value_token)
                for condition in conditions
            )
        ),
    )


def _hypothesis_wire(
    hypothesis: Any, revision: Any
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                ("reason", revision.reason.value),
                ("source_kind", hypothesis.source_kind.value),
                ("source_token", hypothesis.source_token),
                ("status", hypothesis.status.value if hypothesis.status else "unknown"),
                ("confidence", str(revision.confidence_milli)),
                ("evidence_ref", revision.evidence_ref or "none"),
            )
        )
    )


def _model_target_ref(model: Any) -> str:
    if ":" in model.target_ref:
        return str(model.target_ref)
    return str(f"{model.target_kind.value}:{model.target_ref}")


def _model_descriptor(
    model: Any, revision: Any
) -> ModelDescriptor:
    conditions = tuple(
        sorted(
            (condition.slot, condition.value_token)
            for condition in revision.conditions
        )
    )
    parameter_digest = revision.parameter_digest
    parameter_scope = ""
    if parameter_digest:
        parameter_scope = canonical_fingerprint(
            "model-parameter-scope",
            {
                "target_kind": model.target_kind.value,
                "target_ref": _model_target_ref(model),
                "unit": model.unit_token,
                "horizon": model.horizon_ticks,
                "variant": model.predictor_variant.value,
                "conditions": [list(item) for item in conditions],
            },
        )
    return ModelDescriptor(
        target_kind=model.target_kind.value,
        target_ref=_model_target_ref(model),
        unit=model.unit_token,
        horizon=model.horizon_ticks,
        variant=model.predictor_variant.value,
        conditions=conditions,
        predicted_class=revision.predicted_class,
        parameter_digest=parameter_digest,
        parameter_scope=parameter_scope,
    )


def _model_wire(
    model: Any,
    revision: Any,
    hypothesis: Any | None,
    *,
    case_count: int,
    observed_count: int,
    latest_case_ref: str,
) -> tuple[tuple[str, str], ...]:
    source_kind = "unknown" if hypothesis is None else hypothesis.source_kind.value
    return tuple(
        sorted(
            (
                ("reason", revision.reason.value),
                ("lifecycle", model.lifecycle.value),
                ("source_kind", source_kind),
                ("source_revision_ref", revision.source_revision_ref or "none"),
                ("predictor_variant", model.predictor_variant.value),
                ("prediction_cases", str(case_count)),
                ("observed_cases", str(observed_count)),
                ("latest_case_ref", latest_case_ref or "none"),
            )
        )
    )


def _model_root(
    model: Any, hypothesis: Any | None
) -> tuple[str, str]:
    if hypothesis is None or not hypothesis.source_refs:
        return ("", "")
    if hypothesis.source_kind.value == "experiment_hypothesis":
        return ("experiment_hypothesis", hypothesis.source_refs[0])
    if hypothesis.source_kind.value == "observed_regularity":
        return ("observation_source", hypothesis.source_refs[0])
    return ("", "")


def project_science_versions(
    boundary: FinalizedResearchBoundary,
    inventory: ObjectiveFacts,
    config: SimulationRunnerConfig,
    *,
    known: Iterable[ScienceVersion] = (),
    observed_boundary: int | None = None,
    events: Sequence[WorldEvent] | None = None,
) -> ScienceProjection:
    """Project first-seen hypothesis/model revisions and exact carriers.

    Existing qualified rows are immutable: a later boundary may not rewrite an
    earlier version's content. Missing owner ledgers make only the science lane
    partial; objective rows from the valid stream remain usable.
    """

    owners, owner_entities = validate_boundary_identity(boundary, inventory, config)
    observed = (
        boundary.boundary_tick.value
        if observed_boundary is None
        else observed_boundary
    )
    if isinstance(observed, bool) or type(observed) is not int or observed < 0:
        raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
    known_by_key = {item.key: item for item in known}
    kinds = _entity_kinds(inventory)
    run_id = boundary.run_id.value
    versions: list[ScienceVersion] = []
    missing_ledgers = 0
    owners_with_science = 0

    for owner in owners:
        checkpoint = owner.runtime_checkpoint
        if checkpoint is None:
            missing_ledgers += 1
            continue
        experiment_ledger = getattr(checkpoint, "experiment_ledger", None)
        model_ledger = getattr(checkpoint, "scientific_model_ledger", None)
        if experiment_ledger is not None:
            owners_with_science += 1
        if experiment_ledger is not None:
            if not hasattr(experiment_ledger, "hypotheses"):
                missing_ledgers += 1
            elif getattr(experiment_ledger, "owner_id", None) != owner.owner_id:
                raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
            else:
                trials = _deliberate_trials(experiment_ledger)
                for hypothesis in experiment_ledger.hypotheses:
                    versions.extend(
                        _project_hypothesis(
                            hypothesis,
                            owner=owner,
                            run_id=run_id,
                            observed=observed,
                            known=known_by_key,
                            trials=trials,
                            kinds=kinds,
                        )
                    )
        if model_ledger is not None:
            if not hasattr(model_ledger, "models"):
                missing_ledgers += 1
            elif getattr(model_ledger, "owner_id", None) != owner.owner_id:
                raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
            else:
                cases_by_model = _cases_by_model(model_ledger)
                hypotheses_by_id = {
                    row.hypothesis_id: row for row in model_ledger.hypotheses
                }
                for model in model_ledger.models:
                    versions.extend(
                        _project_model(
                            model,
                            hypothesis=hypotheses_by_id.get(model.hypothesis_id),
                            owner=owner,
                            run_id=run_id,
                            observed=observed,
                            known=known_by_key,
                            cases=cases_by_model.get(model.model_id, ()),
                        )
                    )

    science_state = LaneCoverageState.COMPLETE
    science_reason: DiffusionReason | None = None
    if missing_ledgers:
        science_state = LaneCoverageState.PARTIAL
        science_reason = DiffusionReason.COVERAGE_GAP
    elif owners and owners_with_science == 0:
        science_state = LaneCoverageState.UNAVAILABLE
        science_reason = DiffusionReason.COVERAGE_GAP
    end = observed if observed > 0 else 1
    coverage = LaneCoverage(
        lane=DiffusionLane.SCIENCE,
        start_tick=0,
        end_tick_exclusive=end,
        state=science_state,
        observed=len(versions),
        reason=science_reason,
    )
    return ScienceProjection(
        run_id=run_id,
        observed_boundary=observed,
        versions=tuple(versions),
        artifacts=project_artifacts(inventory),
        coverage=coverage,
        owner_ids=tuple(row.owner_id.value for row in owners),
        owner_entities=owner_entities,
    )


def _project_hypothesis(
    hypothesis: Any,
    *,
    owner: FinalizedResearchOwnerSnapshot,
    run_id: str,
    observed: int,
    known: Mapping[ScienceVersionKey, ScienceVersion],
    trials: Mapping[str, tuple[tuple[int, str], ...]],
    kinds: Mapping[str, str],
) -> list[ScienceVersion]:
    if hypothesis.owner_id != owner.owner_id:
        raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
    rows: list[ScienceVersion] = []
    for revision in hypothesis.revisions:
        key = ScienceVersionKey(
            run_id=run_id,
            owner_id=owner.owner_id.value,
            kind=ScienceKind.HYPOTHESIS,
            local_id=hypothesis.hypothesis_id,
            revision_index=revision.revision_index,
        )
        candidate = ScienceVersion(
            key=key,
            occurrence_tick=revision.tick,
            first_observed_boundary=max(observed, revision.tick),
            wire=_hypothesis_wire(hypothesis, revision),
            hypothesis=_hypothesis_descriptor(hypothesis, revision, kinds=kinds),
            evidence=EvidenceRef(
                kind=EvidenceKind.OWNER_ROW,
                run_id=run_id,
                tick=revision.tick,
                owner_id=owner.owner_id.value,
                local_id=hypothesis.hypothesis_id,
                revision_index=revision.revision_index,
            ),
            root_kind=_hypothesis_root(hypothesis, revision, trials=trials)[0],
            root_ref=_hypothesis_root(hypothesis, revision, trials=trials)[1],
        )
        rows.append(_merge_known(candidate, known))
    return rows


def _cases_by_model(
    ledger: Any,
) -> dict[str, tuple[tuple[str, bool], ...]]:
    rows: dict[str, list[tuple[str, bool]]] = {}
    for case in ledger.cases:
        for prediction in case.predictions:
            rows.setdefault(prediction.model_id, []).append(
                (case.case_id, case.observed is not None)
            )
    return {key: tuple(sorted(values)) for key, values in rows.items()}


def _project_model(
    model: Any,
    *,
    hypothesis: Any | None,
    owner: FinalizedResearchOwnerSnapshot,
    run_id: str,
    observed: int,
    known: Mapping[ScienceVersionKey, ScienceVersion],
    cases: tuple[tuple[str, bool], ...],
) -> list[ScienceVersion]:
    if model.owner_id != owner.owner_id:
        raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
    latest_case_ref = cases[-1][0] if cases else ""
    observed_count = sum(1 for _, done in cases if done)
    root_kind, root_ref = _model_root(model, hypothesis)
    rows: list[ScienceVersion] = []
    for revision in model.revisions:
        key = ScienceVersionKey(
            run_id=run_id,
            owner_id=owner.owner_id.value,
            kind=ScienceKind.MODEL,
            local_id=model.model_id,
            revision_index=revision.revision_index,
        )
        candidate = ScienceVersion(
            key=key,
            occurrence_tick=revision.tick,
            first_observed_boundary=max(observed, revision.tick),
            wire=_model_wire(
                model,
                revision,
                hypothesis,
                case_count=len(cases),
                observed_count=observed_count,
                latest_case_ref=latest_case_ref,
            ),
            model=_model_descriptor(model, revision),
            evidence=EvidenceRef(
                kind=EvidenceKind.OWNER_ROW,
                run_id=run_id,
                tick=revision.tick,
                owner_id=owner.owner_id.value,
                local_id=model.model_id,
                revision_index=revision.revision_index,
            ),
            root_kind=root_kind,
            root_ref=root_ref,
        )
        rows.append(_merge_known(candidate, known))
    return rows


def _merge_known(
    candidate: ScienceVersion,
    known: Mapping[ScienceVersionKey, ScienceVersion],
) -> ScienceVersion:
    prior = known.get(candidate.key)
    if prior is None:
        return candidate
    if prior.content_fingerprint() != candidate.content_fingerprint():
        _LOG.warning(
            "science_diffusion_version_conflict run_id=%s kind=%s revision=%s",
            candidate.key.run_id,
            candidate.key.kind.value,
            candidate.key.revision_index,
        )
        raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
    return prior


def project_experiment_roots(events: Sequence[WorldEvent]) -> tuple[str, ...]:
    """Return exact deliberate experiment event IDs in committed order."""

    roots: list[str] = []
    for event in events:
        details = event.details
        if (
            isinstance(details, ExperimentResolved)
            and details.discovery_mode == "deliberate"
        ):
            roots.append(event.event_id.value)
    return tuple(roots)
