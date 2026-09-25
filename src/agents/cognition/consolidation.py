"""Sleep-time consolidation over one owner's subjective stores.

Calls the pure episodic policy, then emits belief, relationship, and goal
intents. It does not persist a self-model and does not read world state.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from agents.cognition.models import (
    DEFAULT_SELF_MODEL_POLICY,
    GoalTransitionIntent,
    GoalTransitionIntentReason,
    MemoryUpdateIntent,
    MemoryUpdateKind,
    SelfModel,
    SelfModelProjectionPolicy,
    SubjectiveSnapshot,
)
from agents.models import AgentId, Goal, GoalStatus
from llm import (
    LLMProvider,
    LLMRequest,
    LLMRequestContext,
    StructuredOutput,
    render_prompt,
)
from llm.errors import LLMError
from memory.belief_formation import (
    DEFAULT_BELIEF_FORMATION_POLICY,
    belief_id_for_claim,
    bundle_from_candidates,
    extract_evidence_candidates,
)
from memory.beliefs import (
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimSubjectKind,
    SemanticClaim,
    canonical_claim_identity,
)
from memory.consolidation import plan_offline_consolidation
from memory.models import (
    MemoryId,
    MemoryTrace,
    OfflineConsolidationAudit,
    OfflineConsolidationPolicy,
    OfflineConsolidationReasonCode,
    OfflineConsolidationSelection,
    default_offline_consolidation_policy,
)
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipInteractionSignal,
    RelationshipRevisionRequest,
    RelationshipSignalKind,
)
from world.identifiers import require_exact_nonneg_int

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.consolidation")
_MAX_TRACES: Final[int] = 256
_TERMINAL_PARENT: Final[frozenset[GoalStatus]] = frozenset(
    {GoalStatus.FAILED, GoalStatus.ABANDONED}
)


@dataclass(frozen=True, slots=True)
class OfflineConsolidationPlan:
    """Intent bundle applied later by runtime finalize. Repr is counts only."""

    selection: OfflineConsolidationSelection
    audit: OfflineConsolidationAudit
    belief_revisions: tuple[BeliefRevisionRequest, ...]
    relationship_revisions: tuple[RelationshipRevisionRequest, ...]
    goal_intents: tuple[GoalTransitionIntent, ...]
    self_model_belief_ids: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            f"OfflineConsolidationPlan(owner_id={self.audit.owner_id.value!r}, "
            f"tick={self.audit.tick}, mode={self.audit.mode!r}, "
            f"belief_count={len(self.belief_revisions)}, "
            f"relationship_count={len(self.relationship_revisions)}, "
            f"goal_count={len(self.goal_intents)}, "
            f"self_model_belief_count={len(self.self_model_belief_ids)})"
        )


def orchestrate_offline_consolidation(
    *,
    snapshot: SubjectiveSnapshot,
    self_model: SelfModel,
    write_intents: Sequence[MemoryUpdateIntent],
    tick: int,
    mode: str,
    policy: OfflineConsolidationPolicy | None = None,
    self_model_policy: SelfModelProjectionPolicy | None = None,
    selection_override: OfflineConsolidationSelection | None = None,
) -> OfflineConsolidationPlan:
    """Plan consolidation from the snapshot plus this invocation's writes."""
    if type(snapshot) is not SubjectiveSnapshot:
        raise TypeError("orchestrate_offline_consolidation: invalid_snapshot")
    if type(self_model) is not SelfModel:
        raise TypeError("orchestrate_offline_consolidation: invalid_self_model")
    resolved_tick = require_exact_nonneg_int(
        "orchestrate_offline_consolidation.tick", tick
    )
    if type(mode) is not str or mode not in {
        "disabled",
        "deterministic",
        "llm_assisted",
    }:
        raise ValueError("orchestrate_offline_consolidation.mode: invalid_mode")
    if self_model.owner_id != snapshot.owner_id:
        _log_owner_mismatch(snapshot.owner_id, resolved_tick)
        raise ValueError("orchestrate_offline_consolidation: owner_mismatch")
    resolved_policy = (
        default_offline_consolidation_policy() if policy is None else policy
    )
    if type(resolved_policy) is not OfflineConsolidationPolicy:
        raise TypeError("orchestrate_offline_consolidation: invalid_policy")
    projection_policy = (
        DEFAULT_SELF_MODEL_POLICY
        if self_model_policy is None
        else self_model_policy
    )
    if type(projection_policy) is not SelfModelProjectionPolicy:
        raise TypeError("orchestrate_offline_consolidation: invalid_self_policy")
    if projection_policy.policy_id != self_model.policy_id:
        projection_policy = SelfModelProjectionPolicy(
            policy_id=self_model.policy_id,
            version=self_model.policy_version,
            min_confidence=projection_policy.min_confidence,
            require_active=projection_policy.require_active,
            max_beliefs=projection_policy.max_beliefs,
        )

    traces = _collect_traces(
        snapshot=snapshot,
        write_intents=write_intents,
        tick=resolved_tick,
    )
    if selection_override is None:
        _candidate, selection = plan_offline_consolidation(
            owner_id=snapshot.owner_id,
            tick=resolved_tick,
            traces=traces,
            policy=resolved_policy,
        )
    else:
        if type(selection_override) is not OfflineConsolidationSelection:
            raise TypeError("orchestrate_offline_consolidation: invalid_selection")
        if (
            selection_override.owner_id != snapshot.owner_id
            or selection_override.tick != resolved_tick
        ):
            _log_owner_mismatch(snapshot.owner_id, resolved_tick)
            raise ValueError("orchestrate_offline_consolidation: owner_mismatch")
        selection = selection_override
    affected = _affected_ids(selection)
    beliefs = _belief_revisions(
        traces=traces,
        selection=selection,
        owner_id=snapshot.owner_id,
        tick=resolved_tick,
    )
    self_ids = tuple(
        request.belief_id.value
        for request in beliefs
        if request.belief_id is not None
        and _claim_references_owner(request.claim, snapshot.owner_id)
        and request.evidence.total_count > 0
        and _supporting_mass(request) >= projection_policy.min_confidence
    )
    relationships: tuple[RelationshipRevisionRequest, ...] = ()
    relationship_ids: tuple[str, ...] = ()
    goals: tuple[GoalTransitionIntent, ...] = ()
    if affected:
        relationships, relationship_ids = _relationship_revisions(
            snapshot=snapshot,
            traces=traces,
            affected=affected,
            tick=resolved_tick,
        )
        goals = _goal_intents(
            snapshot=snapshot,
            affected=affected,
            tick=resolved_tick,
        )
    audit = _audit(
        snapshot=snapshot,
        selection=selection,
        mode=mode,
        beliefs=beliefs,
        relationship_ids=relationship_ids,
        goals=goals,
    )
    _LOG.debug(
        "offline_consolidation_candidates owner_id=%s tick=%s mode=%s "
        "trace_count=%s merge_count=%s soft_forget_count=%s "
        "belief_count=%s relationship_count=%s goal_count=%s",
        snapshot.owner_id.value,
        resolved_tick,
        mode,
        len(traces),
        len(selection.merge_groups),
        len(selection.soft_forget_ids),
        len(beliefs),
        len(relationships),
        len(goals),
    )
    return OfflineConsolidationPlan(
        selection=selection,
        audit=audit,
        belief_revisions=beliefs,
        relationship_revisions=relationships,
        goal_intents=goals,
        self_model_belief_ids=self_ids,
    )


