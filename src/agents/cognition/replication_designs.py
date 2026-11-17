"""Frozen replication design identity, freezing, and adoption.

Pure owner-safe functions only. Nothing here reads world authority, another
owner's ledger, or a private catalog.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from agents.cognition.experimentation import (
    ExperimentHypothesis,
    ExperimentTrial,
    HypothesisCondition,
    conditions_hold,
    observed_condition_tokens,
)
from agents.cognition.production import observed_experiment_operand_ids
from agents.cognition.replication import (
    MAX_DELIVERY_RECEIPTS,
    REPLICATION_POLICY_VERSION,
    ExperimentDesign,
    ExperimentSelector,
    ReplicationBindingMode,
    ReplicationConditionComparison,
    ReplicationError,
    ReplicationLedger,
    ReplicationNoticeCode,
    ReplicationReceipt,
    ReplicationRelationKind,
    ReplicationSelectorFamily,
    ReplicationSourceDraft,
    append_replication_design,
    replication_ref,
)
from agents.models import AgentId
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.replication_designs"
)

_DESIGN_HEX_LEN: Final[int] = 32


def _selector_payload(
    selector: ExperimentSelector | None,
) -> dict[str, object] | None:
    if selector is None:
        return None
    return {
        "binding_mode": selector.binding_mode.value,
        "exact_entity_id": selector.exact_entity_id,
        "family": selector.family.value,
        "kind": selector.kind,
    }


def design_payload(design: ExperimentDesign) -> dict[str, object]:
    """Return the exact eleven-field design preimage body."""

    return {
        "conditions": [
            {"slot": row.slot.value, "value_token": row.value_token}
            for row in design.conditions
        ],
        "created_tick": design.created_tick,
        "operand_a_selector": _selector_payload(design.operand_a_selector),
        "operand_b_selector": _selector_payload(design.operand_b_selector),
        "operator": design.operator.value,
        "origin_token": design.origin_token,
        "parent_design_token": design.parent_design_token,
        "predicted_outcome": (
            None
            if design.predicted_outcome is None
            else design.predicted_outcome.value
        ),
        "process_token": design.process_token.value,
        "source_hypothesis_token": design.source_hypothesis_token,
        "source_trial_token": design.source_trial_token,
    }


def design_preimage(design: ExperimentDesign) -> dict[str, object]:
    """Return the full hash preimage including the locked policy version."""

    return {
        "design": design_payload(design),
        "policy_version": REPLICATION_POLICY_VERSION,
    }


def design_token_for(design: ExperimentDesign) -> str:
    """Recompute the design token from its full non-self-referential payload."""

    material = json.dumps(
        design_preimage(design),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    digest = hashlib.sha256(material.encode("ascii")).hexdigest()[:_DESIGN_HEX_LEN]
    return f"rdes-{digest}"


def verify_replication_design(design: object) -> bool:
    """Return whether the token matches the full canonical content."""

    if type(design) is not ExperimentDesign:
        raise ReplicationError("replication_invalid_design")
    expected = design_token_for(design)
    return expected == design.design_token


def build_experiment_design(
    *,
    origin_token: str,
    parent_design_token: str | None,
    source_hypothesis_token: str,
    source_trial_token: str,
    created_tick: int,
    operator: ExperimentOperator,
    process_token: ExperimentProcessToken,
    operand_a_selector: ExperimentSelector,
    operand_b_selector: ExperimentSelector | None,
    predicted_outcome: ExperimentOutcomeClass | None,
    conditions: Sequence[HypothesisCondition],
) -> ExperimentDesign:
    """Construct a design and derive its token from the content itself."""

    body = ExperimentDesign(
        design_token="rdes-" + "0" * _DESIGN_HEX_LEN,
        origin_token=origin_token,
        parent_design_token=parent_design_token,
        source_hypothesis_token=source_hypothesis_token,
        source_trial_token=source_trial_token,
        created_tick=created_tick,
        operator=operator,
        process_token=process_token,
        operand_a_selector=operand_a_selector,
        operand_b_selector=operand_b_selector,
        predicted_outcome=predicted_outcome,
        conditions=tuple(conditions),
    )
    token = design_token_for(body)
    design = ExperimentDesign(
        design_token=token,
        origin_token=body.origin_token,
        parent_design_token=body.parent_design_token,
        source_hypothesis_token=body.source_hypothesis_token,
        source_trial_token=body.source_trial_token,
        created_tick=body.created_tick,
        operator=body.operator,
        process_token=body.process_token,
        operand_a_selector=body.operand_a_selector,
        operand_b_selector=body.operand_b_selector,
        predicted_outcome=body.predicted_outcome,
        conditions=body.conditions,
    )
    _LOG.debug(
        "replication_design_built design_prefix=%s condition_count=%s",
        design.design_token[:12],
        len(design.conditions),
    )
    return design


@dataclass(frozen=True, slots=True)
class ReplicationDesignResult:
    """One frozen design plus a closed reason. Missing data stays missing."""

    design: ExperimentDesign | None
    reason: str
    notice: ReplicationNoticeCode | None = None

    def __post_init__(self) -> None:
        if self.design is not None and type(self.design) is not ExperimentDesign:
            raise ReplicationError("replication_invalid_design")
        if type(self.reason) is not str or not self.reason:
            raise ReplicationError("replication_invalid_reason")
        if self.notice is not None and type(self.notice) is not ReplicationNoticeCode:
            raise ReplicationError("replication_invalid_notice")


def _actor_entity_id(observation: object) -> str | None:
    body = getattr(observation, "self_body", None)
    candidate = getattr(observation, "observer_id", None)
    if candidate is None and body is not None:
        candidate = getattr(body, "entity_id", None)
    value = getattr(candidate, "value", None)
    if type(value) is str and value:
        return value
    return None


def _selector_for_operand(
    observation: object, operand_id: str
) -> ExperimentSelector | None:
    family_items: tuple[tuple[str, ReplicationSelectorFamily, object], ...] = (
        ("items", ReplicationSelectorFamily.ITEM, None),
        ("resources", ReplicationSelectorFamily.RESOURCE, None),
        ("structures", ReplicationSelectorFamily.STRUCTURE, None),
        ("artifacts", ReplicationSelectorFamily.ARTIFACT, None),
    )
    for attribute, family, _marker in family_items:
        rows = getattr(observation, attribute, ())
        if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
            continue
        for row in rows:
            entity_id = getattr(row, "entity_id", None)
            if getattr(entity_id, "value", None) != operand_id:
                continue
            kind = getattr(row, "kind", None)
            token = getattr(kind, "value", None)
            if type(token) is not str or not token:
                return None
            return ExperimentSelector(
                family=family,
                kind=token,
                binding_mode=ReplicationBindingMode.EXACT,
                exact_entity_id=operand_id,
            )
    return None


def _predicted(hypothesis: ExperimentHypothesis) -> ExperimentOutcomeClass | None:
    value = hypothesis.predicted_outcome
    if value is None:
        return None
    return ExperimentOutcomeClass(value)


def freeze_experiment_design(
    owner_id: AgentId,
    hypothesis: ExperimentHypothesis,
    trial: ExperimentTrial,
    observation: object,
    *,
    parent_design_token: str | None = None,
) -> ReplicationDesignResult:
    """Freeze an owner's completed original test from visible descriptors."""

    if type(owner_id) is not AgentId:
        raise ReplicationError("replication_invalid_owner")
    if type(hypothesis) is not ExperimentHypothesis:
        raise ReplicationError("replication_invalid_hypothesis")
    if hypothesis.owner_id != owner_id:
        raise ReplicationError("replication_hypothesis_owner_mismatch")
    if type(trial) is not ExperimentTrial:
        raise ReplicationError("replication_invalid_trial")
    actor = _actor_entity_id(observation)
    if actor is None:
        _LOG.debug(
            "replication_design_unavailable reason_code=%s",
            "missing_actor",
        )
        return ReplicationDesignResult(
            None,
            "design_unavailable",
            ReplicationNoticeCode.DESIGN_UNAVAILABLE,
        )
    selector_a = _selector_for_operand(observation, hypothesis.operand_a_id)
    selector_b = (
        None
        if hypothesis.operand_b_id is None
        else _selector_for_operand(observation, hypothesis.operand_b_id)
    )
    if selector_a is None or (
        hypothesis.operand_b_id is not None and selector_b is None
    ):
        _LOG.debug(
            "replication_design_unavailable reason_code=%s",
            "missing_operand_descriptor",
        )
        return ReplicationDesignResult(
            None,
            "design_unavailable",
            ReplicationNoticeCode.DESIGN_UNAVAILABLE,
        )
    hypothesis_token = replication_ref(
        "rhyp", owner_id.value, hypothesis.hypothesis_id
    )
    trial_token = replication_ref("rtrl", actor, trial.event_id)
    origin_token = replication_ref(
        "rorg", owner_id.value, hypothesis.hypothesis_id, trial.event_id
    )
    created_tick = getattr(observation, "tick", 0)
    if isinstance(created_tick, bool) or type(created_tick) is not int:
        created_tick = trial.tick
    design = build_experiment_design(
        origin_token=origin_token,
        parent_design_token=parent_design_token,
        source_hypothesis_token=hypothesis_token,
        source_trial_token=trial_token,
        created_tick=created_tick,
        operator=hypothesis.operator,
        process_token=hypothesis.process_token,
        operand_a_selector=selector_a,
        operand_b_selector=selector_b,
        predicted_outcome=_predicted(hypothesis),
        conditions=hypothesis.conditions,
    )
    _LOG.debug(
        "replication_design_frozen owner_id=%s design_prefix=%s",
        owner_id.value,
        design.design_token[:12],
    )
    return ReplicationDesignResult(design, "frozen")


