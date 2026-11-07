# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Detached owner-row harvest for border analysis.

Inputs are metadata-only exported rows plus committed events. Analysis never
imports cognition, experiments, API, persistence, or observer modules.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.borders_contract import (
    BorderAccessRow,
    BorderAgreementRow,
    BorderClaimRow,
    BorderDisputeRow,
    BorderRecognitionRow,
)
from analysis.borders_events import (
    BorderPhysicalRow,
    harvest_physical_rows_with_coverage,
)
from analysis.borders_policy import BordersAnalysisPolicy

_LOG: Final[logging.Logger] = logging.getLogger("analysis.borders.rows")

_ROW_KINDS: Final[frozenset[str]] = frozenset(
    {"claim", "recognition", "access", "agreement", "dispute"}
)


@dataclass(frozen=True, slots=True)
class BorderHarvestRows:
    physical: tuple[BorderPhysicalRow, ...] = ()
    claims: tuple[BorderClaimRow, ...] = ()
    recognitions: tuple[BorderRecognitionRow, ...] = ()
    access_expectations: tuple[BorderAccessRow, ...] = ()
    agreements: tuple[BorderAgreementRow, ...] = ()
    disputes: tuple[BorderDisputeRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: str = "not_applicable"

    def __post_init__(self) -> None:
        if self.coverage not in {"complete", "partial", "not_applicable", "observed"}:
            raise ValueError("coverage: unknown_coverage")


def _row_value(row: object, name: str, default: object = None) -> object:
    return getattr(row, name, default)


def _as_tuple(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, set, frozenset, Mapping)):
        return ()
    if not isinstance(value, Sequence):
        return ()
    return tuple(value)


def _as_tokens(value: object) -> tuple[str, ...]:
    return tuple(str(item) for item in _as_tuple(value) if type(item) is str)


def _as_edges(value: object) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for item in _as_tuple(value):
        if type(item) is tuple and len(item) == 2:
            left, right = item
            if type(left) is str and type(right) is str:
                pairs.append((left, right))
    return tuple(pairs)


def _project_group(
    group: object,
) -> tuple[
    list[BorderClaimRow],
    list[BorderRecognitionRow],
    list[BorderAccessRow],
    list[BorderAgreementRow],
    list[BorderDisputeRow],
]:
    claims: list[BorderClaimRow] = []
    recognitions: list[BorderRecognitionRow] = []
    access: list[BorderAccessRow] = []
    agreements: list[BorderAgreementRow] = []
    disputes: list[BorderDisputeRow] = []
    for row in _as_tuple(group):
        kind = _row_value(row, "row_kind")
        if type(kind) is not str or kind not in _ROW_KINDS:
            raise TypeError("exported row has an unsupported row_kind")
        if kind == "claim":
            claims.append(
                BorderClaimRow(
                    owner_token=str(_row_value(row, "owner_token", "")),
                    domain_token=str(_row_value(row, "domain_token", "")),
                    location_tokens=_as_tokens(_row_value(row, "location_tokens")),
                    boundary_edge_tokens=_as_edges(_row_value(row, "edge_tokens")),
                    status=str(_row_value(row, "status", "")),
                    strength=float(_row_value(row, "strength", 0.0) or 0.0),
                    anchor_token=str(_row_value(row, "anchor_token", "")),
                )
            )
        elif kind == "recognition":
            recognitions.append(
                BorderRecognitionRow(
                    recognition_token=str(_row_value(row, "row_id", "")),
                    domain_token=str(_row_value(row, "domain_token", "")),
                    edge_tokens=_as_edges(_row_value(row, "edge_tokens")),
                    basis=str(_row_value(row, "basis", "")),
                    status=str(_row_value(row, "status", "")),
                )
            )
        elif kind == "access":
            access.append(
                BorderAccessRow(
                    access_token=str(_row_value(row, "row_id", "")),
                    domain_token=str(_row_value(row, "domain_token", "")),
                    subject_token=str(_row_value(row, "subject_token", "")),
                    mode=str(_row_value(row, "mode", "")),
                    status=str(_row_value(row, "status", "")),
                )
            )
        elif kind == "agreement":
            effective = _row_value(row, "effective_tick")
            expiry = _row_value(row, "expiry_tick")
            agreements.append(
                BorderAgreementRow(
                    agreement_token=str(_row_value(row, "row_id", "")),
                    domain_token=str(_row_value(row, "domain_token", "")),
                    counterparty_token=str(_row_value(row, "counterparty_token", "")),
                    provision_tokens=_as_tokens(_row_value(row, "provision_tokens")),
                    status=str(_row_value(row, "status", "")),
                    recognition=str(_row_value(row, "recognition", "")),
                    effective_tick=(None if effective is None else int(effective)),
                    expiry_tick=None if expiry is None else int(expiry),
                )
            )
        else:
            disputes.append(
                BorderDisputeRow(
                    dispute_token=str(_row_value(row, "row_id", "")),
                    domain_token=str(_row_value(row, "domain_token", "")),
                    counterparty_token=str(_row_value(row, "counterparty_token", "")),
                    contested_location_tokens=_as_tokens(
                        _row_value(row, "location_tokens")
                    ),
                    status=str(_row_value(row, "status", "")),
                )
            )
    return claims, recognitions, access, agreements, disputes