def _log_owner_mismatch(owner_id: AgentId, tick: int) -> None:
    _LOG.error(
        "offline_consolidation_aborted owner_id=%s tick=%s reason_code=owner_mismatch",
        owner_id.value,
        tick,
    )


def _collect_traces(
    *,
    snapshot: SubjectiveSnapshot,
    write_intents: Sequence[MemoryUpdateIntent],
    tick: int,
) -> tuple[MemoryTrace, ...]:
    if isinstance(write_intents, (str, bytes)) or not isinstance(
        write_intents, Sequence
    ):
        raise TypeError("orchestrate_offline_consolidation.write_intents: invalid_type")
    combined: list[MemoryTrace] = list(snapshot.memories)
    for intent in write_intents:
        if type(intent) is not MemoryUpdateIntent:
            raise TypeError(
                "orchestrate_offline_consolidation.write_intents: invalid_item_type"
            )
        if intent.owner_id != snapshot.owner_id:
            _log_owner_mismatch(snapshot.owner_id, tick)
            raise ValueError("orchestrate_offline_consolidation: owner_mismatch")
        if intent.kind is not MemoryUpdateKind.WRITE_MEMORY or intent.memory is None:
            continue
        combined.append(intent.memory)
    combined.sort(key=lambda item: item.memory_id.value)
    if len(combined) > _MAX_TRACES:
        omitted = len(combined) - _MAX_TRACES
        _LOG.warning(
            "offline_consolidation_truncated cap=%s omitted_count=%s "
            "owner_id=%s tick=%s",
            _MAX_TRACES,
            omitted,
            snapshot.owner_id.value,
            tick,
        )
        combined = combined[:_MAX_TRACES]
    return tuple(combined)