def adopt_replication_design(
    owner_id: AgentId,
    ledger: ReplicationLedger,
    design: ExperimentDesign,
    *,
    delivery_event_id: str,
    received_tick: int,
    inviter_entity_id: str | None = None,
) -> tuple[ReplicationLedger, str]:
    """Adopt a transmitted design after recomputing its full-content token."""

    if type(owner_id) is not AgentId:
        raise ReplicationError("replication_invalid_owner")
    if ledger.owner_id != owner_id:
        raise ReplicationError("replication_ledger_owner_mismatch")
    if type(design) is not ExperimentDesign:
        raise ReplicationError("replication_invalid_design")
    if not verify_replication_design(design):
        _LOG.warning(
            "replication_design_dropped reason_code=%s", "identity_mismatch"
        )
        return ledger, "design_identity_mismatch"
    for receipt in ledger.receipts:
        if (
            receipt.design_token == design.design_token
            and receipt.delivery_event_id == delivery_event_id
        ):
            return ledger, "duplicate_delivery"
    updated, reason = append_replication_design(ledger, design)
    if reason not in {"design_adopted", "duplicate_design"}:
        return updated, reason
    if len(updated.receipts) >= MAX_DELIVERY_RECEIPTS:
        return updated, "receipt_capacity"
    receipt = ReplicationReceipt(
        owner_id=owner_id,
        design_token=design.design_token,
        origin_token=design.origin_token,
        delivery_event_id=delivery_event_id,
        received_tick=received_tick,
        inviter_entity_id=inviter_entity_id,
    )
    _LOG.debug(
        "replication_design_adopted owner_id=%s design_prefix=%s",
        owner_id.value,
        design.design_token[:12],
    )
    return (
        ReplicationLedger(
            owner_id=updated.owner_id,
            policy_version=updated.policy_version,
            source_drafts=updated.source_drafts,
            designs=updated.designs,
            attempts=updated.attempts,
            reports=updated.reports,
            collaborations=updated.collaborations,
            interpretations=updated.interpretations,
            outbox=updated.outbox,
            receipts=(*updated.receipts, receipt),
            notices=updated.notices,
        ),
        "design_adopted",
    )


