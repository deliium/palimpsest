"""V4-06 bounded paging and cursor-binding contracts."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import pytest

from simulation import (
    FORMAL_RULE_CURSOR_PURPOSES,
    FormalRuleArtifactError,
    FormalRuleCursor,
    FormalRuleRowSelection,
    formal_rule_cursor_matches,
    formal_rule_query_fingerprint,
    select_formal_rule_candidate_rows,
    select_formal_rule_lineage_rows,
    select_formal_rule_rows,
    select_formal_rule_version_rows,
)
from tests.unit.test_formal_rule_snapshot import _snapshot

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src"


def _rows() -> Any:
    snapshot = _snapshot()
    return snapshot.candidates, snapshot.rules, snapshot.versions, snapshot.lineage


def test_selection_is_whole_row_and_bounded() -> None:
    candidates, _, _, _ = _rows()
    selection = select_formal_rule_candidate_rows(
        candidates, offset=0, limit=1, byte_budget=2 * 1024 * 1024
    )
    assert type(selection) is FormalRuleRowSelection
    assert len(selection.rows) == 1
    assert selection.next_offset == 1
    assert selection.truncated is True


def test_offset_limit_and_byte_budget_errors() -> None:
    candidates, _, _, _ = _rows()
    with pytest.raises(FormalRuleArtifactError) as excinfo:
        select_formal_rule_candidate_rows(
            candidates, offset=-1, limit=1, byte_budget=1024
        )
    assert excinfo.value.code == "formal_rule_page_offset"

    with pytest.raises(FormalRuleArtifactError) as excinfo:
        select_formal_rule_candidate_rows(
            candidates, offset=0, limit=-1, byte_budget=1024
        )
    assert excinfo.value.code == "formal_rule_page_limit"

    with pytest.raises(FormalRuleArtifactError) as excinfo:
        select_formal_rule_candidate_rows(
            candidates, offset=0, limit=10, byte_budget=1
        )
    assert excinfo.value.code == "formal_rule_size_limit"


def test_candidate_rules_versions_and_lineage_filters() -> None:
    candidates, rules, versions, lineage = _rows()
    candidate = cast(Any, candidates[0])
    selected_rules = select_formal_rule_rows(
        rules,
        candidate_id=candidate.candidate_id,
        offset=0,
        limit=10,
        byte_budget=2 * 1024 * 1024,
    )
    assert all(
        cast(Any, row).candidate_id == candidate.candidate_id
        for row in selected_rules.rows
    )
    selected_versions = select_formal_rule_version_rows(
        versions,
        candidate_id=candidate.candidate_id,
        rule_id=cast(Any, selected_rules.rows[0]).rule_id,
        offset=0,
        limit=10,
        byte_budget=2 * 1024 * 1024,
    )
    assert selected_versions.rows
    selected_lineage = select_formal_rule_lineage_rows(
        lineage, offset=0, limit=10, byte_budget=2 * 1024 * 1024
    )
    assert len(selected_lineage.rows) == len(lineage)


def test_cursor_fingerprint_changes_with_any_bound_field() -> None:
    base = formal_rule_query_fingerprint(
        "rules",
        run_id="run-1",
        publication_id="frule-pub-0123456789abcdef",
        candidate_id="frule-0123456789abcdef",
        filters=(("stage", "norm"),),
    )
    for changed in (
        formal_rule_query_fingerprint(
            "rules",
            run_id="run-2",
            publication_id="frule-pub-0123456789abcdef",
            candidate_id="frule-0123456789abcdef",
            filters=(("stage", "norm"),),
        ),
        formal_rule_query_fingerprint(
            "rules",
            run_id="run-1",
            publication_id="frule-pub-fedcba9876543210",
            candidate_id="frule-0123456789abcdef",
            filters=(("stage", "norm"),),
        ),
        formal_rule_query_fingerprint(
            "rules",
            run_id="run-1",
            publication_id="frule-pub-0123456789abcdef",
            candidate_id="frule-fedcba9876543210",
            filters=(("stage", "norm"),),
        ),
        formal_rule_query_fingerprint(
            "rules",
            run_id="run-1",
            publication_id="frule-pub-0123456789abcdef",
            candidate_id="frule-0123456789abcdef",
            filters=(("stage", "documented"),),
        ),
    ):
        assert changed != base


def test_cursor_match_rejects_changed_run_publication_digest_or_filter() -> None:
    fingerprint = formal_rule_query_fingerprint(
        "candidates", run_id="run-1", publication_id="frule-pub-0123456789abcdef"
    )
    cursor = FormalRuleCursor(
        purpose="candidates",
        run_id="run-1",
        publication_id="frule-pub-0123456789abcdef",
        snapshot_digest="a" * 64,
        offset=0,
        query_fingerprint=fingerprint,
    )
    assert formal_rule_cursor_matches(
        cursor,
        purpose="candidates",
        run_id="run-1",
        publication_id="frule-pub-0123456789abcdef",
        snapshot_digest="a" * 64,
        fingerprint=fingerprint,
    )
    for kwargs in (
        {"purpose": "rules"},
        {"run_id": "run-2"},
        {"publication_id": "frule-pub-fedcba9876543210"},
        {"snapshot_digest": "b" * 64},
        {"fingerprint": "c" * 64},
    ):
        arguments = {
            "purpose": "candidates",
            "run_id": "run-1",
            "publication_id": "frule-pub-0123456789abcdef",
            "snapshot_digest": "a" * 64,
            "fingerprint": fingerprint,
            **kwargs,
        }
        assert not formal_rule_cursor_matches(cursor, **arguments)


def test_six_cursor_purposes_are_closed() -> None:
    assert FORMAL_RULE_CURSOR_PURPOSES == (
        "summary",
        "candidates",
        "candidate",
        "rules",
        "versions",
        "lineage",
    )
    with pytest.raises(FormalRuleArtifactError):
        FormalRuleCursor(
            purpose="extra",
            run_id="run-1",
            publication_id="frule-pub-0123456789abcdef",
            snapshot_digest="a" * 64,
            offset=0,
            query_fingerprint="b" * 64,
        )


def test_no_analysis_or_api_import() -> None:
    for path in sorted(SRC.glob("simulation/formal_rule_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        assert not imported & {
            "analysis",
            "api",
            "experiments",
            "infrastructure",
            "persistence",
        }, path
