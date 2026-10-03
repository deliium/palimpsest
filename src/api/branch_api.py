"""Research branch HTTP service (fork create + lineage inspection).

Maps domain ``BranchError`` reason codes to stable API problem codes.
Never logs intervention payloads, belief text, or runner config bytes.
"""

from __future__ import annotations

from typing import Protocol

from api.errors import (
    ApiError,
    bad_request,
    conflict,
    not_found,
    unprocessable,
)
from api.schemas import (
    BranchCreateIn,
    BranchCreateOut,
    BranchForkPointOut,
    BranchLineageOut,
    BranchListOut,
    BranchStateOut,
    BranchTimelineCompareIn,
    BranchTimelineCompareOut,
    ConfigAvailabilityOut,
    LifecycleStateOut,
    ResearchInterventionIn,
    RunControlStatusOut,
)
from infrastructure.logging import get_logger
from simulation.branch_service import BranchService
from simulation.branching import (
    BeliefPatchPayload,
    BranchCreateRequest,
    BranchError,
    BranchLineage,
    BranchTimelineCompareRequest,
    BranchTimelineCompareResult,
    CommunicationRemoveTarget,
    ResearchIntervention,
    ResearchInterventionKind,
)
from simulation.models import RunId, StochasticIdentity
from simulation.persistence import BranchLineageRepository, RunControlRepository
from simulation.runner_models import (
    CognitiveBudgetLimits,
    CognitiveBudgetMode,
    MemoryMode,
    MortalityMode,
)
from simulation.runner_serialization import decode_runner_config

_LOGGER = get_logger("api.branch_api")

_NOT_FOUND_CODES = frozenset({"unknown_parent", "branch_root", "run_not_found"})
_CONFLICT_CODES = frozenset({"branch_identity_conflict"})
_UNPROCESSABLE_CODES = frozenset({"architecture_unknown", "belief_not_found"})


class BranchComparePort(Protocol):
    async def compare(
        self, request: BranchTimelineCompareRequest
    ) -> BranchTimelineCompareResult: ...


def _map_branch_error(exc: BranchError, *, run_id: str | None = None) -> ApiError:
    code = exc.reason_code
    if code in _NOT_FOUND_CODES:
        return not_found(code=code, run_id=run_id)
    if code in _CONFLICT_CODES:
        return conflict(code=code, run_id=run_id)
    if code in _UNPROCESSABLE_CODES:
        return unprocessable(code=code, run_id=run_id)
    return bad_request(code=code, run_id=run_id)


def _lineage_out(lineage: BranchLineage) -> BranchLineageOut:
    return BranchLineageOut(
        child_run_id=lineage.child_run_id.value,
        parent_run_id=lineage.parent_run_id.value,
        fork_tick=lineage.fork_tick,
        intervention_kind=lineage.intervention_kind.value,
        intervention_fingerprint=lineage.intervention_fingerprint,
        intervention_summary=(
            f"{lineage.intervention_kind.value}:"
            f"{lineage.intervention_fingerprint[:12]}"
        ),
        branch_id=lineage.branch_id,
        created_as_of_parent_head=lineage.created_as_of_parent_head,
    )


def intervention_from_request(body: ResearchInterventionIn) -> ResearchIntervention:
    """Map closed API intervention body into the domain contract."""
    try:
        kind = ResearchInterventionKind(body.kind)
    except ValueError as exc:
        raise BranchError("invalid_intervention", "unknown_kind") from exc

    belief_patch = None
    if body.belief_patch is not None:
        patch = body.belief_patch
        belief_patch = BeliefPatchPayload(
            owner_id=patch.owner_id,
            belief_id=patch.belief_id,
            subject_kind=patch.subject_kind,
            subject_id=patch.subject_id,
            predicate=patch.predicate,
            value_kind=patch.value_kind,
            bool_value=patch.bool_value,
            number_value=patch.number_value,
            text_value=patch.text_value,
            agent_value=patch.agent_value,
            entity_value=patch.entity_value,
        )

    communication_remove = None
    if body.communication_remove is not None:
        target = body.communication_remove
        communication_remove = CommunicationRemoveTarget(
            event_id=target.event_id,
            tick=target.tick,
            sequence=target.sequence,
        )

    memory_mode = MemoryMode(body.memory_mode) if body.memory_mode else None
    mortality_mode = (
        MortalityMode(body.mortality_mode) if body.mortality_mode else None
    )
    budget_mode = (
        CognitiveBudgetMode(body.cognitive_budget_mode)
        if body.cognitive_budget_mode
        else None
    )
    budget_limits = None
    if body.cognitive_budget_limits is not None:
        limits = body.cognitive_budget_limits
        budget_limits = CognitiveBudgetLimits(
            max_llm_calls_per_tick=limits.max_llm_calls_per_tick,
            max_tokens_per_tick=limits.max_tokens_per_tick,
            max_imagination_branches=limits.max_imagination_branches,
            max_planning_depth=limits.max_planning_depth,
            max_recalled_memories=limits.max_recalled_memories,
            max_tom_targets=limits.max_tom_targets,
            reflection_interval_ticks=limits.reflection_interval_ticks,
            timeout_seconds=limits.timeout_seconds,
        )
    alternate = None
    if body.alternate_stochastic_identity is not None:
        alternate = StochasticIdentity(body.alternate_stochastic_identity)

    return ResearchIntervention(
        kind=kind,
        agent_ids=body.agent_ids,
        memory_mode=memory_mode,
        belief_patch=belief_patch,
        communication_remove=communication_remove,
        mortality_mode=mortality_mode,
        cognitive_budget_mode=budget_mode,
        cognitive_budget_limits=budget_limits,
        architecture_id=body.architecture_id,
        alternate_stochastic_identity=alternate,
    )