def source_draft_for_hypothesis(
    owner_id: AgentId,
    hypothesis: ExperimentHypothesis,
    observation: object,
) -> ReplicationSourceDraft | None:
    """Capture pre-action descriptors for an original owner test."""

    if type(owner_id) is not AgentId:
        raise ReplicationError("replication_invalid_owner")
    if type(hypothesis) is not ExperimentHypothesis:
        raise ReplicationError("replication_invalid_hypothesis")
    if hypothesis.owner_id != owner_id:
        raise ReplicationError("replication_hypothesis_owner_mismatch")
    actor = _actor_entity_id(observation)
    if actor is None:
        return None
    selector_a = _selector_for_operand(observation, hypothesis.operand_a_id)
    selector_b = (
        None
        if hypothesis.operand_b_id is None
        else _selector_for_operand(observation, hypothesis.operand_b_id)
    )
    if selector_a is None or (
        hypothesis.operand_b_id is not None and selector_b is None
    ):
        return None
    selector_a = ExperimentSelector(
        family=selector_a.family,
        kind=selector_a.kind,
        binding_mode=ReplicationBindingMode.SAME_KIND,
    )
    if selector_b is not None:
        selector_b = ExperimentSelector(
            family=selector_b.family,
            kind=selector_b.kind,
            binding_mode=ReplicationBindingMode.SAME_KIND,
        )
    tick_raw = getattr(observation, "tick", 0)
    tick = tick_raw if type(tick_raw) is int and tick_raw >= 0 else 0
    return ReplicationSourceDraft(
        owner_id=owner_id,
        actor_entity_id=actor,
        created_tick=tick,
        hypothesis_id=hypothesis.hypothesis_id,
        operator=hypothesis.operator,
        process_token=hypothesis.process_token,
        operand_a_selector=selector_a,
        operand_b_selector=selector_b,
        predicted_outcome=_predicted(hypothesis),
        conditions=hypothesis.conditions,
    )


