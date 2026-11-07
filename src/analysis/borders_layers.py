# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Four-layer projection and hard leakage guard for border analysis."""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.borders_contract import (
    BORDER_FORBIDDEN_RESULT_FIELDS,
    BORDER_LAYERS,
    BorderAccessRow,
    BorderAgreementRow,
    BorderClaimRow,
    BorderDisputeRow,
    BorderPatternRow,
    BorderRecognitionRow,
)
from analysis.borders_events import BorderPhysicalRow
from analysis.borders_rows import BorderHarvestRows

_LOG: Final[logging.Logger] = logging.getLogger("analysis.borders.layers")

_LAYER_FIELDS: Final[dict[str, frozenset[str]]] = {
    "physical": frozenset(
        {
            "owner_token",
            "domain_token",
            "counterparty_token",
            "agreement_token",
            "pattern",
        }
    ),
    "claim": frozenset(
        {"actor_count", "action_count", "hostile_count", "classification"}
    ),
    "agreement": frozenset(
        {
            "actor_count",
            "action_count",
            "hostile_count",
            "classification",
            "pattern",
        }
    ),
    "pattern": frozenset(
        {"raw_owner_id", "raw_entity_id", "evidence_body", "frame_body"}
    ),
}


@dataclass(frozen=True, slots=True)
class BorderLayerView:
    physical: tuple[BorderPhysicalRow, ...] = ()
    claims: tuple[BorderClaimRow, ...] = ()
    recognitions: tuple[BorderRecognitionRow, ...] = ()
    access_expectations: tuple[BorderAccessRow, ...] = ()
    disputes: tuple[BorderDisputeRow, ...] = ()
    agreements: tuple[BorderAgreementRow, ...] = ()
    patterns: tuple[BorderPatternRow, ...] = ()


def project_border_layers(
    rows: BorderHarvestRows,
    patterns: Sequence[BorderPatternRow],
) -> BorderLayerView:
    """Project harvest rows into the four semantic layers."""
    if type(rows) is not BorderHarvestRows:
        raise TypeError("rows must be BorderHarvestRows")
    physical = tuple(
        sorted(rows.physical, key=lambda item: (item.location_token, item.window_start))
    )
    claims = tuple(
        sorted(rows.claims, key=lambda item: (item.domain_token, item.owner_token))
    )
    recognitions = tuple(
        sorted(rows.recognitions, key=lambda item: (item.domain_token, item.basis))
    )
    access = tuple(
        sorted(
            rows.access_expectations,
            key=lambda item: (item.domain_token, item.subject_token, item.mode),
        )
    )
    disputes = tuple(
        sorted(rows.disputes, key=lambda item: (item.domain_token, item.dispute_token))
    )
    agreements = tuple(
        sorted(
            rows.agreements,
            key=lambda item: (item.domain_token, item.agreement_token),
        )
    )
    projected_patterns = tuple(
        sorted(patterns, key=lambda item: (item.domain_token, item.pattern_token))
    )
    view = BorderLayerView(
        physical=physical,
        claims=claims,
        recognitions=recognitions,
        access_expectations=access,
        disputes=disputes,
        agreements=agreements,
        patterns=projected_patterns,
    )
    assert_border_layer_separation(view)
    return view


def _field_names(row: object) -> set[str]:
    if not dataclasses.is_dataclass(row):
        return set()
    return {item.name for item in dataclasses.fields(row)}


def _check(layer: str, row: object, forbidden: frozenset[str]) -> None:
    present = _field_names(row)
    leaked = present & forbidden
    if leaked:
        field = sorted(leaked)[0]
        _LOG.error("borders_layer_leak layer=%s field=%s", layer, field)
        raise ValueError(f"border_layer_leak:{layer}:{field}")
    leaked_result = present & BORDER_FORBIDDEN_RESULT_FIELDS
    if leaked_result:
        field = sorted(leaked_result)[0]
        _LOG.error("borders_layer_leak layer=%s field=%s", layer, field)
        raise ValueError(f"border_layer_leak:{layer}:{field}")


def assert_border_layer_separation(view: BorderLayerView) -> None:
    """Fail hard when one semantic layer leaks into another."""
    if type(view) is not BorderLayerView:
        raise TypeError("view must be BorderLayerView")
    for row in view.physical:
        _check("physical", row, _LAYER_FIELDS["physical"])
    for row in (
        *view.claims,
        *view.recognitions,
        *view.access_expectations,
        *view.disputes,
    ):
        _check("claim", row, _LAYER_FIELDS["claim"])
    for row in view.agreements:
        _check("agreement", row, _LAYER_FIELDS["agreement"])
    for row in view.patterns:
        _check("pattern", row, _LAYER_FIELDS["pattern"])
    if (
        not view.physical
        and not view.claims
        and not view.agreements
        and not view.patterns
    ):
        return


def layer_counts(view: BorderLayerView) -> tuple[tuple[str, int], ...]:
    if type(view) is not BorderLayerView:
        raise TypeError("view must be BorderLayerView")
    return (
        (BORDER_LAYERS and "physical", len(view.physical)),
        (
            "subjective_claim",
            len(view.claims)
            + len(view.recognitions)
            + len(view.access_expectations)
            + len(view.disputes),
        ),
        ("agreement", len(view.agreements)),
        ("analytical_pattern", len(view.patterns)),
    )


__all__ = [
    "BorderLayerView",
    "assert_border_layer_separation",
    "layer_counts",
    "project_border_layers",
]