def harvest_border_rows(
    exported_ledgers: Sequence[object],
    committed_events: Sequence[object],
    *,
    policy: BordersAnalysisPolicy,
) -> BorderHarvestRows:
    """Project metadata-only owner rows and committed physical rows."""
    if isinstance(exported_ledgers, (str, bytes)) or not isinstance(
        exported_ledgers, Sequence
    ):
        raise TypeError("exported_ledgers must be a sequence")
    physical, physical_coverage = harvest_physical_rows_with_coverage(
        committed_events, policy=policy
    )
    claims: list[BorderClaimRow] = []
    recognitions: list[BorderRecognitionRow] = []
    access: list[BorderAccessRow] = []
    agreements: list[BorderAgreementRow] = []
    disputes: list[BorderDisputeRow] = []
    notices: set[str] = set()
    for group in exported_ledgers:
        (
            group_claims,
            group_recognitions,
            group_access,
            group_agreements,
            group_disputes,
        ) = _project_group(group)
        claims.extend(group_claims)
        recognitions.extend(group_recognitions)
        access.extend(group_access)
        agreements.extend(group_agreements)
        disputes.extend(group_disputes)
    if len(claims) > policy.max_rows_per_family * len(exported_ledgers):
        notices.add("borders_rows_truncated")
        claims = claims[: policy.max_rows_per_family]
    if len(agreements) > policy.max_rows_per_family:
        notices.add("borders_rows_truncated")
        agreements = agreements[: policy.max_rows_per_family]
    if len(disputes) > policy.max_rows_per_family:
        notices.add("borders_rows_truncated")
        disputes = disputes[: policy.max_rows_per_family]
    claims.sort(key=lambda item: (item.domain_token, item.owner_token))
    recognitions.sort(key=lambda item: (item.domain_token, item.basis))
    access.sort(key=lambda item: (item.domain_token, item.subject_token, item.mode))
    agreements.sort(key=lambda item: (item.domain_token, item.agreement_token))
    disputes.sort(key=lambda item: (item.domain_token, item.dispute_token))
    has_rows = bool(
        physical or claims or recognitions or access or agreements or disputes
    )
    if physical_coverage == "partial":
        coverage = "partial"
    elif has_rows:
        coverage = "complete"
    else:
        coverage = "not_applicable"
    _LOG.debug(
        "borders_harvest claims=%s agreements=%s disputes=%s physical=%s",
        len(claims),
        len(agreements),
        len(disputes),
        len(physical),
    )
    return BorderHarvestRows(
        physical=tuple(physical),
        claims=tuple(claims),
        recognitions=tuple(recognitions),
        access_expectations=tuple(access),
        agreements=tuple(agreements),
        disputes=tuple(disputes),
        notices=tuple(sorted(notices)),
        coverage=coverage,
    )


def border_rows_summary(rows: BorderHarvestRows) -> Mapping[str, int]:
    if type(rows) is not BorderHarvestRows:
        raise TypeError("rows must be BorderHarvestRows")
    return {
        "physical": len(rows.physical),
        "claims": len(rows.claims),
        "recognitions": len(rows.recognitions),
        "access_expectations": len(rows.access_expectations),
        "agreements": len(rows.agreements),
        "disputes": len(rows.disputes),
    }


__all__ = [
    "BorderHarvestRows",
    "border_rows_summary",
    "harvest_border_rows",
]