def freeze_source_design_from_draft(
    draft: ReplicationSourceDraft,
    trial: ExperimentTrial,
) -> ReplicationDesignResult:
    """Freeze a retained pre-action draft after an actor-visible result."""

    if type(draft) is not ReplicationSourceDraft:
        raise ReplicationError("replication_invalid_draft")
    if type(trial) is not ExperimentTrial:
        raise ReplicationError("replication_invalid_trial")
    hypothesis_token = replication_ref(
        "rhyp", draft.owner_id.value, draft.hypothesis_id
    )
    trial_token = replication_ref("rtrl", draft.actor_entity_id, trial.event_id)
    origin_token = replication_ref(
        "rorg",
        draft.owner_id.value,
        draft.hypothesis_id,
        trial.event_id,
    )
    design = build_experiment_design(
        origin_token=origin_token,
        parent_design_token=None,
        source_hypothesis_token=hypothesis_token,
        source_trial_token=trial_token,
        created_tick=trial.tick,
        operator=draft.operator,
        process_token=draft.process_token,
        operand_a_selector=draft.operand_a_selector,
        operand_b_selector=draft.operand_b_selector,
        predicted_outcome=draft.predicted_outcome,
        conditions=draft.conditions,
    )
    return ReplicationDesignResult(design, "frozen")


@dataclass(frozen=True, slots=True)
class ReplicationConditionDiff:
    """Slot names only. No condition values leave this comparison."""

    comparison: ReplicationConditionComparison
    slots: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.comparison) is not ReplicationConditionComparison:
            raise ReplicationError("replication_invalid_comparison")
        if not isinstance(self.slots, tuple):
            raise ReplicationError("replication_invalid_comparison")
        for slot in self.slots:
            if type(slot) is not str or not slot:
                raise ReplicationError("replication_invalid_comparison")
        if len(set(self.slots)) != len(self.slots):
            raise ReplicationError("replication_invalid_comparison")


def compare_replication_conditions(
    design_conditions: Sequence[HypothesisCondition],
    actual_conditions: Sequence[HypothesisCondition],
) -> ReplicationConditionDiff:
    """Compare declared and observed slots without claiming full control."""

    declared = {row.slot.value: row.value_token for row in design_conditions}
    actual = {row.slot.value: row.value_token for row in actual_conditions}
    if not declared or not actual:
        return ReplicationConditionDiff(
            ReplicationConditionComparison.UNKNOWN,
            tuple(sorted(declared)),
        )
    missing = tuple(sorted(slot for slot in declared if slot not in actual))
    mismatched = tuple(
        sorted(
            slot
            for slot in declared
            if slot in actual and actual[slot] != declared[slot]
        )
    )
    if missing:
        return ReplicationConditionDiff(
            ReplicationConditionComparison.UNKNOWN,
            (*missing, *mismatched),
        )
    if mismatched:
        return ReplicationConditionDiff(
            ReplicationConditionComparison.DIFFERENT, mismatched
        )
    return ReplicationConditionDiff(ReplicationConditionComparison.MATCHED)