def _affected_ids(selection: OfflineConsolidationSelection) -> frozenset[MemoryId]:
    ids: set[MemoryId] = set(selection.soft_forget_ids)
    for group in selection.merge_groups:
        ids.update(group)
    return frozenset(ids)


def _belief_revisions(
    *,
    traces: Sequence[MemoryTrace],
    selection: OfflineConsolidationSelection,
    owner_id: AgentId,
    tick: int,
) -> tuple[BeliefRevisionRequest, ...]:
    if not selection.belief_source_ids:
        return ()
    wanted = set(selection.belief_source_ids)
    sources = [trace for trace in traces if trace.memory_id in wanted]
    candidates = extract_evidence_candidates(
        sources,
        owner_id=owner_id,
        policy=DEFAULT_BELIEF_FORMATION_POLICY,
    )
    minimum = DEFAULT_BELIEF_FORMATION_POLICY.min_independent_observations
    by_claim: dict[str, list[object]] = {}
    for candidate in candidates:
        if candidate.memory_id not in wanted:
            continue
        by_claim.setdefault(canonical_claim_identity(candidate.claim), []).append(
            candidate
        )
    by_belief: dict[str, list[object]] = {}
    claims_for_belief: dict[str, object] = {}
    for identity in sorted(by_claim):
        group = by_claim[identity]
        memory_ids = {item.memory_id for item in group}
        if len(memory_ids) < minimum:
            continue
        claim = group[0].claim
        belief_id = belief_id_for_claim(owner_id=owner_id, claim=claim).value
        by_belief.setdefault(belief_id, []).extend(group)
        claims_for_belief.setdefault(belief_id, claim)
    revisions: list[BeliefRevisionRequest] = []
    for belief_key in sorted(by_belief):
        group = tuple(by_belief[belief_key])
        claim = claims_for_belief[belief_key]
        bundle = bundle_from_candidates(group, target_claim=claim)
        belief_id = belief_id_for_claim(owner_id=owner_id, claim=claim)
        revisions.append(
            BeliefRevisionRequest(
                owner_id=owner_id,
                operation_id=f"offline-consol-belief-{tick}-{belief_id.value}",
                logical_tick=tick,
                claim=claim,
                evidence=bundle,
                policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
                belief_id=belief_id,
            )
        )
    return tuple(revisions)


def _claim_references_owner(claim: SemanticClaim, owner_id: AgentId) -> bool:
    subject = claim.subject
    if (
        subject.kind is ClaimSubjectKind.AGENT
        and subject.agent_id is not None
        and subject.agent_id == owner_id
    ):
        return True
    value = claim.value
    if (
        value.kind is BeliefValueKind.AGENT
        and value.agent_id is not None
        and value.agent_id == owner_id
    ):
        return True
    return False


def _supporting_mass(request: BeliefRevisionRequest) -> float:
    if not request.evidence.supporting:
        return 0.0
    return max(item.contribution for item in request.evidence.supporting)


