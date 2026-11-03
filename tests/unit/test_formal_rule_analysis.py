"""V4-06 detached formal-rule rows, windows, detection, identity, and lineage."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from agents.cognition import (
    FormalRuleConstraintKind,
    FormalRuleStage,
    FormalRuleStatus,
)
from analysis.formal_rule_contract import (
    FormalRuleAnalysisError,
    FormalRuleCoverage,
    FormalRuleLineageKind,
)
from analysis.formal_rule_detection import detect_formal_rule_candidates
from analysis.formal_rule_evidence import (
    FormalRuleWindowEvidence,
    build_formal_rule_windows,
)
from analysis.formal_rule_identity import assign_formal_rule_identities
from analysis.formal_rule_lineage import (
    derive_formal_rule_lineage,
    summarize_formal_rules,
    validate_formal_rule_lineage,
)
from analysis.formal_rules import harvest_formal_rule_rows
from tests.unit.formal_rule_helpers import make_ledger

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src"
OWNER = "agent-1"
OTHER = "agent-2"


def _rows(*ledgers: Any) -> Any:
    return harvest_formal_rule_rows(ledgers, window_ticks=100)


def _lane(rule: Any) -> str:
    kind = getattr(rule, "scope_kind", None)
    if kind is None:
        kind = getattr(getattr(rule, "scope", None), "kind", None)
    return str(getattr(kind, "value", kind) or "")


def _window(start: int, end: int, *rules: Any) -> Any:
    return FormalRuleWindowEvidence(
        start_tick=start,
        end_tick=end,
        owner_rows=tuple(
            sorted(
                {
                    str(getattr(rule.owner_id, "value", rule.owner_id) or "")
                    for rule in rules
                }
            )
        ),
        objective_rows=(),
        rule_ids=tuple(sorted(rule.rule_id for rule in rules)),
        system_ids=tuple(sorted({rule.system_id for rule in rules})),
        lane_presence=tuple(sorted({_lane(rule) for rule in rules})),
        coverage=FormalRuleCoverage(observed=1, expected=1),
        rules=tuple(rules),
    )


def test_harvest_is_sorted_unique_and_owner_scoped() -> None:
    rows = _rows(
        make_ledger(owner=OTHER, action="attack"),
        make_ledger(owner=OWNER),
    )
    assert [row.owner_id for row in rows.owners] == [OWNER, OTHER]
    assert list(rows.rules) == sorted(rows.rules, key=lambda row: row.rule_id)
    assert all(row.owner_id in {OWNER, OTHER} for row in rows.rules)


def test_harvest_rejects_non_ledgers_and_duplicate_owners() -> None:
    with pytest.raises(FormalRuleAnalysisError) as excinfo:
        harvest_formal_rule_rows([object()], window_ticks=100)
    assert excinfo.value.code == "formal_rule_harvest_invalid"

    with pytest.raises(FormalRuleAnalysisError) as excinfo:
        harvest_formal_rule_rows(
            [make_ledger(owner=OWNER), make_ledger(owner=OWNER)],
            window_ticks=100,
        )
    assert excinfo.value.code == "formal_rule_harvest_invalid"


def test_windows_do_not_fabricate_missing_ticks() -> None:
    rows = _rows(make_ledger(ticks=(0, 250)))
    windows = build_formal_rule_windows(rows, window_ticks=100)
    assert len(windows) == 3
    assert windows[0].rule_ids
    assert windows[1].rule_ids == ()
    assert windows[1].coverage.partial is True
    assert windows[2].rule_ids


def test_partial_coverage_is_explicit() -> None:
    rows = _rows(make_ledger(ticks=(0, 250)))
    windows = build_formal_rule_windows(rows, window_ticks=100)
    observed = sum(1 for window in windows if not window.coverage.partial)
    assert observed == 2
    assert windows[1].coverage.coverage_fraction == 0.0
    assert FormalRuleCoverage(observed=0, expected=0).coverage_fraction is None


def test_analysis_imports_no_cognition_runtime_or_persistence() -> None:
    allowed = {
        "__future__",
        "analysis",
        "collections",
        "dataclasses",
        "enum",
        "hashlib",
        "json",
        "logging",
        "re",
        "types",
        "typing",
    }
    for path in sorted(SRC.glob("analysis/formal_rule*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        assert imported <= allowed, path
        assert not imported & {
            "agents",
            "api",
            "experiments",
            "infrastructure",
            "observer",
            "persistence",
            "simulation",
            "world",
        }, path


def test_opposite_constraints_remain_separate_candidates() -> None:
    rows = _rows(
        make_ledger(
            owner=OWNER,
            constraint=FormalRuleConstraintKind.PROHIBITION,
        ),
        make_ledger(
            owner=OTHER,
            constraint=FormalRuleConstraintKind.OBLIGATION,
        ),
    )
    windows = build_formal_rule_windows(rows, window_ticks=100)
    candidates = detect_formal_rule_candidates(rows, windows)
    assert len({candidate.candidate_key for candidate in candidates}) == 2
    assert len(candidates) == 2


def test_competing_candidates_may_share_anchors() -> None:
    rows = _rows(
        make_ledger(
            owner=OWNER,
            constraint=FormalRuleConstraintKind.PROHIBITION,
        ),
        make_ledger(
            owner=OTHER,
            constraint=FormalRuleConstraintKind.OBLIGATION,
        ),
    )
    windows = build_formal_rule_windows(rows, window_ticks=100)
    candidates = detect_formal_rule_candidates(rows, windows)
    assert {candidate.scope_digest for candidate in candidates} == {
        candidates[0].scope_digest
    }
    assert {candidate.action_token for candidate in candidates} == {"maintain"}
    assert len({candidate.candidate_key for candidate in candidates}) == 2


def test_identity_is_stable_on_continuation() -> None:
    ledger = make_ledger(ticks=(0, 100))
    windows = build_formal_rule_windows(_rows(ledger), window_ticks=100)
    assignment = assign_formal_rule_identities(windows)
    assert len(assignment.records) == 1
    assert assignment.windows[0].record_ids == assignment.windows[1].record_ids


def test_split_and_merge_mint_forward_only_ids() -> None:
    first = _rows(make_ledger(owner=OWNER, ticks=(0,))).rules[0]
    second = _rows(make_ledger(owner=OTHER, ticks=(0,))).rules[0]
    split_prior = _window(0, 99, first, second)
    left = _rows(
        make_ledger(
            owner=OWNER,
            ticks=(100,),
            constraint=FormalRuleConstraintKind.PROHIBITION,
        )
    ).rules[0]
    right = _rows(
        make_ledger(
            owner=OTHER,
            ticks=(100,),
            constraint=FormalRuleConstraintKind.OBLIGATION,
        )
    ).rules[0]
    split_next = _window(100, 199, left, right)
    split = assign_formal_rule_identities((split_prior, split_next))
    assert any(
        transition.kind is FormalRuleLineageKind.SPLIT
        for transition in split.transitions
    )

    merged_left = _rows(
        make_ledger(owner=OWNER, ticks=(100,))
    ).rules[0]
    merged_right = _rows(
        make_ledger(owner=OTHER, ticks=(100,))
    ).rules[0]
    merge_next = _window(100, 199, merged_left, merged_right)
    merge = assign_formal_rule_identities(
        (
            FormalRuleWindowEvidence(
                start_tick=0,
                end_tick=99,
                owner_rows=(OWNER, OTHER),
                objective_rows=(),
                rule_ids=tuple(sorted((left.rule_id, right.rule_id))),
                system_ids=tuple(sorted((left.system_id, right.system_id))),
                lane_presence=("unspecified",),
                coverage=FormalRuleCoverage(observed=1, expected=1),
                rules=(left, right),
            ),
            merge_next,
        )
    )
    assert any(
        transition.kind is FormalRuleLineageKind.MERGE
        for transition in merge.transitions
    )
    for assignment in (split, merge):
        for transition in assignment.transitions:
            assert transition.tick >= 0
            if transition.source_candidate_id is not None:
                assert transition.target_candidate_id.startswith("frule-")


def test_lineage_is_acyclic_and_forward_only() -> None:
    rows = _rows(make_ledger(ticks=(0, 100, 200)))
    windows = build_formal_rule_windows(rows, window_ticks=100)
    analysis = derive_formal_rule_lineage(rows, windows)
    validate_formal_rule_lineage(analysis)
    for edge in analysis.edges:
        assert edge.tick >= 0
        assert edge.source_candidate_id.startswith("frule-")
        assert edge.target_candidate_id.startswith("frule-")


def test_formal_rule_lineage_never_references_organization_candidates() -> None:
    rows = _rows(make_ledger(ticks=(0, 100)))
    windows = build_formal_rule_windows(rows, window_ticks=100)
    analysis = derive_formal_rule_lineage(rows, windows)
    for record in analysis.records:
        assert record.candidate_id.startswith("frule-")
        assert not record.candidate_id.startswith(("org-", "msoc-"))
    for edge in analysis.edges:
        assert not edge.edge_id.startswith(("org-", "msoc-"))


def test_summary_is_deterministic_under_row_permutation() -> None:
    left = make_ledger(owner=OWNER, ticks=(0,))
    right = make_ledger(
        owner=OTHER,
        ticks=(0,),
        constraint=FormalRuleConstraintKind.PROHIBITION,
    )
    first_rows = _rows(left, right)
    second_rows = _rows(right, left)
    first_windows = build_formal_rule_windows(first_rows, window_ticks=100)
    second_windows = build_formal_rule_windows(second_rows, window_ticks=100)
    first = summarize_formal_rules(
        first_rows,
        derive_formal_rule_lineage(first_rows, first_windows),
    )
    second = summarize_formal_rules(
        second_rows,
        derive_formal_rule_lineage(second_rows, second_windows),
    )
    assert first.determinism_digest == second.determinism_digest
    assert first.candidates == second.candidates


def test_stage_counts_reach_documented_and_recognized() -> None:
    rows = _rows(
        make_ledger(
            ticks=(0,),
            stage=FormalRuleStage.RECOGNIZED_ENFORCEMENT,
            status=FormalRuleStatus.ACTIVE,
        )
    )
    windows = build_formal_rule_windows(rows, window_ticks=100)
    summary = summarize_formal_rules(
        rows, derive_formal_rule_lineage(rows, windows)
    )
    assert summary.development[0].recognized_enforcement_count == 1
