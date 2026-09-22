"""Trusted intervention and milestone arbitration contracts.

Truth specifications stay analysis-only. Agents never receive ``is_false``
markers or truth labels through cognition, memory, or prompts. Milestone
overrides produce fresh structured commands that still pass normal runtime
binding, admission, and world resolution.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol, runtime_checkable

from agents.models import AgentId
from analysis.truth import (
    CLAIM_TRUTH_SCHEMA_VERSION,
    ClaimExpectedValue,
    ClaimTruthSpec,
    ClaimValueKind,
    TruthEvaluatorPolicy,
)
from simulation.lifecycle import ActionResolution, ActionResolutionStatus
from world.actions import AgentCommand, Tell, require_agent_command
from world.communications import StructuredUtterance, origin_utterance
from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("experiments.interventions")

INTERVENTION_POLICY_VERSION: Final[str] = "story-intervention-v1"
MILESTONE_ARBITER_POLICY_VERSION: Final[str] = "milestone-arbiter-v1"
DEFAULT_OVERRIDE_BUDGET: Final[int] = 16


class InterventionStatus(StrEnum):
    """Closed intervention lifecycle codes (no payloads)."""

    SCHEDULED = "scheduled"
    APPLIED = "applied"
    CONSUMED_REJECTED = "consumed_rejected"
    PENDING_RETRY = "pending_retry"


class MilestoneStatus(StrEnum):
    """Closed milestone override lifecycle codes (no payloads)."""

    SCHEDULED = "scheduled"
    SELECTED = "selected"
    APPLIED = "applied"
    REJECTED = "rejected"
    BUDGET_EXHAUSTED = "budget_exhausted"
    SKIPPED = "skipped"


class ArbiterErrorCode(StrEnum):
    """Stable ERROR codes for arbiter failures (no payloads)."""

    INVALID_MILESTONE = "arbiter_invalid_milestone"
    DUPLICATE_MILESTONE = "arbiter_duplicate_milestone"
    BUDGET_INVALID = "arbiter_budget_invalid"
    ACK_WITHOUT_SELECTION = "arbiter_ack_without_selection"


@dataclass(frozen=True, slots=True)
class StoryTruthSpec:
    """Analysis-only truth label with claim-level identity for metrics.

    Never exposed to agents or cognition. Use ``to_claim_truth`` to export the
    metric-facing ``ClaimTruthSpec`` owned by ``analysis``.
    """

    intervention_id: str
    is_false: bool
    concept_codes: tuple[str, ...]
    claim_id: str | None = None
    valid_from_tick: int = 0
    valid_to_tick: int | None = None
    unit: str | None = None
    tolerance: float | None = None
    evaluator_policy: TruthEvaluatorPolicy = TruthEvaluatorPolicy.EXACT_MATCH
    objective_provenance: str | None = None
    policy_version: str = INTERVENTION_POLICY_VERSION

    def __post_init__(self) -> None:
        require_stable_id("intervention_id", self.intervention_id)
        if type(self.is_false) is not bool:
            raise TypeError("is_false must be bool")
        if self.policy_version != INTERVENTION_POLICY_VERSION:
            raise ValueError("unsupported intervention policy_version")
        object.__setattr__(self, "concept_codes", tuple(self.concept_codes))
        for code in self.concept_codes:
            require_stable_id("concept_code", code)
        claim_id = self.claim_id
        if claim_id is None:
            claim_id = f"{self.intervention_id}-claim"
        object.__setattr__(
            self,
            "claim_id",
            require_stable_id("claim_id", claim_id),
        )
        object.__setattr__(
            self,
            "valid_from_tick",
            require_exact_nonneg_int("valid_from_tick", self.valid_from_tick),
        )
        if self.valid_to_tick is not None:
            object.__setattr__(
                self,
                "valid_to_tick",
                require_exact_nonneg_int("valid_to_tick", self.valid_to_tick),
            )
            if self.valid_to_tick < self.valid_from_tick:
                raise ValueError("invalid_validity_interval")
        if self.unit is not None:
            object.__setattr__(self, "unit", require_stable_id("unit", self.unit))
        if self.tolerance is not None:
            if type(self.tolerance) is not float:
                raise TypeError("tolerance must be float")
            if (
                self.tolerance != self.tolerance
                or self.tolerance in (float("inf"), float("-inf"))
                or self.tolerance < 0.0
            ):
                raise ValueError("invalid_tolerance")
        if type(self.evaluator_policy) is not TruthEvaluatorPolicy:
            raise TypeError("evaluator_policy must be TruthEvaluatorPolicy")
        if self.objective_provenance is not None:
            object.__setattr__(
                self,
                "objective_provenance",
                require_stable_id("objective_provenance", self.objective_provenance),
            )

    def to_claim_truth(self) -> ClaimTruthSpec:
        """Export analysis-owned claim truth for metric evaluation."""
        assert self.claim_id is not None
        expected = ClaimExpectedValue(
            kind=ClaimValueKind.BOOLEAN,
            boolean_value=not self.is_false,
        )
        spec = ClaimTruthSpec(
            claim_id=self.claim_id,
            schema_version=CLAIM_TRUTH_SCHEMA_VERSION,
            expected=expected,
            valid_from_tick=self.valid_from_tick,
            valid_to_tick=self.valid_to_tick,
            unit=self.unit,
            tolerance=self.tolerance,
            evaluator_policy=self.evaluator_policy,
            intervention_id=self.intervention_id,
            objective_provenance=self.objective_provenance,
            concept_codes=self.concept_codes,
        )
        _LOG.debug(
            "story_truth_exported_to_claim",
            extra={
                "operation": "StoryTruthSpec.to_claim_truth",
                "intervention_id": self.intervention_id,
                "claim_id": self.claim_id,
                "schema_version": CLAIM_TRUTH_SCHEMA_VERSION,
                "evaluator_policy": self.evaluator_policy.value,
                "valid_from_tick": self.valid_from_tick,
                "has_valid_to_tick": self.valid_to_tick is not None,
                "concept_count": len(self.concept_codes),
            },
        )
        return spec


@dataclass(frozen=True, slots=True)
class StoryIntervention:
    """One-shot Tell replacement applied by the trusted runner arbiter."""

    intervention_id: str
    tick: int
    source_agent_id: AgentId
    recipient_entity_id: EntityId
    utterance: StructuredUtterance
    truth: StoryTruthSpec
    policy_version: str = INTERVENTION_POLICY_VERSION

    def __post_init__(self) -> None:
        require_stable_id("intervention_id", self.intervention_id)
        if type(self.tick) is not int or self.tick < 0:
            raise ValueError("tick must be a non-negative int")
        if type(self.source_agent_id) is not AgentId:
            raise TypeError("source_agent_id must be AgentId")
        if type(self.recipient_entity_id) is not EntityId:
            raise TypeError("recipient_entity_id must be EntityId")
        if type(self.utterance) is not StructuredUtterance:
            raise TypeError("utterance must be StructuredUtterance")
        if type(self.truth) is not StoryTruthSpec:
            raise TypeError("truth must be StoryTruthSpec")
        if self.truth.intervention_id != self.intervention_id:
            raise ValueError("truth.intervention_id must match intervention_id")
        if self.policy_version != INTERVENTION_POLICY_VERSION:
            raise ValueError("unsupported intervention policy_version")
        # Utterance must not carry an is_false marker field.
        if hasattr(self.utterance, "is_false"):
            raise ValueError("utterance must not expose is_false")

    def as_tell(self) -> Tell:
        return Tell(
            recipient_id=self.recipient_entity_id,
            utterance=self.utterance,
        )


@dataclass(frozen=True, slots=True)
class ArbiterOverrideDecision:
    """Fresh command plus milestone identity returned by a typed arbiter."""

    milestone_id: str
    command: AgentCommand
    policy_version: str = MILESTONE_ARBITER_POLICY_VERSION

    def __post_init__(self) -> None:
        require_stable_id("milestone_id", self.milestone_id)
        object.__setattr__(self, "command", require_agent_command(self.command))
        if self.policy_version != MILESTONE_ARBITER_POLICY_VERSION:
            raise ValueError("unsupported milestone arbiter policy_version")


@dataclass(frozen=True, slots=True)
class ProposedVersusEffectiveRecord:
    """Metadata-only record of cognition proposal versus arbiter override."""

    milestone_id: str
    tick: int
    agent_id: AgentId
    proposed_command_kind: str
    effective_command_kind: str
    resolution_status: str | None = None
    milestone_status: MilestoneStatus = MilestoneStatus.SELECTED

    def __post_init__(self) -> None:
        require_stable_id("milestone_id", self.milestone_id)
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        if type(self.agent_id) is not AgentId:
            raise TypeError("agent_id must be AgentId")
        require_stable_id("proposed_command_kind", self.proposed_command_kind)
        require_stable_id("effective_command_kind", self.effective_command_kind)
        if self.resolution_status is not None:
            require_stable_id("resolution_status", self.resolution_status)
        if type(self.milestone_status) is not MilestoneStatus:
            raise TypeError("milestone_status must be MilestoneStatus")


@dataclass(frozen=True, slots=True)
class MilestoneOverride:
    """One scheduled trusted override producing a fresh command when selected."""

    milestone_id: str
    tick: int
    agent_id: AgentId
    build_command: Callable[[], AgentCommand]
    policy_version: str = MILESTONE_ARBITER_POLICY_VERSION

    def __post_init__(self) -> None:
        require_stable_id("milestone_id", self.milestone_id)
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        if type(self.agent_id) is not AgentId:
            raise TypeError("agent_id must be AgentId")
        if not callable(self.build_command):
            raise TypeError("build_command must be callable")
        if self.policy_version != MILESTONE_ARBITER_POLICY_VERSION:
            raise ValueError("unsupported milestone arbiter policy_version")


def _command_kind(command: AgentCommand) -> str:
    kind = getattr(command, "kind", None)
    if isinstance(kind, str) and kind:
        return kind
    return type(command).__name__.lower()


@runtime_checkable
class CommandOverrideArbiter(Protocol):
    """Typed pre-admission arbiter returning a fresh command plus milestone ID."""

    def maybe_replace(
        self,
        *,
        tick: int,
        agent_id: AgentId,
        proposed_command: AgentCommand | None = None,
    ) -> ArbiterOverrideDecision | AgentCommand | None:
        """Return an override decision or raw command, or None for production policy."""

    def acknowledge_resolutions(self, resolutions: Sequence[ActionResolution]) -> None:
        """Consume one-shot milestones from committed ActionResolution outcomes."""

    @property
    def override_budget(self) -> int:
        """Configured maximum override acknowledgements."""

    @property
    def overrides_used(self) -> int:
        """Acknowledged override count against the budget."""

    @property
    def proposed_versus_effective(
        self,
    ) -> tuple[ProposedVersusEffectiveRecord, ...]:
        """Immutable proposed-versus-effective metadata (kinds/status only)."""


class StoryInterventionArbiter:
    """Deterministic pre-admission arbiter for one configured intervention."""

    __slots__ = ("_consumed", "_intervention", "_pending_selected")

    def __init__(self, intervention: StoryIntervention) -> None:
        if type(intervention) is not StoryIntervention:
            raise TypeError("intervention must be StoryIntervention")
        self._intervention = intervention
        self._consumed = False
        self._pending_selected = False

    @property
    def intervention(self) -> StoryIntervention:
        return self._intervention

    @property
    def consumed(self) -> bool:
        return self._consumed

    def maybe_replace(
        self,
        *,
        tick: int,
        agent_id: AgentId,
        proposed_command: AgentCommand | None = None,
    ) -> Tell | None:
        """Return a Tell replacement when this agent/tick matches.

        Does not consume the intervention; call ``acknowledge_resolutions`` or
        ``mark_committed`` after the objective tick commits.
        """
        del proposed_command
        if self._consumed:
            return None
        target = self._intervention
        if tick != target.tick or agent_id != target.source_agent_id:
            return None
        self._pending_selected = True
        _LOG.debug(
            "intervention_selected",
            extra={
                "intervention": {
                    "intervention_id": target.intervention_id,
                    "tick": tick,
                    "source_agent_id": agent_id.value,
                    "recipient_entity_id": target.recipient_entity_id.value,
                    "policy_version": target.policy_version,
                    "status": InterventionStatus.APPLIED.value,
                }
            },
        )
        return target.as_tell()

    def mark_committed(self, *, accepted: bool) -> InterventionStatus:
        """Consume after a successful objective commit for the intervention tick."""
        if self._consumed:
            return InterventionStatus.CONSUMED_REJECTED
        self._consumed = True
        self._pending_selected = False
        status = (
            InterventionStatus.APPLIED
            if accepted
            else InterventionStatus.CONSUMED_REJECTED
        )
        _LOG.info(
            "intervention_consumed",
            extra={
                "intervention": {
                    "intervention_id": self._intervention.intervention_id,
                    "tick": self._intervention.tick,
                    "status": status.value,
                }
            },
        )
        return status

    def acknowledge_resolutions(self, resolutions: Sequence[ActionResolution]) -> None:
        """Map committed ActionResolution status onto one-shot consumption."""
        if self._consumed or not self._pending_selected:
            return
        target = self._intervention
        for resolution in resolutions:
            if type(resolution) is not ActionResolution:
                continue
            if resolution.agent_id != target.source_agent_id:
                continue
            if resolution.tick.value != target.tick:
                continue
            accepted = resolution.status is ActionResolutionStatus.APPLIED
            self.mark_committed(accepted=accepted)
            return
        _LOG.warning(
            "intervention_ack_missing_resolution",
            extra={
                "intervention": {
                    "intervention_id": target.intervention_id,
                    "tick": target.tick,
                    "status": InterventionStatus.PENDING_RETRY.value,
                }
            },
        )


class MilestoneInterventionArbiter:
    """Sparse trusted milestone arbiter with a numeric override budget.

    Most cognition invocations remain production-policy decisions. Selected
    overrides build a fresh command (including fresh communication IDs for Tell)
    and record proposed-versus-effective kinds only.
    """

    __slots__ = (
        "_budget",
        "_by_tick_agent",
        "_consumed",
        "_milestones",
        "_overrides_used",
        "_pending",
        "_records",
        "_statuses",
    )

    def __init__(
        self,
        milestones: Sequence[MilestoneOverride],
        *,
        override_budget: int = DEFAULT_OVERRIDE_BUDGET,
    ) -> None:
        if isinstance(milestones, (set, frozenset)):
            raise TypeError("milestones must be ordered")
        if isinstance(milestones, (str, bytes)) or not isinstance(milestones, Sequence):
            raise TypeError("milestones must be ordered")
        if type(override_budget) is not int or override_budget < 0:
            _LOG.error(
                "arbiter_budget_invalid code=%s",
                ArbiterErrorCode.BUDGET_INVALID.value,
            )
            raise ValueError("override_budget must be a non-negative int")
        ordered = tuple(milestones)
        seen: set[str] = set()
        index: dict[tuple[int, str], MilestoneOverride] = {}
        for item in ordered:
            if type(item) is not MilestoneOverride:
                _LOG.error(
                    "arbiter_invalid_milestone code=%s",
                    ArbiterErrorCode.INVALID_MILESTONE.value,
                )
                raise TypeError("milestones entries must be MilestoneOverride")
            if item.milestone_id in seen:
                _LOG.error(
                    "arbiter_duplicate_milestone code=%s milestone_id=%s",
                    ArbiterErrorCode.DUPLICATE_MILESTONE.value,
                    item.milestone_id,
                )
                raise ValueError("milestone_id values must be unique")
            seen.add(item.milestone_id)
            key = (item.tick, item.agent_id.value)
            if key in index:
                _LOG.error(
                    "arbiter_duplicate_milestone code=%s milestone_id=%s tick=%s",
                    ArbiterErrorCode.DUPLICATE_MILESTONE.value,
                    item.milestone_id,
                    item.tick,
                )
                raise ValueError("tick/agent milestone slots must be unique")
            index[key] = item
        self._milestones = ordered
        self._by_tick_agent = index
        self._budget = override_budget
        self._overrides_used = 0
        self._consumed: set[str] = set()
        self._pending: dict[tuple[int, str], str] = {}
        self._records: list[ProposedVersusEffectiveRecord] = []
        self._statuses: dict[str, MilestoneStatus] = {
            item.milestone_id: MilestoneStatus.SCHEDULED for item in ordered
        }
        _LOG.info(
            "milestone_arbiter_ready milestone_count=%s override_budget=%s "
            "policy_version=%s",
            len(ordered),
            override_budget,
            MILESTONE_ARBITER_POLICY_VERSION,
        )

    @property
    def override_budget(self) -> int:
        return self._budget

    @property
    def overrides_used(self) -> int:
        return self._overrides_used

    @property
    def override_budget_remaining(self) -> int:
        pending = len(self._pending)
        remaining = self._budget - self._overrides_used - pending
        return max(0, remaining)

    @property
    def milestones(self) -> tuple[MilestoneOverride, ...]:
        return self._milestones

    @property
    def proposed_versus_effective(self) -> tuple[ProposedVersusEffectiveRecord, ...]:
        return tuple(self._records)

    def milestone_status(self, milestone_id: str) -> MilestoneStatus:
        require_stable_id("milestone_id", milestone_id)
        try:
            return self._statuses[milestone_id]
        except KeyError as exc:
            raise KeyError(milestone_id) from exc

    def maybe_replace(
        self,
        *,
        tick: int,
        agent_id: AgentId,
        proposed_command: AgentCommand | None = None,
    ) -> ArbiterOverrideDecision | None:
        """Select a scheduled milestone override when tick/agent match."""
        if type(agent_id) is not AgentId:
            raise TypeError("agent_id must be AgentId")
        if type(tick) is not int or tick < 0:
            raise ValueError("tick must be a non-negative int")
        key = (tick, agent_id.value)
        milestone = self._by_tick_agent.get(key)
        if milestone is None:
            return None
        if milestone.milestone_id in self._consumed:
            return None
        reserved = self._overrides_used + len(self._pending)
        if reserved >= self._budget:
            self._statuses[milestone.milestone_id] = MilestoneStatus.BUDGET_EXHAUSTED
            _LOG.warning(
                "milestone_budget_exhausted milestone_id=%s tick=%s status=%s "
                "override_budget=%s overrides_used=%s",
                milestone.milestone_id,
                tick,
                MilestoneStatus.BUDGET_EXHAUSTED.value,
                self._budget,
                self._overrides_used,
            )
            return None
        try:
            command = require_agent_command(milestone.build_command())
        except (TypeError, ValueError):
            _LOG.error(
                "arbiter_invalid_milestone code=%s milestone_id=%s tick=%s",
                ArbiterErrorCode.INVALID_MILESTONE.value,
                milestone.milestone_id,
                tick,
            )
            raise
        proposed_kind = (
            "none"
            if proposed_command is None
            else _command_kind(require_agent_command(proposed_command))
        )
        effective_kind = _command_kind(command)
        self._pending[key] = milestone.milestone_id
        self._statuses[milestone.milestone_id] = MilestoneStatus.SELECTED
        self._records.append(
            ProposedVersusEffectiveRecord(
                milestone_id=milestone.milestone_id,
                tick=tick,
                agent_id=agent_id,
                proposed_command_kind=proposed_kind,
                effective_command_kind=effective_kind,
                milestone_status=MilestoneStatus.SELECTED,
            )
        )
        _LOG.debug(
            "milestone_selected milestone_id=%s tick=%s status=%s",
            milestone.milestone_id,
            tick,
            MilestoneStatus.SELECTED.value,
        )
        return ArbiterOverrideDecision(
            milestone_id=milestone.milestone_id,
            command=command,
        )

    def acknowledge_resolutions(self, resolutions: Sequence[ActionResolution]) -> None:
        """Acknowledge one-shot milestone status from committed resolutions."""
        if isinstance(resolutions, (set, frozenset)):
            raise TypeError("resolutions must be ordered")
        if isinstance(resolutions, Mapping) or (
            isinstance(resolutions, (str, bytes))
            or not isinstance(resolutions, Sequence)
        ):
            raise TypeError("resolutions must be ordered")
        for resolution in resolutions:
            if type(resolution) is not ActionResolution:
                raise TypeError("resolutions entries must be ActionResolution")
            key = (resolution.tick.value, resolution.agent_id.value)
            milestone_id = self._pending.pop(key, None)
            if milestone_id is None:
                continue
            if milestone_id in self._consumed:
                continue
            self._consumed.add(milestone_id)
            self._overrides_used += 1
            applied = resolution.status is ActionResolutionStatus.APPLIED
            status = MilestoneStatus.APPLIED if applied else MilestoneStatus.REJECTED
            self._statuses[milestone_id] = status
            self._update_record(
                milestone_id=milestone_id,
                resolution_status=resolution.status.value,
                milestone_status=status,
            )
            _LOG.debug(
                "milestone_acknowledged milestone_id=%s tick=%s status=%s",
                milestone_id,
                resolution.tick.value,
                status.value,
            )
        # Pending selections without a matching resolution stay retryable.
        if self._pending:
            for milestone_id in tuple(self._pending.values()):
                _LOG.warning(
                    "milestone_precondition_unmet milestone_id=%s status=%s",
                    milestone_id,
                    MilestoneStatus.SKIPPED.value,
                )
            self._pending.clear()

    def _update_record(
        self,
        *,
        milestone_id: str,
        resolution_status: str,
        milestone_status: MilestoneStatus,
    ) -> None:
        for index in range(len(self._records) - 1, -1, -1):
            record = self._records[index]
            if record.milestone_id != milestone_id:
                continue
            self._records[index] = ProposedVersusEffectiveRecord(
                milestone_id=record.milestone_id,
                tick=record.tick,
                agent_id=record.agent_id,
                proposed_command_kind=record.proposed_command_kind,
                effective_command_kind=record.effective_command_kind,
                resolution_status=resolution_status,
                milestone_status=milestone_status,
            )
            return
        _LOG.error(
            "arbiter_ack_without_selection code=%s milestone_id=%s",
            ArbiterErrorCode.ACK_WITHOUT_SELECTION.value,
            milestone_id,
        )


def unwrap_arbiter_command(
    decision: ArbiterOverrideDecision | AgentCommand | None,
) -> AgentCommand | None:
    """Normalize typed decisions and legacy raw commands for runner binding."""
    if decision is None:
        return None
    if type(decision) is ArbiterOverrideDecision:
        return decision.command
    return require_agent_command(decision)


def make_false_story_intervention(
    *,
    intervention_id: str,
    tick: int,
    source_agent_id: AgentId,
    source_entity_id: EntityId,
    recipient_entity_id: EntityId,
    text: str,
    concepts: tuple[str, ...] = (),
) -> StoryIntervention:
    """Build a controlled false-story Tell with analysis-only truth."""
    utterance = origin_utterance(
        text=text,
        speaker_id=source_entity_id,
        communication_id=f"{intervention_id}-comm",
        concepts=concepts,
    )
    truth = StoryTruthSpec(
        intervention_id=intervention_id,
        is_false=True,
        concept_codes=concepts,
        valid_from_tick=tick,
    )
    return StoryIntervention(
        intervention_id=intervention_id,
        tick=tick,
        source_agent_id=source_agent_id,
        recipient_entity_id=recipient_entity_id,
        utterance=utterance,
        truth=truth,
    )
