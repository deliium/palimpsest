"""Build phenomenon indicator panels from already-computed MetricDocuments.

Analysis-only. Does not recompute NetworkX/pandas from raw evidence.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.models import MetricAvailability, MetricDocument
from analysis.phenomenon_models import (
    PHENOMENON_INDICATORS_SCHEMA_VERSION,
    PhenomenonId,
    PhenomenonIndicatorPanel,
    PhenomenonIndicatorReading,
    SupportBand,
)
from analysis.phenomenon_specifications import (
    indicator_meets_floor,
    phenomenon_indicator_refs,
    resolve_support_band,
    validate_phenomenon_mappings,
)
from world.identifiers import require_stable_id

__all__ = [
    "build_phenomenon_indicator_panel",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.phenomenon_panel")


def build_phenomenon_indicator_panel(
    documents: Sequence[MetricDocument],
    *,
    run_id: str,
    input_revision: str,
) -> PhenomenonIndicatorPanel:
    """Select indicator values by family/key and apply locked support_band rules."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    validate_phenomenon_mappings()
    by_family: dict[str, MetricDocument] = {}
    for doc in documents:
        if type(doc) is not MetricDocument:
            raise TypeError("documents: invalid_type")
        by_family[doc.metric_family] = doc

    readings: list[PhenomenonIndicatorReading] = []
    present_total = 0
    absent_total = 0
    for phenomenon_id in PhenomenonId:
        refs = phenomenon_indicator_refs(phenomenon_id)
        indicator_values: list[tuple[str, str, object, MetricAvailability]] = []
        present_count = 0
        meets_weak = 0
        meets_moderate = 0
        meets_strong = 0
        for ref in refs:
            doc = by_family.get(ref.metric_family)
            if doc is None or doc.availability is MetricAvailability.ABSENT:
                availability = MetricAvailability.ABSENT
                value: object = None
            elif doc.availability is MetricAvailability.UNKNOWN:
                availability = MetricAvailability.UNKNOWN
                value = None
            else:
                raw = doc.values.get(ref.value_key)
                if raw is None or type(raw) is not float and type(raw) is not int:
                    availability = MetricAvailability.ABSENT
                    value = None
                else:
                    availability = MetricAvailability.PRESENT
                    value = float(raw)
                    present_count += 1
                    if indicator_meets_floor(float(raw), ref.weak_floor, ref.direction):
                        meets_weak += 1
                    if indicator_meets_floor(
                        float(raw), ref.moderate_floor, ref.direction
                    ):
                        meets_moderate += 1
                    if indicator_meets_floor(float(raw), ref.strong_floor, ref.direction):
                        meets_strong += 1
            indicator_values.append(
                (ref.metric_family, ref.value_key, value, availability)
            )
        band = resolve_support_band(
            present_count=present_count,
            meets_weak=meets_weak,
            meets_moderate=meets_moderate,
            meets_strong=meets_strong,
            unary_allowed=len(refs) == 1,
        )
        if band is SupportBand.ABSENT:
            absent_total += 1
        else:
            present_total += 1
        readings.append(
            PhenomenonIndicatorReading(
                phenomenon_id=phenomenon_id,
                support_band=band,
                present_indicator_count=present_count,
                indicator_values=tuple(indicator_values),
            )
        )
        _LOG.debug(
            "phenomenon_support_band",
            extra={
                "operation": "build_phenomenon_indicator_panel",
                "phenomenon_id": phenomenon_id.value,
                "support_band": band.value,
                "present_indicator_count": present_count,
            },
        )

    _LOG.info(
        "phenomenon_panel_built",
        extra={
            "operation": "build_phenomenon_indicator_panel",
            "run_id": document_run,
            "phenomenon_count": len(readings),
            "present_tally": present_total,
            "absent_tally": absent_total,
        },
    )
    return PhenomenonIndicatorPanel(
        schema_version=PHENOMENON_INDICATORS_SCHEMA_VERSION,
        run_id=document_run,
        input_revision=revision,
        readings=tuple(readings),
    )
