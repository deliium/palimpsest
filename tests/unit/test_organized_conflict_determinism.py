# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from agents.cognition.organized_conflict import (
    ConflictLedger,
    ConflictOperation,
    ConflictPlan,
    ConflictPlanStatus,
    ConflictRole,
    ConflictTargetKind,
    conflict_plan_id,
    organized_conflict_ledger_digest,
)
from agents.models import AgentId
from analysis.organized_conflict_detection import detect_organized_conflict_episodes
from analysis.organized_conflict_events import ConflictEventRow
from analysis.organized_conflict_identity import (
    assign_organized_conflict_identities,
    derive_organized_conflict_lineage,
)
from analysis.organized_conflict_metrics import compute_organized_conflict_participation
from analysis.organized_conflict_policy import (
    default_organized_conflict_analysis_policy,
)
from analysis.organized_conflict_rows import OrganizedConflictHarvestRows
from simulation.organized_conflict_codec import finalize_organized_conflict_snapshot
from simulation.organized_conflict_models import (
    OrganizedConflictSnapshot,
    OrganizedConflictSummaryRow,
)

OWNER = AgentId("agent-deterministic")
POLICY = default_organized_conflict_analysis_policy()


def _rows() -> tuple[ConflictEventRow, ...]:
    return tuple(
        ConflictEventRow(
            tick=tick,
            sequence=index,
            event_class="attack",
            actor_token=("a" if tick % 2 else "b") * 16,
            other_token=("b" if tick % 2 else "a") * 16,
            success=True,
            magnitude=10,
        )
        for index, tick in enumerate((1, 2, 7, 8, 13, 14))
    )


def _ledger() -> ConflictLedger:
    plan = ConflictPlan(
        plan_id=conflict_plan_id(
            OWNER,
            ConflictOperation.COORDINATED_ATTACK,
            ConflictTargetKind.AGENT,
            "b" * 16,
            1,
            ("a" * 16,),
        ),
        operation=ConflictOperation.COORDINATED_ATTACK,
        target_kind=ConflictTargetKind.AGENT,
        target_ref="b" * 16,
        role=ConflictRole.ATTACKER,
        side_ref="a" * 16,
        participant_refs=("a" * 16,),
        start_tick=1,
        status=ConflictPlanStatus.ACTIVE,
        last_tick=1,
    )
    return ConflictLedger(owner_id=OWNER, tick=1, plans=(plan,))


def test_repeated_runs_produce_identical_ids_digests_and_values() -> None:
    first_candidates = assign_organized_conflict_identities(
        detect_organized_conflict_episodes(_rows(), policy=POLICY)
    )
    second_candidates = assign_organized_conflict_identities(
        detect_organized_conflict_episodes(_rows(), policy=POLICY)
    )
    assert first_candidates == second_candidates
    assert derive_organized_conflict_lineage(
        first_candidates
    ) == derive_organized_conflict_lineage(second_candidates)
    assert organized_conflict_ledger_digest(_ledger()) == organized_conflict_ledger_digest(
        _ledger()
    )

    rows = OrganizedConflictHarvestRows(objective_events=_rows())
    first_metrics = compute_organized_conflict_participation(
        rows, first_candidates, run_id="run", input_revision="rev"
    )
    second_metrics = compute_organized_conflict_participation(
        rows, second_candidates, run_id="run", input_revision="rev"
    )
    assert first_metrics.values == second_metrics.values

    snapshot = OrganizedConflictSnapshot(
        schema_version="organized-conflict-snapshot-v1",
        policy_version="organized-conflict-snapshot.v1",
        run_id="run",
        publication_id="oc-pub-" + "0" * 16,
        digest="0" * 64,
        summary=OrganizedConflictSummaryRow(),
    )
    assert finalize_organized_conflict_snapshot(
        snapshot
    ) == finalize_organized_conflict_snapshot(snapshot)
