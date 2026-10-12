"""Metric documents for exchange-function counts. Not a currency label."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.exchange_functions import (
    FORBIDDEN_KEYS,
    classify_exchange_functions,
)
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.specifications import MetricFamilyId, metric_specification
from world.events import WorldEvent
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.metric_service")
_LAYER: Final[str] = "research_inference"


def assemble_exchange_function_metrics(
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    input_revision: str,
    spec: object | None,
    as_of_tick: int,
    ledgers: Sequence[object] = (),
) -> tuple[MetricDocument, ...]:
    """Three families, one document per kind. An absent spec yields nothing."""
    if spec is None:
        _LOG.info(
            "exchange_functions_metrics_empty reason=resource_exchange_profile_absent"
        )
        return ()
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    require_exact_nonneg_int("as_of_tick", as_of_tick)
    views = classify_exchange_functions(events, spec=spec, ledgers=ledgers)
    documents = (
        *_rows(
            MetricFamilyId.EXCHANGE_ACCEPTANCE_SHARE,
            views.acceptance_share,
            document_run,
            revision,
        ),
        *_rows(
            MetricFamilyId.EXCHANGE_ACQUISITION_FATE,
            views.acquisition_fate,
            document_run,
            revision,
        ),
        *_rows(
            MetricFamilyId.EXCHANGE_QUOTE_HOMOGENEITY,
            views.quote_homogeneity,
            document_run,
            revision,
        ),
    )
    _LOG.debug(
        "exchange_functions_metrics_emitted family_id=%s row_count=%s",
        "exchange_functions",
        len(documents),
    )
    return documents


def _rows(
    family: MetricFamilyId,
    rows: Sequence[object],
    run_id: str,
    revision: str,
) -> tuple[MetricDocument, ...]:
    spec = metric_specification(family)
    documents: list[MetricDocument] = []
    for row in rows:
        values = {
            "layer": _LAYER,
            **{
                name: getattr(row, name)
                for name in spec.value_keys
                if hasattr(row, name)
            },
        }
        blocked = set(values) & FORBIDDEN_KEYS
        if blocked:
            _LOG.warning(
                "exchange_functions_forbidden_key family=%s keys=%s",
                family.value,
                ",".join(sorted(blocked)),
            )
            continue
        documents.append(
            MetricDocument(
                schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
                metric_family=spec.family_id.value,
                algorithm_version=spec.algorithm_version,
                library_versions=library_versions(),
                run_id=run_id,
                input_revision=revision,
                evidence_stages=frozenset(spec.evidence_inputs),
                population=spec.population,
                denominator=spec.denominator,
                coverage=MetricCoverage(observed=1, expected=1),
                availability=MetricAvailability.PRESENT,
                values=values,
                provenance=MetricProvenance(
                    source_kind="resource_exchange_profile",
                    source_ids=(run_id,),
                    notes_code="ok",
                ),
            )
        )
    _LOG.debug(
        "exchange_functions_metrics_emitted family_id=%s row_count=%s",
        family.value,
        len(documents),
    )
    return tuple(documents)
