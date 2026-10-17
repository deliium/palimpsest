"""Sibling metric families for barter. Reservations are not a market number."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from analysis.subjective_value import (
    ExchangeLedgerSnapshot,
    ExchangeView,
    classify_exchange,
)
from world.events import WorldEvent
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.subjective_value_metrics")
_LAYER: Final[str] = "research_inference"
_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {"price", "world_price", "market_price", "clearing_price", "posted_price"}
)

EXCHANGE_RESERVATION_DIVERGENCE_METRIC_VERSION: Final[str] = (
    "exchange_reservation_divergence@1"
)
EXCHANGE_NEGOTIATION_PATH_METRIC_VERSION: Final[str] = "exchange_negotiation_path@1"
EXCHANGE_REALIZED_BUNDLES_METRIC_VERSION: Final[str] = "exchange_realized_bundles@1"


def assemble_subjective_value_metrics(
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    input_revision: str,
    spec: object | None,
    as_of_tick: int,
    ledgers: Sequence[ExchangeLedgerSnapshot] = (),
    owner_ids: Sequence[str] = (),
) -> tuple[MetricDocument, ...]:
    """Three families. An absent spec yields an empty harvest."""
    if spec is None:
        return ()
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    views = classify_exchange(
        events,
        as_of_tick=tick,
        ledgers=ledgers,
        owner_ids=owner_ids,
    )
    documents = (
        _divergence(views, document_run, revision),
        _path(views, document_run, revision),
        _bundles(views, document_run, revision),
    )
    _LOG.debug(
        "subjective_value_metrics_assembled family_ids=%s row_counts=%s",
        [document.metric_family for document in documents],
        [len(views), len(views), len(views)],
    )
    return documents


def _document(
    spec: MetricSpecification,
    run_id: str,
    revision: str,
    values: Mapping[str, object],
    *,
    observed: int,
) -> MetricDocument:
    if set(values) & _FORBIDDEN_KEYS:
        raise ValueError("price field")
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=MetricCoverage(observed=observed, expected=max(observed, 1)),
        availability=MetricAvailability.PRESENT,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="subjective_valuation",
            source_ids=(run_id,),
            notes_code="ok",
        ),
    )


def _divergence(
    views: Sequence[ExchangeView], run_id: str, revision: str
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.EXCHANGE_RESERVATION_DIVERGENCE)
    if spec.version_identifier != EXCHANGE_RESERVATION_DIVERGENCE_METRIC_VERSION:
        raise ValueError("unsupported_metric_version")
    rows = [
        f"{row.owner_id}:{row.item_kind}:{row.reservation}"
        for view in views
        for row in view.reservations
        if row.status == "formed" and row.reservation is not None
    ]
    unformed = sum(
        1 for view in views for row in view.reservations if row.status == "unformed"
    )
    return _document(
        spec,
        run_id,
        revision,
        {
            "layer": _LAYER,
            "reservations": ",".join(sorted(rows)),
            "divergent_count": sum(view.divergent for view in views),
            "unformed_count": unformed,
        },
        observed=len(views),
    )


def _path(views: Sequence[ExchangeView], run_id: str, revision: str) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.EXCHANGE_NEGOTIATION_PATH)
    if spec.version_identifier != EXCHANGE_NEGOTIATION_PATH_METRIC_VERSION:
        raise ValueError("unsupported_metric_version")
    tokens = [token for view in views for token in view.path]
    return _document(
        spec,
        run_id,
        revision,
        {
            "layer": _LAYER,
            "offer_count": tokens.count("offer"),
            "counteroffer_count": tokens.count("counteroffer"),
            "withdraw_count": tokens.count("withdraw"),
            "complete_count": tokens.count("complete"),
        },
        observed=len(tokens),
    )


def _bundles(
    views: Sequence[ExchangeView], run_id: str, revision: str
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.EXCHANGE_REALIZED_BUNDLES)
    if spec.version_identifier != EXCHANGE_REALIZED_BUNDLES_METRIC_VERSION:
        raise ValueError("unsupported_metric_version")
    counts: dict[str, int] = {}
    completes = 0
    for view in views:
        completes += view.path.count("complete")
        for kind, count in view.realized_bundle:
            counts[kind] = counts.get(kind, 0) + count
    kind_counts = ",".join(f"{kind}:{count}" for kind, count in sorted(counts.items()))
    return _document(
        spec,
        run_id,
        revision,
        {
            "layer": _LAYER,
            "kind_counts": kind_counts,
            "complete_count": completes,
        },
        observed=completes,
    )