def _relationship_revisions(
    *,
    snapshot: SubjectiveSnapshot,
    traces: Sequence[MemoryTrace],
    affected: frozenset[MemoryId],
    tick: int,
) -> tuple[tuple[RelationshipRevisionRequest, ...], tuple[str, ...]]:
    profiles = tuple(
        profile
        for profile in snapshot.relationships
        if type(profile) is DirectedRelationshipProfile
        and profile.source_id == snapshot.owner_id
    )
    by_target = {profile.target_id.value: profile for profile in profiles}
    requests: list[RelationshipRevisionRequest] = []
    relationship_ids: list[str] = []
    seen: set[str] = set()
    for trace in traces:
        if trace.memory_id not in affected:
            continue
        for entity in trace.entities:
            if entity.entity_id is None:
                continue
            profile = by_target.get(entity.entity_id.value)
            if profile is None or profile.target_id == snapshot.owner_id:
                continue
            if profile.relationship_id.value in seen:
                continue
            if profile.target_id == profile.source_id:
                continue
            seen.add(profile.relationship_id.value)
            relationship_ids.append(profile.relationship_id.value)
            kind = (
                RelationshipSignalKind.COMMUNICATION
                if trace.provenance.kind.value == "communicated"
                else RelationshipSignalKind.PROXIMITY
            )
            root = (
                trace.lineage.source_memory_ids[0].value
                if trace.lineage.source_memory_ids
                else trace.memory_id.value
            )
            requests.append(
                RelationshipRevisionRequest(
                    source_id=snapshot.owner_id,
                    target_id=profile.target_id,
                    operation_id=(
                        f"offline-consol-rel-{tick}-{profile.relationship_id.value}"
                    ),
                    logical_tick=tick,
                    signals=(
                        RelationshipInteractionSignal(
                            counterpart_id=profile.target_id,
                            kind=kind,
                            strength=trace.confidence,
                            memory_ref=trace.memory_id.value,
                            lineage_root_ref=root,
                            source_tick=trace.source_tick,
                        ),
                    ),
                    policy=profile.policy,
                    expected_revision_ordinal=profile.revision_ordinal,
                )
            )
    paired = sorted(
        zip(relationship_ids, requests, strict=True),
        key=lambda item: item[1].target_id.value,
    )
    if not paired:
        return (), ()
    ordered_ids, ordered_requests = zip(*paired, strict=True)
    return tuple(ordered_requests), tuple(ordered_ids)


def _goal_intents(
    *,
    snapshot: SubjectiveSnapshot,
    affected: frozenset[MemoryId],
    tick: int,
) -> tuple[GoalTransitionIntent, ...]:
    affected_values = {memory_id.value for memory_id in affected}
    goals_by_id = {goal.goal_id: goal for goal in snapshot.goals}
    intents: list[GoalTransitionIntent] = []
    for goal in snapshot.goals:
        if goal.status is not GoalStatus.ACTIVE:
            continue
        if not any(ref in affected_values for ref in goal.belief_refs):
            continue
        if _owned_by_goal_manager(goal, goals_by_id=goals_by_id, tick=tick):
            continue
        intents.append(
            GoalTransitionIntent(
                goal_id=goal.goal_id,
                owner_id=snapshot.owner_id,
                from_status=goal.status,
                to_status=GoalStatus.SUSPENDED,
                reason_code=GoalTransitionIntentReason.SUSPENDED,
                tick=tick,
            )
        )
    return tuple(intents)


def _owned_by_goal_manager(
    goal: Goal, *, goals_by_id: dict[object, Goal], tick: int
) -> bool:
    if goal.deadline_tick is not None and tick > goal.deadline_tick:
        return True
    if goal.parent_goal_id is None:
        return False
    parent = goals_by_id.get(goal.parent_goal_id)
    return parent is not None and parent.status in _TERMINAL_PARENT


def _audit(
    *,
    snapshot: SubjectiveSnapshot,
    selection: OfflineConsolidationSelection,
    mode: str,
    beliefs: tuple[BeliefRevisionRequest, ...],
    relationship_ids: tuple[str, ...],
    goals: tuple[GoalTransitionIntent, ...],
) -> OfflineConsolidationAudit:
    memory_ids = sorted(
        set(selection.strengthen_ids)
        | set(selection.soft_forget_ids)
        | {memory_id for group in selection.merge_groups for memory_id in group},
        key=lambda item: item.value,
    )
    return OfflineConsolidationAudit(
        owner_id=snapshot.owner_id,
        tick=selection.tick,
        mode=mode,
        memory_ids=tuple(memory_ids),
        belief_ids=tuple(
            request.belief_id
            for request in beliefs
            if request.belief_id is not None
        ),
        relationship_ids=relationship_ids,
        goal_ids=tuple(intent.goal_id for intent in goals),
        strengthen_ids=selection.strengthen_ids,
        soft_forget_ids=selection.soft_forget_ids,
        merge_groups=selection.merge_groups,
        reason_codes=selection.reason_codes,
        fallback_used=selection.fallback_used,
    )