@dataclass(frozen=True, slots=True)
class ReplicationBinding:
    """Concrete owner-visible operands for one design. Non-authoritative."""

    design_token: str
    operand_a_id: str
    operand_b_id: str | None
    observed_conditions: tuple[HypothesisCondition, ...]
    condition_comparison: ReplicationConditionComparison
    relation_kind: ReplicationRelationKind = ReplicationRelationKind.REPEAT

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "design_token", _require_design_token(self.design_token)
        )
        for name in ("operand_a_id", "operand_b_id"):
            value = getattr(self, name)
            if value is not None and (type(value) is not str or not value):
                raise ReplicationError("replication_invalid_operand")
        if type(self.observed_conditions) is not tuple:
            raise ReplicationError("replication_invalid_conditions")
        if type(self.condition_comparison) is not ReplicationConditionComparison:
            raise ReplicationError("replication_invalid_comparison")
        if type(self.relation_kind) is not ReplicationRelationKind:
            raise ReplicationError("replication_invalid_relation")


def _require_design_token(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith("rdes-")
        or len(value) != len("rdes-") + 32
    ):
        raise ReplicationError("replication_invalid_id")
    return value


@dataclass(frozen=True, slots=True)
class ReplicationBindingResult:
    """One binding attempt with a closed skip reason."""

    binding: ReplicationBinding | None
    reason: str
    notice: ReplicationNoticeCode | None = None

    def __post_init__(self) -> None:
        if self.binding is not None and type(self.binding) is not ReplicationBinding:
            raise ReplicationError("replication_invalid_binding")
        if type(self.reason) is not str or not self.reason:
            raise ReplicationError("replication_invalid_reason")
        if self.notice is not None and type(self.notice) is not ReplicationNoticeCode:
            raise ReplicationError("replication_invalid_notice")


_FAMILY_ATTRIBUTES: Final[tuple[tuple[str, ReplicationSelectorFamily], ...]] = (
    ("items", ReplicationSelectorFamily.ITEM),
    ("resources", ReplicationSelectorFamily.RESOURCE),
    ("structures", ReplicationSelectorFamily.STRUCTURE),
    ("artifacts", ReplicationSelectorFamily.ARTIFACT),
)


def _visible_rows(
    observation: object,
) -> dict[str, tuple[ReplicationSelectorFamily, object]]:
    admitted = set(observed_experiment_operand_ids(observation))
    visible: dict[str, tuple[ReplicationSelectorFamily, object]] = {}
    for attribute, family in _FAMILY_ATTRIBUTES:
        rows = getattr(observation, attribute, ())
        if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
            continue
        for row in rows:
            entity_id = getattr(getattr(row, "entity_id", None), "value", None)
            if type(entity_id) is not str or entity_id not in admitted:
                continue
            visible[entity_id] = (family, row)
    return visible


def _kind_token(row: object) -> str | None:
    token = getattr(getattr(row, "kind", None), "value", None)
    return token if type(token) is str and token else None


def _usable(family: ReplicationSelectorFamily, row: object) -> bool:
    if family is ReplicationSelectorFamily.RESOURCE:
        quantity = getattr(row, "quantity", None)
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
            return False
        return float(quantity) >= 1.0
    if family is ReplicationSelectorFamily.STRUCTURE:
        integrity = getattr(row, "integrity", None)
        if isinstance(integrity, bool) or not isinstance(integrity, (int, float)):
            return False
        return float(integrity) > 0.0
    if family is ReplicationSelectorFamily.ITEM:
        placement = getattr(getattr(row, "placement", None), "value", None)
        return placement in {"held_by_self", "ground_here", "corpse_here"}
    return True


def _resolve_selector(
    selector: ExperimentSelector,
    visible: dict[str, tuple[ReplicationSelectorFamily, object]],
    used: set[str],
) -> str | None:
    if selector.binding_mode is ReplicationBindingMode.EXACT:
        candidate = selector.exact_entity_id
        if candidate is None or candidate in used or candidate not in visible:
            return None
        family, row = visible[candidate]
        if family is not selector.family or _kind_token(row) != selector.kind:
            return None
        return candidate if _usable(family, row) else None
    matches: list[str] = []
    for entity_id, (family, row) in visible.items():
        if entity_id in used or family is not selector.family:
            continue
        if _kind_token(row) != selector.kind:
            continue
        if not _usable(family, row):
            continue
        matches.append(entity_id)
    return sorted(matches)[0] if matches else None


