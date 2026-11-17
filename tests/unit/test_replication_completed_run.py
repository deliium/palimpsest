# mypy: ignore-errors
"""V4-28 completed-run bridge normalizes once and tokenizes references."""

from __future__ import annotations

import pytest

from agents.cognition import (
    ExperimentSelector,
    ReplicationBindingMode,
    ReplicationSelectorFamily,
    append_replication_design,
    build_experiment_design,
    empty_replication_ledger,
    replication_ref,
)
from agents.models import AgentId
from experiments.replication_completed_run import (
    build_completed_run_replication_analysis,
    replication_facts,
)
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

pytestmark = pytest.mark.unit


def test_bridge_tokenizes_designs_and_keeps_raw_ids_out_of_rows() -> None:
    owner = AgentId("raw-owner-id")
    design = build_experiment_design(
        origin_token=replication_ref("rorg", owner.value, "trial"),
        parent_design_token=None,
        source_hypothesis_token=replication_ref("rhyp", owner.value, "hyp"),
        source_trial_token=replication_ref("rtrl", "raw-body", "event"),
        created_tick=1,
        operator=ExperimentOperator.APPLY_TOOL,
        process_token=ExperimentProcessToken.CRAFT,
        operand_a_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="tool",
            binding_mode=ReplicationBindingMode.SAME_KIND,
        ),
        operand_b_selector=None,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(),
    )
    ledger, _ = append_replication_design(empty_replication_ledger(owner), design)
    facts = replication_facts(
        run_id="run-1",
        replication_ledgers=(ledger,),
        registered_agent_ids=(owner.value, "other-owner"),
        expected_participants=3,
    )
    assert len(facts.designs) == 1
    row = facts.designs[0]
    assert row.design_token.startswith("rpd-")
    assert row.source_trial_token.startswith("rpt-")
    assert row.origin_token.startswith("rpo-")
    assert "raw-owner-id" not in row.design_token
    assert "partial_owner_export" in facts.notices
    analysis = build_completed_run_replication_analysis(
        run_id="run-1",
        replication_ledgers=(ledger,),
        registered_agent_ids=(owner.value, "other-owner"),
        expected_participants=3,
    )
    assert analysis.policy_version == "scientific-replication.v1"
    assert analysis.comparisons == ()
    assert analysis.coverage[0].coverage == "missing"
