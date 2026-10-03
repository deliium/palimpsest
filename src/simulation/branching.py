"""Research simulation branching contracts (forks), not agent counterfactuals.

Research forks create a new durable ``run_id`` under an explicit
``ResearchIntervention``. Agent-generated imagination lives in
``agents.cognition.counterfactual`` / ``prospective``
(``CounterfactualScenario``, ``ImaginedFuture``) and must not be reused here.
Cross-imports that treat a research fork as an imagined alternative (or the
reverse) are forbidden.

Logging terms: ``research_fork`` / ``research_intervention`` versus
``counterfactual_scenario`` / ``prospective_rollout``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final

from simulation.clock import require_exact_nonneg_int
from simulation.models import RunId, StochasticIdentity, require_stochastic_identity
from simulation.runner_models import (
    CognitiveBudgetLimits,
    CognitiveBudgetMode,
    MemoryMode,
    MortalityMode,
)
from world.identifiers import require_stable_id

__all__ = [
    "INHERIT_SEED_STREAM_TOKEN",
    "RESEARCH_INTERVENTION_REASON_CODES",
    "BeliefPatchPayload",
    "BranchCreateRequest",
    "BranchCreateResult",
    "BranchError",
    "BranchLineage",
    "BranchTimelineCompareRequest",
    "BranchTimelineCompareResult",
    "CommunicationRemoveTarget",
    "InMemoryBranchLineageRepository",
    "ResearchIntervention",
    "ResearchInterventionKind",
    "SeedStreamPolicy",
    "canonical_intervention_document",
    "decode_branch_lineage",
    "encode_branch_lineage",
    "intervention_fingerprint",
    "intervention_summary",
    "resolve_idempotent_create",
    "seed_stream_token_for_intervention",
    "validate_branch_create_request",
    "validate_research_intervention",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.branching")

INHERIT_SEED_STREAM_TOKEN: Final[str] = "inherit"

RESEARCH_INTERVENTION_REASON_CODES: Final[frozenset[str]] = frozenset(
    {
        "invalid_intervention",
        "intervention_past_event",
        "belief_not_found",
        "architecture_unknown",
        "fork_tick_ahead_of_head",
        "branch_identity_conflict",
        "branch_root",
        "subjective_clone_incomplete",
        "unknown_parent",
        "multiple_interventions",
        "empty_patch",
    }
)

_MEMORY_MODE_VALUES: Final[frozenset[str]] = frozenset(m.value for m in MemoryMode)
_BUDGET_MODE_VALUES: Final[frozenset[str]] = frozenset(
    m.value for m in CognitiveBudgetMode
)
_VALUE_KINDS: Final[frozenset[str]] = frozenset(
    {"bool", "number", "text", "agent", "entity"}
)
_SUBJECT_KINDS: Final[frozenset[str]] = frozenset({"agent", "entity", "self"})


class BranchError(ValueError):
    """Fail-closed branching error with a stable ``reason_code``."""

    def __init__(self, reason_code: str, message: str | None = None) -> None:
        if not isinstance(reason_code, str) or not reason_code:
            raise TypeError("BranchError.reason_code must be a non-empty str")
        self.reason_code = reason_code
        super().__init__(message if message is not None else reason_code)


class ResearchInterventionKind(StrEnum):
    """Closed catalog of research-only fork interventions (exactly one per fork)."""

    MEMORY_ARCHITECTURE = "memory_architecture"
    BELIEF_PATCH = "belief_patch"
    COMMUNICATION_REMOVE = "communication_remove"
    MORTALITY_DISABLED = "mortality_disabled"
    COGNITIVE_BUDGET = "cognitive_budget"
    AGENT_ARCHITECTURE = "agent_architecture"
    ALTERNATE_SEED_STREAM = "alternate_seed_stream"


class SeedStreamPolicy(StrEnum):
    """Whether the child inherits the parent objective stream or uses an alternate."""

    INHERIT = "inherit"
    ALTERNATE = "alternate"


@dataclass(frozen=True, slots=True)
class BeliefPatchPayload:
    """Closed belief revision applied only on the child subjective clone."""

    owner_id: str
    belief_id: str
    subject_kind: str
    subject_id: str
    predicate: str
    value_kind: str
    bool_value: bool | None = None
    number_value: float | None = None
    text_value: str | None = None
    agent_value: str | None = None
    entity_value: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("BeliefPatchPayload.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "belief_id",
            require_stable_id("BeliefPatchPayload.belief_id", self.belief_id),
        )
        if self.subject_kind not in _SUBJECT_KINDS:
            raise BranchError("invalid_intervention", "unknown subject_kind")
        object.__setattr__(
            self,
            "subject_id",
            require_stable_id("BeliefPatchPayload.subject_id", self.subject_id),
        )
        if not isinstance(self.predicate, str) or not self.predicate.strip():
            raise BranchError("empty_patch", "predicate required")
        object.__setattr__(self, "predicate", self.predicate.strip())
        if self.value_kind not in _VALUE_KINDS:
            raise BranchError("invalid_intervention", "unknown value_kind")
        _validate_belief_value_fields(self)


def _validate_belief_value_fields(payload: BeliefPatchPayload) -> None:
    kind = payload.value_kind
    if kind == "bool":
        if type(payload.bool_value) is not bool:
            raise BranchError("invalid_intervention", "bool_value required")
        if any(
            v is not None
            for v in (
                payload.number_value,
                payload.text_value,
                payload.agent_value,
                payload.entity_value,
            )
        ):
            raise BranchError("invalid_intervention", "unexpected value fields")
    elif kind == "number":
        if payload.number_value is None or isinstance(payload.number_value, bool):
            raise BranchError("invalid_intervention", "number_value required")
        if not isinstance(payload.number_value, (int, float)):
            raise BranchError("invalid_intervention", "number_value required")
        if any(
            v is not None
            for v in (
                payload.bool_value,
                payload.text_value,
                payload.agent_value,
                payload.entity_value,
            )
        ):
            raise BranchError("invalid_intervention", "unexpected value fields")
    elif kind == "text":
        if not isinstance(payload.text_value, str) or not payload.text_value:
            raise BranchError("empty_patch", "text_value required")
        if any(
            v is not None
            for v in (
                payload.bool_value,
                payload.number_value,
                payload.agent_value,
                payload.entity_value,
            )
        ):
            raise BranchError("invalid_intervention", "unexpected value fields")
    elif kind == "agent":
        if payload.agent_value is None:
            raise BranchError("invalid_intervention", "agent_value required")
        require_stable_id("BeliefPatchPayload.agent_value", payload.agent_value)
        if any(
            v is not None
            for v in (
                payload.bool_value,
                payload.number_value,
                payload.text_value,
                payload.entity_value,
            )
        ):
            raise BranchError("invalid_intervention", "unexpected value fields")
    elif kind == "entity":
        if payload.entity_value is None:
            raise BranchError("invalid_intervention", "entity_value required")
        require_stable_id("BeliefPatchPayload.entity_value", payload.entity_value)
        if any(
            v is not None
            for v in (
                payload.bool_value,
                payload.number_value,
                payload.text_value,
                payload.agent_value,
            )
        ):
            raise BranchError("invalid_intervention", "unexpected value fields")


@dataclass(frozen=True, slots=True)
class CommunicationRemoveTarget:
    """Parent communication locator that must lie at or after the fork tick."""

    event_id: str | None = None
    tick: int | None = None
    sequence: int | None = None

    def __post_init__(self) -> None:
        has_event = self.event_id is not None
        has_coord = self.tick is not None or self.sequence is not None
        if has_event == has_coord:
            # Exactly one locator form: event_id XOR (tick, sequence).
            if has_event and has_coord:
                raise BranchError(
                    "invalid_intervention",
                    "communication target must be event_id or tick/sequence",
                )
            raise BranchError(
                "invalid_intervention",
                "communication target requires event_id or tick/sequence",
            )
        if has_event:
            object.__setattr__(
                self,
                "event_id",
                require_stable_id(
                    "CommunicationRemoveTarget.event_id", self.event_id
                ),
            )
            return
        tick = require_exact_nonneg_int("CommunicationRemoveTarget.tick", self.tick)
        sequence = require_exact_nonneg_int(
            "CommunicationRemoveTarget.sequence", self.sequence
        )
        object.__setattr__(self, "tick", tick)
        object.__setattr__(self, "sequence", sequence)


@dataclass(frozen=True, slots=True)
class ResearchIntervention:
    """Exactly one closed research change applied to a child run only."""

    kind: ResearchInterventionKind
    agent_ids: tuple[str, ...] = ()
    memory_mode: MemoryMode | None = None
    belief_patch: BeliefPatchPayload | None = None
    communication_remove: CommunicationRemoveTarget | None = None
    mortality_mode: MortalityMode | None = None
    cognitive_budget_mode: CognitiveBudgetMode | None = None
    cognitive_budget_limits: CognitiveBudgetLimits | None = None
    architecture_id: str | None = None
    alternate_stochastic_identity: StochasticIdentity | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not ResearchInterventionKind:
            raise BranchError("invalid_intervention", "unknown intervention kind")
        agents = tuple(
            require_stable_id("ResearchIntervention.agent_ids", agent_id)
            for agent_id in self.agent_ids
        )
        if len(set(agents)) != len(agents):
            raise BranchError("invalid_intervention", "duplicate agent_ids")
        object.__setattr__(self, "agent_ids", agents)
        if self.alternate_stochastic_identity is not None:
            object.__setattr__(
                self,
                "alternate_stochastic_identity",
                require_stochastic_identity(self.alternate_stochastic_identity),
            )


@dataclass(frozen=True, slots=True)
class BranchLineage:
    """Control-plane genealogy linking a child run to its immutable parent."""

    child_run_id: RunId
    parent_run_id: RunId
    fork_tick: int
    intervention_kind: ResearchInterventionKind
    intervention_fingerprint: str
    intervention_canonical: Mapping[str, Any]
    branch_id: str
    created_as_of_parent_head: int

    def __post_init__(self) -> None:
        if type(self.child_run_id) is not RunId:
            raise TypeError("BranchLineage.child_run_id must be RunId")
        if type(self.parent_run_id) is not RunId:
            raise TypeError("BranchLineage.parent_run_id must be RunId")
        object.__setattr__(
            self,
            "fork_tick",
            require_exact_nonneg_int("BranchLineage.fork_tick", self.fork_tick),
        )
        if type(self.intervention_kind) is not ResearchInterventionKind:
            raise TypeError(
                "BranchLineage.intervention_kind must be ResearchInterventionKind"
            )
        if (
            not isinstance(self.intervention_fingerprint, str)
            or len(self.intervention_fingerprint) != 64
        ):
            raise ValueError(
                "BranchLineage.intervention_fingerprint must be sha256 hex"
            )
        object.__setattr__(
            self,
            "branch_id",
            require_stable_id("BranchLineage.branch_id", self.branch_id),
        )
        object.__setattr__(
            self,
            "created_as_of_parent_head",
            require_exact_nonneg_int(
                "BranchLineage.created_as_of_parent_head",
                self.created_as_of_parent_head,
            ),
        )
        if not isinstance(self.intervention_canonical, Mapping):
            raise TypeError("BranchLineage.intervention_canonical must be a mapping")
        object.__setattr__(
            self,
            "intervention_canonical",
            MappingProxyType(dict(self.intervention_canonical)),
        )


@dataclass(frozen=True, slots=True)
class BranchCreateRequest:
    """Create exactly one research fork from a parent run cursor."""

    parent_run_id: RunId
    fork_tick: int
    intervention: ResearchIntervention

    def __post_init__(self) -> None:
        if type(self.parent_run_id) is not RunId:
            raise TypeError("BranchCreateRequest.parent_run_id must be RunId")
        object.__setattr__(
            self,
            "fork_tick",
            require_exact_nonneg_int("BranchCreateRequest.fork_tick", self.fork_tick),
        )
        if type(self.intervention) is not ResearchIntervention:
            raise TypeError(
                "BranchCreateRequest.intervention must be ResearchIntervention"
            )


@dataclass(frozen=True, slots=True)
class BranchCreateResult:
    """Outcome of a fork create, including idempotent hits."""

    child_run_id: RunId
    branch_id: str
    lineage: BranchLineage
    idempotent_hit: bool

    def __post_init__(self) -> None:
        if type(self.child_run_id) is not RunId:
            raise TypeError("BranchCreateResult.child_run_id must be RunId")
        object.__setattr__(
            self,
            "branch_id",
            require_stable_id("BranchCreateResult.branch_id", self.branch_id),
        )
        if type(self.lineage) is not BranchLineage:
            raise TypeError("BranchCreateResult.lineage must be BranchLineage")
        if type(self.idempotent_hit) is not bool:
            raise TypeError("BranchCreateResult.idempotent_hit must be bool")


@dataclass(frozen=True, slots=True)
class BranchTimelineCompareRequest:
    """Compare two run journals that share (or claim) a fork relationship."""

    left_run_id: RunId
    right_run_id: RunId
    fork_tick: int | None = None
    include_event_kind_counts: bool = False

    def __post_init__(self) -> None:
        if type(self.left_run_id) is not RunId:
            raise TypeError("BranchTimelineCompareRequest.left_run_id must be RunId")
        if type(self.right_run_id) is not RunId:
            raise TypeError("BranchTimelineCompareRequest.right_run_id must be RunId")
        if self.fork_tick is not None:
            object.__setattr__(
                self,
                "fork_tick",
                require_exact_nonneg_int(
                    "BranchTimelineCompareRequest.fork_tick", self.fork_tick
                ),
            )
        if type(self.include_event_kind_counts) is not bool:
            raise TypeError(
                "BranchTimelineCompareRequest.include_event_kind_counts must be bool"
            )


@dataclass(frozen=True, slots=True)
class BranchTimelineCompareResult:
    """Payload-equivalent prefix check plus first post-fork divergence."""

    left_run_id: RunId
    right_run_id: RunId
    fork_tick: int
    prefix_equivalent: bool
    diverge_tick: int | None
    diverge_sequence: int | None
    reason_code: str | None
    left_post_fork_trajectory_hash: str | None
    right_post_fork_trajectory_hash: str | None
    event_kind_counts: Mapping[str, Mapping[str, int]] | None = None

    def __post_init__(self) -> None:
        if type(self.left_run_id) is not RunId:
            raise TypeError("BranchTimelineCompareResult.left_run_id must be RunId")
        if type(self.right_run_id) is not RunId:
            raise TypeError("BranchTimelineCompareResult.right_run_id must be RunId")
        object.__setattr__(
            self,
            "fork_tick",
            require_exact_nonneg_int(
                "BranchTimelineCompareResult.fork_tick", self.fork_tick
            ),
        )
        if type(self.prefix_equivalent) is not bool:
            raise TypeError(
                "BranchTimelineCompareResult.prefix_equivalent must be bool"
            )
        if self.event_kind_counts is not None:
            object.__setattr__(
                self,
                "event_kind_counts",
                MappingProxyType(
                    {
                        str(side): MappingProxyType(
                            {str(k): int(v) for k, v in counts.items()}
                        )
                        for side, counts in self.event_kind_counts.items()
                    }
                ),
            )


def _reject(reason_code: str, detail: str | None = None) -> None:
    _LOG.error(
        "research_intervention_rejected reason_code=%s",
        reason_code,
    )
    raise BranchError(reason_code, detail)


def _require_agents(intervention: ResearchIntervention) -> None:
    if not intervention.agent_ids:
        _reject("invalid_intervention", "agent_ids required")


def _assert_only(
    intervention: ResearchIntervention,
    *,
    allowed: frozenset[str],
) -> None:
    present: dict[str, bool] = {
        "memory_mode": intervention.memory_mode is not None,
        "belief_patch": intervention.belief_patch is not None,
        "communication_remove": intervention.communication_remove is not None,
        "mortality_mode": intervention.mortality_mode is not None,
        "cognitive_budget_mode": intervention.cognitive_budget_mode is not None,
        "cognitive_budget_limits": intervention.cognitive_budget_limits is not None,
        "architecture_id": intervention.architecture_id is not None,
        "alternate_stochastic_identity": (
            intervention.alternate_stochastic_identity is not None
        ),
        "agent_ids": bool(intervention.agent_ids),
    }
    for field_name, is_set in present.items():
        if is_set and field_name not in allowed:
            _reject("invalid_intervention", f"unexpected field {field_name}")


def validate_research_intervention(
    intervention: ResearchIntervention,
) -> ResearchIntervention:
    """Validate exact key-set for one closed intervention kind."""
    if type(intervention) is not ResearchIntervention:
        _reject("invalid_intervention", "expected ResearchIntervention")
    kind = intervention.kind
    try:
        if kind is ResearchInterventionKind.MEMORY_ARCHITECTURE:
            _assert_only(
                intervention,
                allowed=frozenset({"agent_ids", "memory_mode"}),
            )
            _require_agents(intervention)
            if type(intervention.memory_mode) is not MemoryMode:
                _reject("invalid_intervention", "memory_mode required")
            if intervention.memory_mode.value not in _MEMORY_MODE_VALUES:
                _reject("invalid_intervention", "unknown memory_mode")
        elif kind is ResearchInterventionKind.BELIEF_PATCH:
            _assert_only(
                intervention,
                allowed=frozenset({"belief_patch"}),
            )
            if type(intervention.belief_patch) is not BeliefPatchPayload:
                _reject("empty_patch", "belief_patch required")
        elif kind is ResearchInterventionKind.COMMUNICATION_REMOVE:
            _assert_only(
                intervention,
                allowed=frozenset({"communication_remove"}),
            )
            if type(intervention.communication_remove) is not CommunicationRemoveTarget:
                _reject("invalid_intervention", "communication_remove required")
        elif kind is ResearchInterventionKind.MORTALITY_DISABLED:
            _assert_only(
                intervention,
                allowed=frozenset({"mortality_mode"}),
            )
            mode = intervention.mortality_mode
            if mode is None:
                mode = MortalityMode.DISABLED
                object.__setattr__(intervention, "mortality_mode", mode)
            if mode is not MortalityMode.DISABLED:
                _reject("invalid_intervention", "mortality must be disabled")
        elif kind is ResearchInterventionKind.COGNITIVE_BUDGET:
            _assert_only(
                intervention,
                allowed=frozenset(
                    {"agent_ids", "cognitive_budget_mode", "cognitive_budget_limits"}
                ),
            )
            _require_agents(intervention)
            if type(intervention.cognitive_budget_mode) is not CognitiveBudgetMode:
                _reject("invalid_intervention", "cognitive_budget_mode required")
            if intervention.cognitive_budget_mode.value not in _BUDGET_MODE_VALUES:
                _reject("invalid_intervention", "unknown cognitive_budget_mode")
            if intervention.cognitive_budget_mode is CognitiveBudgetMode.ENFORCED:
                if (
                    type(intervention.cognitive_budget_limits)
                    is not CognitiveBudgetLimits
                ):
                    _reject("invalid_intervention", "cognitive_budget_limits required")
            elif intervention.cognitive_budget_limits is not None:
                _reject(
                    "invalid_intervention",
                    "cognitive_budget_limits forbidden when disabled",
                )
        elif kind is ResearchInterventionKind.AGENT_ARCHITECTURE:
            _assert_only(
                intervention,
                allowed=frozenset({"agent_ids", "architecture_id"}),
            )
            _require_agents(intervention)
            if (
                not isinstance(intervention.architecture_id, str)
                or not intervention.architecture_id.strip()
            ):
                _reject("architecture_unknown", "architecture_id required")
            object.__setattr__(
                intervention,
                "architecture_id",
                intervention.architecture_id.strip(),
            )
        elif kind is ResearchInterventionKind.ALTERNATE_SEED_STREAM:
            _assert_only(
                intervention,
                allowed=frozenset({"alternate_stochastic_identity"}),
            )
            if intervention.alternate_stochastic_identity is None:
                _reject(
                    "invalid_intervention",
                    "alternate_stochastic_identity required",
                )
        else:
            _reject("invalid_intervention", "unknown intervention kind")
    except BranchError:
        raise
    except (TypeError, ValueError) as exc:
        _reject("invalid_intervention", str(exc))

    fingerprint = _fingerprint_document(_canonical_intervention_document(intervention))
    _LOG.debug(
        "[simulation.branching] intervention_validated kind=%s fingerprint=%s",
        kind.value,
        fingerprint,
    )
    return intervention


def validate_branch_create_request(request: BranchCreateRequest) -> BranchCreateRequest:
    """Validate a create request carrying exactly one intervention."""
    if type(request) is not BranchCreateRequest:
        _reject("invalid_intervention", "expected BranchCreateRequest")
    validate_research_intervention(request.intervention)
    return request


def _canonical_intervention_document(
    intervention: ResearchIntervention,
) -> dict[str, Any]:
    """Exact key-set document; caller must validate first."""
    kind = intervention.kind
    document: dict[str, Any] = {"kind": kind.value}
    if kind is ResearchInterventionKind.MEMORY_ARCHITECTURE:
        document["agent_ids"] = list(intervention.agent_ids)
        assert intervention.memory_mode is not None
        document["memory_mode"] = intervention.memory_mode.value
    elif kind is ResearchInterventionKind.BELIEF_PATCH:
        assert intervention.belief_patch is not None
        patch = intervention.belief_patch
        document["belief_patch"] = {
            "owner_id": patch.owner_id,
            "belief_id": patch.belief_id,
            "subject_kind": patch.subject_kind,
            "subject_id": patch.subject_id,
            "predicate": patch.predicate,
            "value_kind": patch.value_kind,
            "bool_value": patch.bool_value,
            "number_value": patch.number_value,
            "text_value": patch.text_value,
            "agent_value": patch.agent_value,
            "entity_value": patch.entity_value,
        }
    elif kind is ResearchInterventionKind.COMMUNICATION_REMOVE:
        assert intervention.communication_remove is not None
        target = intervention.communication_remove
        document["communication_remove"] = {
            "event_id": target.event_id,
            "tick": target.tick,
            "sequence": target.sequence,
        }
    elif kind is ResearchInterventionKind.MORTALITY_DISABLED:
        document["mortality_mode"] = MortalityMode.DISABLED.value
    elif kind is ResearchInterventionKind.COGNITIVE_BUDGET:
        assert intervention.cognitive_budget_mode is not None
        document["agent_ids"] = list(intervention.agent_ids)
        document["cognitive_budget_mode"] = intervention.cognitive_budget_mode.value
        if intervention.cognitive_budget_limits is not None:
            limits = intervention.cognitive_budget_limits
            document["cognitive_budget_limits"] = {
                "max_llm_calls_per_tick": limits.max_llm_calls_per_tick,
                "max_tokens_per_tick": limits.max_tokens_per_tick,
                "max_imagination_branches": limits.max_imagination_branches,
                "max_planning_depth": limits.max_planning_depth,
                "max_recalled_memories": limits.max_recalled_memories,
                "max_tom_targets": limits.max_tom_targets,
                "reflection_interval_ticks": limits.reflection_interval_ticks,
                "timeout_seconds": limits.timeout_seconds,
            }
        else:
            document["cognitive_budget_limits"] = None
    elif kind is ResearchInterventionKind.AGENT_ARCHITECTURE:
        document["agent_ids"] = list(intervention.agent_ids)
        document["architecture_id"] = intervention.architecture_id
    elif kind is ResearchInterventionKind.ALTERNATE_SEED_STREAM:
        assert intervention.alternate_stochastic_identity is not None
        document["alternate_stochastic_identity"] = (
            intervention.alternate_stochastic_identity.value
        )
    else:
        _reject("invalid_intervention", "unknown intervention kind")
    return document


def _fingerprint_document(document: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(document), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def canonical_intervention_document(
    intervention: ResearchIntervention,
) -> dict[str, Any]:
    """Exact key-set canonical document for fingerprinting and persistence."""
    validated = validate_research_intervention(intervention)
    return _canonical_intervention_document(validated)


def intervention_fingerprint(intervention: ResearchIntervention) -> str:
    """Canonical SHA-256 hex over the closed intervention record."""
    document = canonical_intervention_document(intervention)
    return _fingerprint_document(document)


def intervention_summary(intervention: ResearchIntervention) -> str:
    """Short closed summary suitable for observer metadata (no payloads)."""
    fingerprint = intervention_fingerprint(intervention)
    return f"{intervention.kind.value}:{fingerprint[:12]}"


def seed_stream_token_for_intervention(intervention: ResearchIntervention) -> str:
    """Stable digest token for child run identity seed-stream participation."""
    validated = validate_research_intervention(intervention)
    if validated.kind is ResearchInterventionKind.ALTERNATE_SEED_STREAM:
        assert validated.alternate_stochastic_identity is not None
        return f"alternate:{validated.alternate_stochastic_identity.value}"
    return INHERIT_SEED_STREAM_TOKEN


def resolve_idempotent_create(
    *,
    child_run_id: RunId,
    request: BranchCreateRequest,
    existing: BranchLineage | None,
) -> BranchCreateResult | None:
    """Return an idempotent hit, raise on identity conflict, or ``None`` to create.

    Port-level create semantics used by ``BranchService`` before rematerialization.
    """
    validated = validate_branch_create_request(request)
    fingerprint = intervention_fingerprint(validated.intervention)
    if existing is None:
        return None
    if existing.child_run_id != child_run_id:
        _LOG.error(
            "branch_identity_conflict child_run_id=%s existing_child_run_id=%s",
            child_run_id.value,
            existing.child_run_id.value,
        )
        raise BranchError("branch_identity_conflict")
    if (
        existing.parent_run_id != validated.parent_run_id
        or existing.fork_tick != validated.fork_tick
        or existing.intervention_fingerprint != fingerprint
    ):
        _LOG.error(
            "branch_identity_conflict child_run_id=%s parent_run_id=%s",
            child_run_id.value,
            validated.parent_run_id.value,
        )
        raise BranchError("branch_identity_conflict")
    _LOG.info(
        "research_fork_idempotent_hit child_run_id=%s fingerprint=%s",
        child_run_id.value,
        fingerprint,
    )
    return BranchCreateResult(
        child_run_id=child_run_id,
        branch_id=existing.branch_id,
        lineage=existing,
        idempotent_hit=True,
    )


def reject_multiple_interventions(
    interventions: Sequence[ResearchIntervention],
) -> None:
    """Reject zero or multiple interventions in one request."""
    if len(interventions) != 1:
        _reject(
            "multiple_interventions"
            if len(interventions) > 1
            else "invalid_intervention"
        )


def encode_branch_lineage(lineage: BranchLineage) -> dict[str, Any]:
    """Encode lineage into a persistence-facing exact key-set document."""
    if type(lineage) is not BranchLineage:
        raise TypeError("encode_branch_lineage requires BranchLineage")
    return {
        "child_run_id": lineage.child_run_id.value,
        "parent_run_id": lineage.parent_run_id.value,
        "fork_tick": lineage.fork_tick,
        "intervention_kind": lineage.intervention_kind.value,
        "intervention_fingerprint": lineage.intervention_fingerprint,
        "intervention_canonical": dict(lineage.intervention_canonical),
        "branch_id": lineage.branch_id,
        "created_as_of_parent_head": lineage.created_as_of_parent_head,
    }


def decode_branch_lineage(document: Mapping[str, Any]) -> BranchLineage:
    """Decode a persistence document into ``BranchLineage``."""
    if not isinstance(document, Mapping):
        raise TypeError("decode_branch_lineage requires a mapping")
    expected = frozenset(
        {
            "child_run_id",
            "parent_run_id",
            "fork_tick",
            "intervention_kind",
            "intervention_fingerprint",
            "intervention_canonical",
            "branch_id",
            "created_as_of_parent_head",
        }
    )
    keys = frozenset(document.keys())
    if keys != expected:
        raise BranchError("invalid_intervention", "lineage key-set mismatch")
    kind = ResearchInterventionKind(str(document["intervention_kind"]))
    return BranchLineage(
        child_run_id=RunId(str(document["child_run_id"])),
        parent_run_id=RunId(str(document["parent_run_id"])),
        fork_tick=int(document["fork_tick"]),
        intervention_kind=kind,
        intervention_fingerprint=str(document["intervention_fingerprint"]),
        intervention_canonical=dict(document["intervention_canonical"]),
        branch_id=str(document["branch_id"]),
        created_as_of_parent_head=int(document["created_as_of_parent_head"]),
    )


class InMemoryBranchLineageRepository:
    """In-memory lineage store for unit proofs (not durable)."""

    def __init__(self) -> None:
        self._by_child: dict[str, BranchLineage] = {}

    async def put_lineage(self, lineage: BranchLineage) -> BranchLineage:
        if type(lineage) is not BranchLineage:
            raise TypeError("put_lineage requires BranchLineage")
        existing = self._by_child.get(lineage.child_run_id.value)
        if existing is not None:
            if (
                existing.intervention_fingerprint == lineage.intervention_fingerprint
                and existing.parent_run_id == lineage.parent_run_id
                and existing.fork_tick == lineage.fork_tick
            ):
                _LOG.info(
                    "research_fork_idempotent_hit child_run_id=%s fingerprint=%s",
                    lineage.child_run_id.value,
                    lineage.intervention_fingerprint,
                )
                return existing
            _LOG.error(
                "branch_identity_conflict child_run_id=%s parent_run_id=%s",
                lineage.child_run_id.value,
                lineage.parent_run_id.value,
            )
            raise BranchError("branch_identity_conflict")
        self._by_child[lineage.child_run_id.value] = lineage
        _LOG.debug(
            "branch_lineage_put child_run_id=%s parent_run_id=%s",
            lineage.child_run_id.value,
            lineage.parent_run_id.value,
        )
        return lineage

    async def get_lineage(self, *, child_run_id: RunId) -> BranchLineage | None:
        if type(child_run_id) is not RunId:
            raise TypeError("get_lineage requires RunId")
        return self._by_child.get(child_run_id.value)

    async def list_children(
        self,
        *,
        parent_run_id: RunId,
        after_child_run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[BranchLineage, ...]:
        if type(parent_run_id) is not RunId:
            raise TypeError("list_children requires RunId")
        page_limit = require_exact_nonneg_int("limit", limit)
        if page_limit < 1:
            raise ValueError("limit must be >= 1")
        rows = [
            lineage
            for lineage in self._by_child.values()
            if lineage.parent_run_id == parent_run_id
        ]
        rows.sort(key=lambda item: item.child_run_id.value)
        if after_child_run_id is not None:
            rows = [
                lineage
                for lineage in rows
                if lineage.child_run_id.value > after_child_run_id
            ]
        result = tuple(rows[:page_limit])
        _LOG.debug(
            "branch_lineage_list parent_run_id=%s count=%s",
            parent_run_id.value,
            len(result),
        )
        return result