_PROMPT_NAME: Final[str] = "offline_consolidation"
_PROMPT_VERSION: Final[str] = "v1"
_SCHEMA_VERSION: Final[str] = "offline_consolidation.selection.v1"


class OfflineConsolidationSelectionOutput(StructuredOutput):
    """ID lists only. Prose claims are rejected by the closed schema."""

    strengthen_ids: tuple[str, ...]
    soft_forget_ids: tuple[str, ...]
    merge_group_keys: tuple[str, ...]
    belief_source_ids: tuple[str, ...]


class LLMOfflineConsolidationSelector:
    """Restrict a deterministic selection to provider-chosen candidate IDs."""

    __slots__ = ("_provider",)

    def __init__(self, provider: LLMProvider | None) -> None:
        self._provider = provider

    async def restrict(
        self,
        selection: OfflineConsolidationSelection,
        *,
        policy: OfflineConsolidationPolicy,
    ) -> OfflineConsolidationSelection:
        if type(selection) is not OfflineConsolidationSelection:
            raise TypeError("LLMOfflineConsolidationSelector: invalid_selection")
        if type(policy) is not OfflineConsolidationPolicy:
            raise TypeError("LLMOfflineConsolidationSelector: invalid_policy")
        if not policy.allow_provider or self._provider is None:
            _LOG.debug(
                "offline_consolidation_llm_complete prompt_version=%s "
                "schema_version=%s candidate_count=%s selected_count=%s "
                "used_provider=%s fallback_used=%s",
                _PROMPT_VERSION,
                _SCHEMA_VERSION,
                _candidate_count(selection),
                _candidate_count(selection),
                False,
                True,
            )
            return _mark_fallback(selection)
        _LOG.debug(
            "offline_consolidation_llm_start prompt_version=%s "
            "schema_version=%s candidate_count=%s",
            _PROMPT_VERSION,
            _SCHEMA_VERSION,
            _candidate_count(selection),
        )
        try:
            output = await self._generate(selection)
            restricted = _restrict_selection(selection, output)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            reason = "provider_error"
            if isinstance(exc, LLMError):
                reason = "provider_error"
            elif type(exc) is ValueError and str(exc) in {
                "foreign_id",
                "schema_invalid",
            }:
                reason = str(exc)
            _LOG.error(
                "offline_consolidation_llm_rejected reason_code=%s",
                reason,
            )
            return _mark_fallback(selection)
        _LOG.debug(
            "offline_consolidation_llm_complete prompt_version=%s "
            "schema_version=%s candidate_count=%s selected_count=%s "
            "used_provider=%s fallback_used=%s",
            _PROMPT_VERSION,
            _SCHEMA_VERSION,
            _candidate_count(selection),
            _candidate_count(restricted),
            True,
            False,
        )
        return restricted

    async def _generate(
        self, selection: OfflineConsolidationSelection
    ) -> OfflineConsolidationSelectionOutput:
        payload = {
            "strengthen_ids": [item.value for item in selection.strengthen_ids],
            "soft_forget_ids": [item.value for item in selection.soft_forget_ids],
            "merge_group_keys": [
                _group_key(group) for group in selection.merge_groups
            ],
            "belief_source_ids": [
                item.value for item in selection.belief_source_ids
            ],
            "reason_codes": [code.value for code in selection.reason_codes],
        }
        rendered = render_prompt(
            _PROMPT_NAME,
            _PROMPT_VERSION,
            {
                "schema_name": _SCHEMA_VERSION,
                "schema_json": json.dumps(
                    OfflineConsolidationSelectionOutput.model_json_schema(),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "candidate_json": json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                ),
            },
        )
        assert self._provider is not None
        result = await self._provider.generate(
            LLMRequest(
                messages=rendered.messages,
                response_model=OfflineConsolidationSelectionOutput,
                context=LLMRequestContext(
                    run_id="offline-consolidation",
                    agent_id=selection.owner_id.value,
                    tick=selection.tick,
                    llm_request_id=(
                        f"offline-consolidation-{selection.tick}-"
                        f"{selection.owner_id.value}"
                    ),
                ),
                prompt=rendered.reference,
            )
        )
        output = result.output
        if type(output) is not OfflineConsolidationSelectionOutput:
            raise ValueError("schema_invalid")
        return output


