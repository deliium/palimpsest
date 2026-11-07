# mypy: ignore-errors
"""Four-layer projection and hard leakage guard."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from analysis.borders_contract import (
    BorderAccessRow,
    BorderAgreementRow,
    BorderClaimRow,
    BorderDisputeRow,
    BorderPatternRow,
    BorderRecognitionRow,
)
from analysis.borders_events import BorderPhysicalRow
from analysis.borders_layers import (
    BorderLayerView,
    assert_border_layer_separation,
    layer_counts,
    project_border_layers,
)
from analysis.borders_rows import BorderHarvestRows


def _rows() -> BorderHarvestRows:
    return BorderHarvestRows(
        physical=(BorderPhysicalRow("bloc-a", 0, 5, 1, 2, 0, 0, 2, "repeated_use"),),
        claims=(
            BorderClaimRow(
                "bown-1",
                "bdc-1",
                ("bloc-a",),
                (),
                "claimed",
                0.8,
            ),
        ),
        recognitions=(
            BorderRecognitionRow("bdr-1", "bdc-1", (), "own_claim", "unresolved"),
        ),
        access_expectations=(
            BorderAccessRow("bdx-1", "bdc-1", "bsub-1", "open", "expected"),
        ),
        agreements=(
            BorderAgreementRow(
                "bda-1", "bdc-1", "bcp-1", ("passage",), "proposed", "unresolved"
            ),
        ),
        disputes=(BorderDisputeRow("bdd-1", "bdc-1", "bcp-1", ("bloc-a",), "active"),),
        coverage="complete",
    )


def _pattern() -> BorderPatternRow:
    return BorderPatternRow("bpat-1", "bdc-1", ("bloc-a",), "claim_aligned", 2, 1, 0, 0)


def test_four_layer_types_are_distinct() -> None:
    view = project_border_layers(_rows(), (_pattern(),))
    assert type(view.physical[0]) is BorderPhysicalRow
    assert type(view.claims[0]) is BorderClaimRow
    assert type(view.agreements[0]) is BorderAgreementRow
    assert type(view.patterns[0]) is BorderPatternRow
    assert len(layer_counts(view)) == 4


@dataclasses.dataclass(frozen=True)
class _LeakyPhysical:
    owner_token: str


@dataclasses.dataclass(frozen=True)
class _LeakyClaim:
    actor_count: int


@dataclasses.dataclass(frozen=True)
class _LeakyAgreement:
    pattern: str


@dataclasses.dataclass(frozen=True)
class _ForbiddenRow:
    winner: str


def test_physical_rows_reject_claim_fields() -> None:
    view = BorderLayerView(physical=(_LeakyPhysical("x"),))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        assert_border_layer_separation(view)


def test_claim_rows_reject_physical_counts() -> None:
    view = BorderLayerView(claims=(_LeakyClaim(1),))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        assert_border_layer_separation(view)


def test_agreement_rows_reject_pattern_fields() -> None:
    view = BorderLayerView(agreements=(_LeakyAgreement("x"),))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        assert_border_layer_separation(view)


def test_pattern_rows_reject_raw_ids_and_forbidden_results() -> None:
    view = BorderLayerView(patterns=(_ForbiddenRow("x"),))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        assert_border_layer_separation(view)


def test_rows_are_sorted_and_deterministic() -> None:
    first = project_border_layers(_rows(), (_pattern(),))
    second = project_border_layers(_rows(), (_pattern(),))
    assert first == second
    assert first.claims == tuple(
        sorted(first.claims, key=lambda item: (item.domain_token, item.owner_token))
    )


def test_empty_layers_are_legal() -> None:
    view = project_border_layers(BorderHarvestRows(), ())
    assert view.physical == ()
    assert view.claims == ()


def test_analysis_modules_do_not_import_cognition_or_adapters() -> None:
    root = Path("src/analysis")
    forbidden = (
        "agents.cognition",
        "experiments",
        "api",
        "persistence",
        "observer",
    )
    for path in sorted(root.glob("borders_*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                for prefix in forbidden:
                    assert not name.startswith(prefix), (path, name)