class BranchApiService:
    """Compose lineage inspection and fork create for HTTP routes."""

    __slots__ = ("_branch", "_compare", "_lineage", "_run_control")

    def __init__(
        self,
        *,
        lineage: BranchLineageRepository | None = None,
        branch: BranchService | None = None,
        run_control: RunControlRepository | None = None,
        compare: BranchComparePort | None = None,
    ) -> None:
        self._lineage = lineage
        self._branch = branch
        self._run_control = run_control
        self._compare = compare

    async def create_branch(
        self, parent_run_id: str, body: BranchCreateIn
    ) -> BranchCreateOut:
        if self._branch is None or self._run_control is None:
            _LOGGER.error(
                "branch_create_unavailable",
                reason_code="branch_service_unavailable",
                parent_run_id=parent_run_id,
            )
            raise bad_request(code="branch_service_unavailable", run_id=parent_run_id)
        try:
            intervention = intervention_from_request(body.intervention)
            parent = RunId(parent_run_id)
            control = await self._run_control.get(parent)
            if control is None or control.config_payload is None:
                raise BranchError("unknown_parent")
            runner_config = decode_runner_config(control.config_payload)
            result = await self._branch.create_research_fork(
                BranchCreateRequest(
                    parent_run_id=parent,
                    fork_tick=body.fork_tick,
                    intervention=intervention,
                ),
                parent_runner_config=runner_config,
            )
        except BranchError as exc:
            raise _map_branch_error(exc, run_id=parent_run_id) from exc
        except ValueError as exc:
            _LOGGER.error(
                "branch_create_rejected",
                reason_code="invalid_intervention",
                parent_run_id=parent_run_id,
            )
            raise bad_request(
                code="invalid_intervention", run_id=parent_run_id
            ) from exc

        child_status: RunControlStatusOut | None = None
        child_record = await self._run_control.get(result.child_run_id)
        if child_record is not None:
            child_status = RunControlStatusOut(
                run_id=child_record.run_id.value,
                lifecycle_state=LifecycleStateOut(child_record.lifecycle_state.value),
                lifecycle_version=child_record.lifecycle_version,
                config_availability=ConfigAvailabilityOut(
                    child_record.config_availability.value
                ),
                ticks_committed=child_record.ticks_committed,
                progress_cursor=child_record.progress_cursor,
                config_schema_version=child_record.config_schema_version,
                config_fingerprint=child_record.config_fingerprint,
                has_lease=child_record.lease is not None,
                terminal_reason_code=child_record.terminal_reason_code,
            )
        _LOGGER.info(
            "route_branch_create",
            parent_run_id=parent_run_id,
            child_run_id=result.child_run_id.value,
            fork_tick=body.fork_tick,
            kind=body.intervention.kind,
            idempotent_hit=result.idempotent_hit,
        )
        return BranchCreateOut(
            child_run_id=result.child_run_id.value,
            branch_id=result.branch_id,
            lineage=_lineage_out(result.lineage),
            idempotent_hit=result.idempotent_hit,
            run=child_status,
        )

    async def list_children(
        self,
        parent_run_id: str,
        *,
        after_child_run_id: str | None,
        limit: int,
    ) -> BranchListOut:
        if self._lineage is None:
            raise bad_request(code="branch_service_unavailable", run_id=parent_run_id)
        rows = await self._lineage.list_children(
            parent_run_id=RunId(parent_run_id),
            after_child_run_id=after_child_run_id,
            limit=limit,
        )
        items = tuple(_lineage_out(row) for row in rows if type(row) is BranchLineage)
        next_cursor = items[-1].child_run_id if len(items) == limit else None
        _LOGGER.info(
            "route_branch_list",
            parent_run_id=parent_run_id,
            count=len(items),
        )
        return BranchListOut(items=items, next_cursor=next_cursor, count=len(items))

    async def get_lineage(self, run_id: str) -> BranchLineageOut:
        if self._lineage is None:
            raise bad_request(code="branch_service_unavailable", run_id=run_id)
        lineage = await self._lineage.get_lineage(child_run_id=RunId(run_id))
        if lineage is None:
            raise not_found(code="branch_root", run_id=run_id)
        if type(lineage) is not BranchLineage:
            raise TypeError("lineage repository must return BranchLineage")
        _LOGGER.debug(
            "route_branch_get",
            run_id=run_id,
            parent_run_id=lineage.parent_run_id.value,
            fork_tick=lineage.fork_tick,
        )
        return _lineage_out(lineage)

    async def fork_point(self, run_id: str) -> BranchForkPointOut:
        lineage_out = await self.get_lineage(run_id)
        return BranchForkPointOut(
            parent_run_id=lineage_out.parent_run_id,
            child_run_id=lineage_out.child_run_id,
            fork_tick=lineage_out.fork_tick,
            parent_observer_tick=lineage_out.fork_tick,
            child_observer_tick=lineage_out.fork_tick,
        )

    async def branch_state(self, run_id: str) -> BranchStateOut:
        lineage: BranchLineage | None = None
        if self._lineage is not None:
            loaded = await self._lineage.get_lineage(child_run_id=RunId(run_id))
            if loaded is not None and type(loaded) is BranchLineage:
                lineage = loaded
        ticks = 0
        progress = 0
        lifecycle: LifecycleStateOut | None = None
        if self._run_control is not None:
            record = await self._run_control.get(RunId(run_id))
            if record is None and lineage is None:
                raise not_found(code="run_not_found", run_id=run_id)
            if record is not None:
                ticks = record.ticks_committed
                progress = record.progress_cursor
                lifecycle = LifecycleStateOut(record.lifecycle_state.value)
        summary = None
        if lineage is not None:
            summary = (
                f"{lineage.intervention_kind.value}:"
                f"{lineage.intervention_fingerprint[:12]}"
            )
        return BranchStateOut(
            run_id=run_id,
            parent_run_id=None if lineage is None else lineage.parent_run_id.value,
            fork_tick=None if lineage is None else lineage.fork_tick,
            intervention_summary=summary,
            branch_id=None if lineage is None else lineage.branch_id,
            ticks_committed=ticks,
            progress_cursor=progress,
            lifecycle_state=lifecycle,
        )

    async def compare_timelines(
        self, body: BranchTimelineCompareIn
    ) -> BranchTimelineCompareOut:
        if self._compare is None:
            raise bad_request(code="branch_compare_unavailable")
        request = BranchTimelineCompareRequest(
            left_run_id=RunId(body.left_run_id),
            right_run_id=RunId(body.right_run_id),
            fork_tick=body.fork_tick,
            include_event_kind_counts=body.include_event_kind_counts,
        )
        try:
            result = await self._compare.compare(request)
        except BranchError as exc:
            raise _map_branch_error(exc) from exc
        if type(result) is not BranchTimelineCompareResult:
            raise TypeError("compare port must return BranchTimelineCompareResult")
        counts = None
        if result.event_kind_counts is not None:
            counts = {
                side: dict(values) for side, values in result.event_kind_counts.items()
            }
        _LOGGER.info(
            "route_branch_compare",
            left_run_id=result.left_run_id.value,
            right_run_id=result.right_run_id.value,
            diverge_tick=result.diverge_tick,
        )
        return BranchTimelineCompareOut(
            left_run_id=result.left_run_id.value,
            right_run_id=result.right_run_id.value,
            fork_tick=result.fork_tick,
            prefix_equivalent=result.prefix_equivalent,
            diverge_tick=result.diverge_tick,
            diverge_sequence=result.diverge_sequence,
            reason_code=result.reason_code,
            left_post_fork_trajectory_hash=result.left_post_fork_trajectory_hash,
            right_post_fork_trajectory_hash=result.right_post_fork_trajectory_hash,
            event_kind_counts=counts,
        )
