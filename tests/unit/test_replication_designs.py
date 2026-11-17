# mypy: ignore-errors
"""V4-28 design freezing, adaptation, and delivered adoption."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from agents.cognition import (
    ExperimentDesign,
    ExperimentSelector,
    ReplicationBindingMode,
    ReplicationConditionComparison,
    ReplicationError,
    ReplicationNoticeCode,
    ReplicationSelectorFamily,
    adapt_replication_design,
    adopt_replication_design,
    bind_replication_design,
    build_experiment_design,
    compare_replication_conditions,
    design_token_for,
    empty_replication_ledger,
    freeze_experiment_design,
    replication_ref,
    verify_replication_design,
)
from agents.cognition.experimentation import (
    ExperimentHypothesis,
    ExperimentTrial,
    HypothesisCondition,
    HypothesisConditionSlot,
    experiment_hypothesis_id,
)
from agents.models import AgentId
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId
from world.values import ItemKind

pytestmark = pytest.mark.unit

OWNER = AgentId("owner-1")
OTHER = AgentId("owner-2")


def _observation(*, items: tuple[tuple[str, ItemKind], ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(
        observer_id=EntityId("body-owner"),
        tick=3,
        items=tuple(
            SimpleNamespace(
                entity_id=EntityId(entity_id),
                kind=kind,
                placement=SimpleNamespace(value="held_by_self"),
            )
            for entity_id, kind in items
        ),
        resources=(),
        structures=(),
        artifacts=(),
    )


def _hypothesis(
    *,
    operand_a: str = "item-a",
    operand_b: str | None = "item-b",
    conditions: tuple[HypothesisCondition, ...] = (),
) -> ExperimentHypothesis:
    operator = ExperimentOperator.COMBINE
    process = ExperimentProcessToken.NONE
    return ExperimentHypothesis(
        owner_id=OWNER,
        hypothesis_id=experiment_hypothesis_id(
            OWNER, operator, operand_a, operand_b, process
        ),
        operator=operator,
        operand_a_id=operand_a,
        operand_b_id=operand_b,
        process_token=process,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        conditions=conditions,
        created_tick=2,
    )


def _trial(event_id: str = "event-9") -> ExperimentTrial:
    return ExperimentTrial(
        tick=3,
        event_id=event_id,
        outcome_class=ExperimentOutcomeClass.SUCCESS.value,
        discovery_mode="deliberate",
    )


def test_reference_helper_is_stable_and_namespaced() -> None:
    first = replication_ref("rtrl", "body-1", "event-1")
    again = replication_ref("rtrl", "body-1", "event-1")
    other_namespace = replication_ref("rrep", "body-1", "event-1")
    assert first == again
    assert first.startswith("rtrl-")
    assert other_namespace.startswith("rrep-")
    assert first != other_namespace
    with pytest.raises(ReplicationError):
        replication_ref("unknown", "value")


def test_freeze_uses_only_observed_owner_safe_descriptors() -> None:
    result = freeze_experiment_design(
        OWNER,
        _hypothesis(),
        _trial(),
        _observation(
            items=(("item-a", ItemKind.TOOL), ("item-b", ItemKind.MATERIAL))
        ),
    )
    assert result.reason == "frozen"
    design = result.design
    assert design is not None
    assert verify_replication_design(design)
    assert design.operand_a_selector.family is ReplicationSelectorFamily.ITEM
    assert design.operand_a_selector.kind == "tool"
    assert design.operand_a_selector.exact_entity_id == "item-a"
    assert design.operand_b_selector is not None
    assert design.operand_b_selector.exact_entity_id == "item-b"
    assert design.source_trial_token.startswith("rtrl-")
    assert design.predicted_outcome is ExperimentOutcomeClass.SUCCESS


def test_missing_consumed_operand_yields_design_unavailable() -> None:
    result = freeze_experiment_design(
        OWNER,
        _hypothesis(),
        _trial(),
        _observation(items=(("item-a", ItemKind.TOOL),)),
    )
    assert result.design is None
    assert result.reason == "design_unavailable"
    assert result.notice is ReplicationNoticeCode.DESIGN_UNAVAILABLE


def test_freeze_rejects_another_owners_hypothesis() -> None:
    with pytest.raises(ReplicationError):
        freeze_experiment_design(
            OTHER,
            _hypothesis(),
            _trial(),
            _observation(
                items=(("item-a", ItemKind.TOOL), ("item-b", ItemKind.MATERIAL))
            ),
        )


def test_conditions_are_sorted_and_part_of_the_design_token() -> None:
    location = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    weather = HypothesisCondition(HypothesisConditionSlot.WEATHER, "rain")
    observation = _observation(
        items=(("item-a", ItemKind.TOOL), ("item-b", ItemKind.MATERIAL))
    )
    first = freeze_experiment_design(
        OWNER, _hypothesis(conditions=(weather, location)), _trial(), observation
    )
    second = freeze_experiment_design(
        OWNER,
        _hypothesis(conditions=(location,)),
        _trial("event-9"),
        observation,
    )
    assert first.design is not None and second.design is not None
    assert first.design.conditions[0].slot is HypothesisConditionSlot.LOCATION
    assert first.design.design_token != second.design.design_token


def test_adapted_child_keeps_parent_identity_and_origin() -> None:
    source = freeze_experiment_design(
        OWNER,
        _hypothesis(),
        _trial(),
        _observation(items=(("item-a", ItemKind.TOOL), ("item-b", ItemKind.MATERIAL))),
    ).design
    assert source is not None
    adapted = build_experiment_design(
        origin_token=source.origin_token,
        parent_design_token=source.design_token,
        source_hypothesis_token=source.source_hypothesis_token,
        source_trial_token=source.source_trial_token,
        created_tick=5,
        operator=source.operator,
        process_token=source.process_token,
        operand_a_selector=dataclasses.replace(
            source.operand_a_selector,
            kind="material",
            exact_entity_id="item-c",
        ),
        operand_b_selector=source.operand_b_selector,
        predicted_outcome=source.predicted_outcome,
        conditions=source.conditions,
    )
    assert adapted.parent_design_token == source.design_token
    assert adapted.origin_token == source.origin_token
    assert adapted.design_token != source.design_token


def test_adoption_retains_transmitted_tokens_and_adds_a_local_receipt() -> None:
    source = freeze_experiment_design(
        OWNER,
        _hypothesis(),
        _trial(),
        _observation(items=(("item-a", ItemKind.TOOL), ("item-b", ItemKind.MATERIAL))),
    ).design
    assert source is not None
    receiver = empty_replication_ledger(OTHER)
    adopted, reason = adopt_replication_design(
        OTHER,
        receiver,
        source,
        delivery_event_id="delivery-1",
        received_tick=8,
        inviter_entity_id="body-owner",
    )
    assert reason == "design_adopted"
    assert adopted.designs == (source,)
    assert adopted.designs[0].origin_token == source.origin_token
    assert adopted.designs[0].design_token == source.design_token
    assert adopted.receipts[0].owner_id == OTHER
    assert adopted.receipts[0].design_token == source.design_token
    assert adopted.receipts[0].inviter_entity_id == "body-owner"

    again, reason = adopt_replication_design(
        OTHER,
        adopted,
        source,
        delivery_event_id="delivery-1",
        received_tick=8,
    )
    assert reason == "duplicate_delivery"
    assert again == adopted


def test_tampered_design_content_is_rejected_before_adoption() -> None:
    source = freeze_experiment_design(
        OWNER,
        _hypothesis(),
        _trial(),
        _observation(items=(("item-a", ItemKind.TOOL), ("item-b", ItemKind.MATERIAL))),
    ).design
    assert source is not None
    tampered = dataclasses.replace(
        source,
        operand_a_selector=dataclasses.replace(
            source.operand_a_selector, exact_entity_id="item-z"
        ),
    )
    assert design_token_for(tampered) != tampered.design_token
    ledger, reason = adopt_replication_design(
        OTHER,
        empty_replication_ledger(OTHER),
        tampered,
        delivery_event_id="delivery-2",
        received_tick=9,
    )
    assert reason == "design_identity_mismatch"
    assert ledger.designs == ()


def test_adoption_rejects_a_foreign_ledger() -> None:
    source = freeze_experiment_design(
        OWNER,
        _hypothesis(),
        _trial(),
        _observation(items=(("item-a", ItemKind.TOOL), ("item-b", ItemKind.MATERIAL))),
    ).design
    assert source is not None
    with pytest.raises(ReplicationError):
        adopt_replication_design(
            OTHER,
            empty_replication_ledger(OWNER),
            source,
            delivery_event_id="delivery-3",
            received_tick=1,
        )


def _same_kind_design(
    *,
    kind: str = "tool",
    second_kind: str | None = None,
    conditions: tuple[HypothesisCondition, ...] = (),
) -> ExperimentDesign:
    return build_experiment_design(
        origin_token=replication_ref("rorg", OWNER.value, "same-kind"),
        parent_design_token=None,
        source_hypothesis_token=replication_ref("rhyp", OWNER.value, "hyp-1"),
        source_trial_token=replication_ref("rtrl", "body-source", "event-1"),
        created_tick=4,
        operator=ExperimentOperator.APPLY_TOOL,
        process_token=ExperimentProcessToken.CRAFT,
        operand_a_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind=kind,
            binding_mode=ReplicationBindingMode.SAME_KIND,
        ),
        operand_b_selector=(
            None
            if second_kind is None
            else ExperimentSelector(
                family=ReplicationSelectorFamily.ITEM,
                kind=second_kind,
                binding_mode=ReplicationBindingMode.SAME_KIND,
            )
        ),
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=conditions,
    )


def _exact_selector(entity_id: str) -> ExperimentSelector:
    return ExperimentSelector(
        family=ReplicationSelectorFamily.ITEM,
        kind="tool",
        binding_mode=ReplicationBindingMode.EXACT,
        exact_entity_id=entity_id,
    )


def test_receiver_binds_equivalent_own_material_not_the_source_tool() -> None:
    source_tool = _exact_selector("item-a")
    exact_design = build_experiment_design(
        origin_token=replication_ref("rorg", OWNER.value, "exact"),
        parent_design_token=None,
        source_hypothesis_token=replication_ref("rhyp", OWNER.value, "hyp-1"),
        source_trial_token=replication_ref("rtrl", "body-source", "event-1"),
        created_tick=4,
        operator=ExperimentOperator.APPLY_TOOL,
        process_token=ExperimentProcessToken.CRAFT,
        operand_a_selector=source_tool,
        operand_b_selector=None,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(),
    )
    receiver_observation = _observation(items=(("item-b", ItemKind.TOOL),))
    missing = bind_replication_design(exact_design, receiver_observation)
    assert missing.binding is None
    assert missing.reason == "selector_unavailable"
    assert missing.notice is ReplicationNoticeCode.SELECTOR_UNAVAILABLE

    adapted = adapt_replication_design(
        exact_design,
        operand_a_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="tool",
            binding_mode=ReplicationBindingMode.SAME_KIND,
        ),
        operand_b_selector=None,
        conditions=(),
        created_tick=5,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
    )
    result = bind_replication_design(adapted, receiver_observation)
    assert result.reason == "bound"
    assert result.binding is not None
    assert result.binding.operand_a_id == "item-b"
    assert result.binding.operand_a_id != "item-a"


def test_consumed_exact_resource_is_unavailable() -> None:
    design = build_experiment_design(
        origin_token=replication_ref("rorg", OWNER.value, "resource"),
        parent_design_token=None,
        source_hypothesis_token=replication_ref("rhyp", OWNER.value, "hyp-1"),
        source_trial_token=replication_ref("rtrl", "body-source", "event-1"),
        created_tick=4,
        operator=ExperimentOperator.COMBINE,
        process_token=ExperimentProcessToken.NONE,
        operand_a_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.RESOURCE,
            kind="food",
            binding_mode=ReplicationBindingMode.EXACT,
            exact_entity_id="resource-1",
        ),
        operand_b_selector=None,
        predicted_outcome=None,
        conditions=(),
    )
    observation = SimpleNamespace(
        observer_id=EntityId("body-owner"),
        tick=3,
        items=(),
        resources=(
            SimpleNamespace(
                entity_id=EntityId("resource-1"),
                kind=SimpleNamespace(value="food"),
                quantity=0.0,
            ),
        ),
        structures=(),
        artifacts=(),
    )
    result = bind_replication_design(design, observation)
    assert result.binding is None
    assert result.reason == "selector_unavailable"


def test_same_kind_tie_breaks_on_stable_entity_id_and_two_operands_differ() -> None:
    design = _same_kind_design(kind="tool")
    two_tools = _observation(
        items=(("item-c", ItemKind.TOOL), ("item-b", ItemKind.TOOL))
    )
    result = bind_replication_design(design, two_tools)
    assert result.binding is not None
    assert result.binding.operand_a_id == "item-b"

    two_operand_design = _same_kind_design(kind="tool", second_kind="tool")
    one_tool = _observation(items=(("item-b", ItemKind.TOOL),))
    result = bind_replication_design(two_operand_design, one_tool)
    assert result.binding is None
    assert result.reason == "duplicate_operand"

    result = bind_replication_design(two_operand_design, two_tools)
    assert result.binding is not None
    assert result.binding.operand_a_id != result.binding.operand_b_id


def test_missing_declared_condition_prevents_binding() -> None:
    rain = HypothesisCondition(HypothesisConditionSlot.WEATHER, "rain")
    design = _same_kind_design(conditions=(rain,))
    result = bind_replication_design(
        design, _observation(items=(("item-b", ItemKind.TOOL),))
    )
    assert result.binding is None
    assert result.reason == "condition_unsatisfied"
    assert result.notice is ReplicationNoticeCode.CONDITION_UNKNOWN


def test_condition_comparison_reports_slot_names_only() -> None:
    location = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    other = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-2")
    matched = compare_replication_conditions((location,), (location,))
    assert matched.comparison is ReplicationConditionComparison.MATCHED
    assert matched.slots == ()
    different = compare_replication_conditions((location,), (other,))
    assert different.comparison is ReplicationConditionComparison.DIFFERENT
    assert different.slots == ("location",)
    unknown = compare_replication_conditions((location,), ())
    assert unknown.comparison is ReplicationConditionComparison.UNKNOWN
    assert unknown.slots == ("location",)


def test_adapted_child_requires_an_actual_change() -> None:
    parent = _same_kind_design()
    with pytest.raises(ReplicationError):
        adapt_replication_design(
            parent,
            operand_a_selector=parent.operand_a_selector,
            operand_b_selector=parent.operand_b_selector,
            conditions=parent.conditions,
            created_tick=5,
            predicted_outcome=parent.predicted_outcome,
        )
    child = adapt_replication_design(
        parent,
        operand_a_selector=dataclasses.replace(
            parent.operand_a_selector, kind="material"
        ),
        operand_b_selector=parent.operand_b_selector,
        conditions=parent.conditions,
        created_tick=5,
        predicted_outcome=parent.predicted_outcome,
    )
    assert child.parent_design_token == parent.design_token
    assert child.origin_token == parent.origin_token
    assert child.design_token != parent.design_token
    assert verify_replication_design(child)
