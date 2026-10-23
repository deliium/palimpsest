"""Bounded child-only scheduled command arbiter and treatment ledger."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from experiments.interventions import (
    ArbiterOverrideDecision,
    ProposedVersusEffectiveRecord,
)
from experiments.path_dependence_models import (
    DEFAULT_MAX_ACTIONS_PER_ARM_FORK,
    MAX_ACTIONS_PER_ARM_FORK,
    GiveInterventionAction,
    PathDependenceValidationError,
    ScheduledCommandIntervention,
    WaitInterventionAction,
)
from simulation.lifecycle import ActionResolution, ActionResolutionStatus
from world.actions import (
    AgentCommand,
    Give,
    Wait,
    agent_command_tag,
    require_agent_command,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.path_dependence_interventions"
)

PATH_DEPENDENCE_ARBITER_POLICY_VERSION: Final[str] = "path-dependence-arbiter-v1"


class TreatmentStatus(StrEnum):
    """Requested-versus-realized treatment state for one scheduled action."""

    SCHEDULED = "scheduled"
    SELECTED = "selected"
    COMMITTED = "committed"
    REJECTED = "rejected"
    MISSED = "missed"


@dataclass(frozen=True, slots=True)
class TreatmentLedgerEntry:
    """Metadata-only treatment exposure record for one action."""

    intervention_id: str
    tick: int
    actor_id: AgentId
    action_kind: str
    proposed_command_kind: str | None = None
    effective_command_kind: str | None = None
    status: TreatmentStatus = TreatmentStatus.SCHEDULED
    resolution_status: str | None = None
    resolution_reason: str | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.actor_id) is not AgentId:
            raise TypeError("actor_id must be AgentId")
        if type(self.status) is not TreatmentStatus:
            raise TypeError("status must be TreatmentStatus")
        for name in (
            "intervention_id",
            "action_kind",
            "proposed_command_kind",
            "effective_command_kind",
            "resolution_status",
            "resolution_reason",
            "request_id",
        ):
            value = getattr(self, name)
            if value is not None and type(value) is not str:
                raise TypeError(f"{name} must be str or None")
        if isinstance(self.tick, bool) or type(self.tick) is not int or self.tick < 0:
            raise ValueError("tick must be a non-negative int")


class PathDependenceArbiter:
    """Install bounded child-only commands through ordinary admission."""

    __slots__ = (
        "_budget",
        "_by_slot",
        "_consumed",
        "_entries",
        "_overrides_used",
        "_pending",
        "_records",
    )

    def __init__(
        self,
        actions: Sequence[ScheduledCommandIntervention],
        *,
        override_budget: int = DEFAULT_MAX_ACTIONS_PER_ARM_FORK,
    ) -> None:
        if isinstance(actions, (set, frozenset, Mapping)):
            raise PathDependenceValidationError(
                "invalid_type", "actions must be ordered"
            )
        if isinstance(actions, (str, bytes)) or not isinstance(actions, Sequence):
            raise PathDependenceValidationError(
                "invalid_type", "actions must be ordered"
            )
        if (
            isinstance(override_budget, bool)
            or type(override_budget) is not int
            or override_budget < 0
            or override_budget > MAX_ACTIONS_PER_ARM_FORK
        ):
            raise PathDependenceValidationError(
                "intervention_budget_exceeded", "invalid override budget"
            )
        ordered = tuple(actions)
        if len(ordered) > override_budget:
            raise PathDependenceValidationError(
                "intervention_budget_exceeded", "schedule exceeds override budget"
            )
        index: dict[tuple[int, str], ScheduledCommandIntervention] = {}
        entries: dict[str, TreatmentLedgerEntry] = {}
        for action in ordered:
            if type(action) is not ScheduledCommandIntervention:
                raise PathDependenceValidationError(
                    "invalid_type", "invalid scheduled intervention"
                )
            key = (action.tick.value, action.actor_id.value)
            if key in index:
                raise PathDependenceValidationError(
                    "duplicate_intervention", "duplicate actor/tick slot"
                )
            index[key] = action
            action_kind = (
                "give"
                if type(action.action) is GiveInterventionAction
                else "wait"
            )
            entries[action.intervention_id] = TreatmentLedgerEntry(
                intervention_id=action.intervention_id,
                tick=action.tick.value,
                actor_id=action.actor_id,
                action_kind=action_kind,
            )
        self._by_slot = index
        self._entries = entries
        self._budget = override_budget
        self._overrides_used = 0
        self._consumed: set[str] = set()
        self._pending: dict[tuple[int, str], str] = {}
        self._records: list[ProposedVersusEffectiveRecord] = []
        _LOG.info(
            "path_dependence_arbiter_ready action_count=%s override_budget=%s "
            "policy_version=%s",
            len(ordered),
            override_budget,
            PATH_DEPENDENCE_ARBITER_POLICY_VERSION,
        )

    @property
    def override_budget(self) -> int:
        return self._budget

    @property
    def overrides_used(self) -> int:
        return self._overrides_used

    @property
    def proposed_versus_effective(self) -> tuple[ProposedVersusEffectiveRecord, ...]:
        return tuple(self._records)

    @property
    def treatment_ledger(self) -> tuple[TreatmentLedgerEntry, ...]:
        return tuple(
            sorted(
                self._entries.values(),
                key=lambda item: (item.tick, item.intervention_id),
            )
        )

    def _build_command(self, action: ScheduledCommandIntervention) -> AgentCommand:
        if type(action.action) is GiveInterventionAction:
            return Give(
                recipient_id=action.action.recipient_entity_id,
                item_id=action.action.item_id,
            )
        if type(action.action) is WaitInterventionAction:
            return Wait()
        raise PathDependenceValidationError(
            "unsupported_intervention", "unsupported action"
        )

    def maybe_replace(
        self,
        *,
        tick: int,
        agent_id: AgentId,
        proposed_command: AgentCommand | None = None,
    ) -> ArbiterOverrideDecision | None:
        if type(agent_id) is not AgentId:
            raise TypeError("agent_id must be AgentId")
        if isinstance(tick, bool) or type(tick) is not int or tick < 0:
            raise ValueError("tick must be a non-negative int")
        action = self._by_slot.get((tick, agent_id.value))
        if action is None:
            return None
        if action.intervention_id in self._consumed:
            return None
        if (tick, agent_id.value) in self._pending:
            return None
        if self._overrides_used + len(self._pending) >= self._budget:
            self._mark_missed(action.intervention_id)
            return None
        command = require_agent_command(self._build_command(action))
        proposed_kind = (
            None
            if proposed_command is None
            else agent_command_tag(require_agent_command(proposed_command))
        )
        effective_kind = agent_command_tag(command)
        self._pending[(tick, agent_id.value)] = action.intervention_id
        entry = self._entries[action.intervention_id]
        self._entries[action.intervention_id] = TreatmentLedgerEntry(
            intervention_id=entry.intervention_id,
            tick=entry.tick,
            actor_id=entry.actor_id,
            action_kind=entry.action_kind,
            proposed_command_kind=proposed_kind,
            effective_command_kind=effective_kind,
            status=TreatmentStatus.SELECTED,
        )
        self._records.append(
            ProposedVersusEffectiveRecord(
                milestone_id=action.intervention_id,
                tick=tick,
                agent_id=agent_id,
                proposed_command_kind=proposed_kind or "none",
                effective_command_kind=effective_kind,
            )
        )
        _LOG.debug(
            "path_dependence_intervention_selected intervention_id=%s tick=%s "
            "status=%s",
            action.intervention_id,
            tick,
            TreatmentStatus.SELECTED.value,
        )
        return ArbiterOverrideDecision(
            milestone_id=action.intervention_id,
            command=command,
        )

    def acknowledge_resolutions(self, resolutions: Sequence[ActionResolution]) -> None:
        if isinstance(resolutions, (set, frozenset, Mapping)) or (
            isinstance(resolutions, (str, bytes))
            or not isinstance(resolutions, Sequence)
        ):
            raise TypeError("resolutions must be ordered")
        for resolution in resolutions:
            if type(resolution) is not ActionResolution:
                raise TypeError("resolutions entries must be ActionResolution")
            key = (resolution.tick.value, resolution.agent_id.value)
            intervention_id = self._pending.pop(key, None)
            if intervention_id is None:
                continue
            if intervention_id in self._consumed:
                continue
            self._consumed.add(intervention_id)
            self._overrides_used += 1
            applied = resolution.status is ActionResolutionStatus.APPLIED
            entry = self._entries[intervention_id]
            self._entries[intervention_id] = TreatmentLedgerEntry(
                intervention_id=entry.intervention_id,
                tick=entry.tick,
                actor_id=entry.actor_id,
                action_kind=entry.action_kind,
                proposed_command_kind=entry.proposed_command_kind,
                effective_command_kind=entry.effective_command_kind,
                status=(
                    TreatmentStatus.COMMITTED
                    if applied
                    else TreatmentStatus.REJECTED
                ),
                resolution_status=resolution.status.value,
                resolution_reason=resolution.reason.value,
                request_id=resolution.request_id.value,
            )
            if not applied:
                _LOG.warning(
                    "path_dependence_treatment_rejected intervention_id=%s "
                    "tick=%s reason_code=%s",
                    intervention_id,
                    resolution.tick.value,
                    resolution.reason.value,
                )

    def finalize_unreached(self) -> None:
        """Mark selected/scheduled actions that never committed as missed."""
        for intervention_id, entry in tuple(self._entries.items()):
            if entry.status in {
                TreatmentStatus.SCHEDULED,
                TreatmentStatus.SELECTED,
            }:
                self._mark_missed(intervention_id)

    def _mark_missed(self, intervention_id: str) -> None:
        entry = self._entries.get(intervention_id)
        if entry is None or entry.status in {
            TreatmentStatus.COMMITTED,
            TreatmentStatus.REJECTED,
            TreatmentStatus.MISSED,
        }:
            return
        self._entries[intervention_id] = TreatmentLedgerEntry(
            intervention_id=entry.intervention_id,
            tick=entry.tick,
            actor_id=entry.actor_id,
            action_kind=entry.action_kind,
            proposed_command_kind=entry.proposed_command_kind,
            effective_command_kind=entry.effective_command_kind,
            status=TreatmentStatus.MISSED,
        )
        _LOG.warning(
            "path_dependence_treatment_missed intervention_id=%s tick=%s",
            intervention_id,
            entry.tick,
        )


__all__ = [
    "PATH_DEPENDENCE_ARBITER_POLICY_VERSION",
    "PathDependenceArbiter",
    "TreatmentLedgerEntry",
    "TreatmentStatus",
]