def _observed_conditions_for(
    design: ExperimentDesign, observation: object
) -> tuple[HypothesisCondition, ...]:
    tokens = observed_condition_tokens(observation)
    rows: list[HypothesisCondition] = []
    for condition in design.conditions:
        values = tokens.get(condition.slot, ())
        if values:
            rows.append(
                HypothesisCondition(condition.slot, values[0])
            )
    return tuple(sorted(rows, key=lambda row: row.slot.value))


def bind_replication_design(
    design: ExperimentDesign, observation: object
) -> ReplicationBindingResult:
    """Bind one frozen design to currently observable owner materials."""

    if type(design) is not ExperimentDesign:
        raise ReplicationError("replication_invalid_design")
    visible = _visible_rows(observation)
    used: set[str] = set()
    operand_a = _resolve_selector(design.operand_a_selector, visible, used)
    if operand_a is None:
        return ReplicationBindingResult(
            None, "selector_unavailable", ReplicationNoticeCode.SELECTOR_UNAVAILABLE
        )
    used.add(operand_a)
    operand_b: str | None = None
    if design.operand_b_selector is not None:
        operand_b = _resolve_selector(design.operand_b_selector, visible, used)
        if operand_b is None:
            return ReplicationBindingResult(
                None,
                "duplicate_operand",
                ReplicationNoticeCode.SELECTOR_UNAVAILABLE,
            )
        used.add(operand_b)
    if not conditions_hold(design.conditions, observation):
        return ReplicationBindingResult(
            None, "condition_unsatisfied", ReplicationNoticeCode.CONDITION_UNKNOWN
        )
    actual = _observed_conditions_for(design, observation)
    diff = compare_replication_conditions(design.conditions, actual)
    binding = ReplicationBinding(
        design_token=design.design_token,
        operand_a_id=operand_a,
        operand_b_id=operand_b,
        observed_conditions=actual,
        condition_comparison=diff.comparison,
    )
    _LOG.debug(
        "replication_design_bound design_prefix=%s comparison=%s",
        design.design_token[:12],
        diff.comparison.value,
    )
    return ReplicationBindingResult(binding, "bound")


def adapt_replication_design(
    parent: ExperimentDesign,
    *,
    operand_a_selector: ExperimentSelector,
    operand_b_selector: ExperimentSelector | None,
    conditions: Sequence[HypothesisCondition],
    created_tick: int,
    predicted_outcome: ExperimentOutcomeClass | None = None,
) -> ExperimentDesign:
    """Create an explicit parent-linked adapted procedure.

    A caller must change at least one selector, condition, or the prediction;
    otherwise the design is not an adaptation and fails closed.
    """

    if type(parent) is not ExperimentDesign:
        raise ReplicationError("replication_invalid_design")
    normalized = tuple(sorted(conditions, key=lambda row: row.slot.value))
    unchanged = (
        operand_a_selector == parent.operand_a_selector
        and operand_b_selector == parent.operand_b_selector
        and normalized == parent.conditions
        and predicted_outcome is parent.predicted_outcome
    )
    if unchanged:
        raise ReplicationError("replication_design_not_adapted")
    return build_experiment_design(
        origin_token=parent.origin_token,
        parent_design_token=parent.design_token,
        source_hypothesis_token=parent.source_hypothesis_token,
        source_trial_token=parent.source_trial_token,
        created_tick=created_tick,
        operator=parent.operator,
        process_token=parent.process_token,
        operand_a_selector=operand_a_selector,
        operand_b_selector=operand_b_selector,
        predicted_outcome=predicted_outcome,
        conditions=normalized,
    )


__all__ = [
    "ReplicationBinding",
    "ReplicationBindingResult",
    "ReplicationConditionDiff",
    "ReplicationDesignResult",
    "adapt_replication_design",
    "adopt_replication_design",
    "bind_replication_design",
    "build_experiment_design",
    "compare_replication_conditions",
    "design_payload",
    "design_preimage",
    "design_token_for",
    "freeze_experiment_design",
    "freeze_source_design_from_draft",
    "replication_ref",
    "source_draft_for_hypothesis",
    "verify_replication_design",
]