def _candidate_count(selection: OfflineConsolidationSelection) -> int:
    return (
        len(selection.strengthen_ids)
        + len(selection.soft_forget_ids)
        + len(selection.merge_groups)
        + len(selection.belief_source_ids)
    )


def _group_key(group: tuple[MemoryId, ...]) -> str:
    return "|".join(memory_id.value for memory_id in group)


def _mark_fallback(
    selection: OfflineConsolidationSelection,
) -> OfflineConsolidationSelection:
    codes = (
        *(
            code
            for code in selection.reason_codes
            if code is not OfflineConsolidationReasonCode.FALLBACK_DETERMINISTIC
        ),
        OfflineConsolidationReasonCode.FALLBACK_DETERMINISTIC,
    )
    return replace(
        selection,
        reason_codes=codes,
        used_provider=False,
        fallback_used=True,
    )


def _restrict_selection(
    selection: OfflineConsolidationSelection,
    output: OfflineConsolidationSelectionOutput,
) -> OfflineConsolidationSelection:
    strengthen = _subset_ids(
        output.strengthen_ids, selection.strengthen_ids, label="strengthen_ids"
    )
    forget = _subset_ids(
        output.soft_forget_ids, selection.soft_forget_ids, label="soft_forget_ids"
    )
    beliefs = _subset_ids(
        output.belief_source_ids,
        selection.belief_source_ids,
        label="belief_source_ids",
    )
    allowed = {_group_key(group): group for group in selection.merge_groups}
    groups: list[tuple[MemoryId, ...]] = []
    seen_keys: set[str] = set()
    for key in output.merge_group_keys:
        if type(key) is not str or key not in allowed or key in seen_keys:
            raise ValueError("foreign_id")
        seen_keys.add(key)
        groups.append(allowed[key])
    derived = tuple(
        trace
        for trace in selection.derived_traces
        if _group_key(trace.lineage.source_memory_ids) in seen_keys
    )
    codes: list[OfflineConsolidationReasonCode] = []
    if groups:
        codes.append(OfflineConsolidationReasonCode.REPEATED_PATTERN)
        codes.append(OfflineConsolidationReasonCode.MERGED)
    if strengthen:
        codes.append(OfflineConsolidationReasonCode.STRENGTHENED)
    if forget:
        codes.append(OfflineConsolidationReasonCode.LOW_RETENTION)
        codes.append(OfflineConsolidationReasonCode.SOFT_FORGOTTEN)
    if beliefs:
        codes.append(OfflineConsolidationReasonCode.BELIEF_CANDIDATE)
    return replace(
        selection,
        merge_groups=tuple(groups),
        strengthen_ids=strengthen,
        soft_forget_ids=forget,
        belief_source_ids=beliefs,
        derived_traces=derived,
        reason_codes=tuple(codes),
        used_provider=True,
        fallback_used=False,
    )


def _subset_ids(
    chosen: tuple[str, ...],
    allowed: tuple[MemoryId, ...],
    *,
    label: str,
) -> tuple[MemoryId, ...]:
    _ = label
    if isinstance(chosen, (str, bytes)) or not isinstance(chosen, tuple):
        raise ValueError("schema_invalid")
    index = {item.value: item for item in allowed}
    selected: list[MemoryId] = []
    seen: set[str] = set()
    for value in chosen:
        if type(value) is not str or value not in index or value in seen:
            raise ValueError("foreign_id")
        seen.add(value)
        selected.append(index[value])
    return tuple(selected)
