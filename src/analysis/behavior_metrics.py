"""Repeated-convention and behavioral-specialization metrics (Task 12).

Neutral primitives only — no culture, role, leader, friend, or enemy labels.
Uses deterministic pandas tables and NumPy/SciPy per Task 10 specifications.
"""

from __future__ import annotations

import logging
import math
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import entropy as scipy_entropy

from analysis.evidence import EvidenceStage
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    AppliedActionRow,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import (
    ACTION_VOCABULARY_V1,
    MetricFamilyId,
    metric_specification,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "compute_behavioral_specialization",
    "compute_repeated_conventions",
    "motif_token",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.behavior_metrics")
_VOCAB: Final[tuple[str, ...]] = ACTION_VOCABULARY_V1
_VOCAB_SET: Final[frozenset[str]] = frozenset(_VOCAB)
_MIN_SUPPORT: Final[int] = 2
_NGRAM_ORDERS: Final[tuple[int, ...]] = (2, 3)


def motif_token(
    action_kind: str,
    *,
    location_id: str | None = None,
    target_id: str | None = None,
) -> str:
    """Canonical lexicographic motif token; no role/culture labels."""
    kind = require_stable_id("action_kind", action_kind)
    parts = [kind]
    if location_id is not None:
        parts.append(f"loc:{require_stable_id('location_id', location_id)}")
    if target_id is not None:
        parts.append(f"tgt:{require_stable_id('target_id', target_id)}")
    return "|".join(parts)


def _document(
    *,
    family: str,
    algorithm_version: str,
    run_id: str,
    input_revision: str,
    evidence_stages: frozenset[EvidenceStage],
    population: str,
    denominator: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    coverage: MetricCoverage | None,
    notes_code: str,
) -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family,
        algorithm_version=algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=evidence_stages,
        population=population,
        denominator=denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="behavior_metrics",
            source_ids=(),
            notes_code=notes_code,
        ),
    )


def _q(value: float) -> float:
    return quantize_float(require_finite(float(value)))


def _sorted_actions(
    actions: Sequence[AppliedActionRow],
    *,
    window_start: int,
    window_end: int,
    death_ticks: Mapping[str, int],
) -> list[AppliedActionRow]:
    rows = [
        row
        for row in actions
        if window_start <= row.tick <= window_end and row.action_kind in _VOCAB_SET
    ]
    filtered: list[AppliedActionRow] = []
    for row in rows:
        death = death_ticks.get(row.agent_id)
        if death is not None and row.tick > death:
            continue
        filtered.append(row)
    filtered.sort(key=lambda item: (item.tick, item.ordinal, item.agent_id))
    return filtered


def compute_repeated_conventions(
    actions: Sequence[AppliedActionRow],
    *,
    run_id: str,
    input_revision: str,
    window_start: int = 0,
    window_end: int,
    death_ticks: Mapping[str, int] | None = None,
    include_location: bool = False,
    include_target: bool = False,
    max_gap_ticks: int = 0,
    min_support: int = _MIN_SUPPORT,
) -> MetricDocument:
    """Neutral n-gram / motif support with opportunity coverage."""
    started = time.perf_counter()
    spec = metric_specification(MetricFamilyId.REPEATED_CONVENTIONS)
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    window_end = require_exact_nonneg_int("window_end", window_end)
    max_gap_ticks = require_exact_nonneg_int("max_gap_ticks", max_gap_ticks)
    min_support = require_exact_nonneg_int("min_support", min_support)
    deaths = dict(death_ticks or {})
    ordered = _sorted_actions(
        actions,
        window_start=window_start,
        window_end=window_end,
        death_ticks=deaths,
    )
    _LOG.debug(
        "repeated_conventions_start",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "action_count": len(ordered),
            "max_gap_ticks": max_gap_ticks,
            "min_support": min_support,
        },
    )
    if not ordered:
        _LOG.warning(
            "repeated_conventions_empty",
            extra={
                "metric_family": spec.family_id.value,
                "algorithm_version": spec.algorithm_version,
                "code": "empty_token_stream",
            },
        )
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=spec.evidence_inputs,
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="empty_token_stream",
        )

    # Per-actor token stream sorted by tick, ordinal.
    by_agent: dict[str, list[AppliedActionRow]] = {}
    for row in ordered:
        by_agent.setdefault(row.agent_id, []).append(row)

    support: Counter[str] = Counter()
    first_tick: dict[str, int] = {}
    last_tick: dict[str, int] = {}
    opportunity_windows = 0
    matched_windows = 0
    short_sequence = False

    for agent_id in sorted(by_agent):
        sequence = by_agent[agent_id]
        tokens = [
            motif_token(
                row.action_kind,
                location_id=row.location_id if include_location else None,
                target_id=row.target_id if include_target else None,
            )
            for row in sequence
        ]
        ticks = [row.tick for row in sequence]
        for order in _NGRAM_ORDERS:
            if len(tokens) < order:
                short_sequence = True
                continue
            eligible = len(tokens) - order + 1
            opportunity_windows += eligible
            for index in range(eligible):
                window_ticks = ticks[index : index + order]
                gaps = [
                    window_ticks[i + 1] - window_ticks[i]
                    for i in range(order - 1)
                ]
                # Contiguous when max_gap_ticks==0 means successive tokens in
                # the actor stream (already consecutive indices); optional
                # tick-gap filter for gapped motifs.
                if max_gap_ticks == 0:
                    ok = all(gap >= 0 for gap in gaps)
                else:
                    ok = all(0 <= gap <= max_gap_ticks for gap in gaps)
                if not ok:
                    continue
                motif_id = ">>".join(tokens[index : index + order])
                support[motif_id] += 1
                matched_windows += 1
                tick_span_start = window_ticks[0]
                tick_span_end = window_ticks[-1]
                if motif_id not in first_tick or tick_span_start < first_tick[motif_id]:
                    first_tick[motif_id] = tick_span_start
                if motif_id not in last_tick or tick_span_end > last_tick[motif_id]:
                    last_tick[motif_id] = tick_span_end

    # Sort motifs by (-support, motif_id); keep those meeting min_support.
    ranked = sorted(
        ((motif_id, count) for motif_id, count in support.items()),
        key=lambda item: (-item[1], item[0]),
    )
    qualifying = [
        (motif_id, count) for motif_id, count in ranked if count >= min_support
    ]
    # Build deterministic table (not exported in flat values).
    if qualifying:
        frame = pd.DataFrame(
            {
                "motif_id": [item[0] for item in qualifying],
                "support": [item[1] for item in qualifying],
                "recurrence_span_ticks": [
                    last_tick[item[0]] - first_tick[item[0]] for item in qualifying
                ],
            }
        )
        frame = frame.sort_values(
            by=["support", "motif_id"], ascending=[False, True], kind="mergesort"
        )
        top_support = int(frame.iloc[0]["support"])
        motif_count = len(frame)
    else:
        top_support = 0
        motif_count = 0

    if opportunity_windows == 0:
        coverage_value: float | None = None
        availability = (
            MetricAvailability.PARTIAL
            if short_sequence
            else MetricAvailability.UNKNOWN
        )
    else:
        coverage_value = _q(matched_windows / float(opportunity_windows))
        availability = (
            MetricAvailability.PARTIAL if short_sequence else MetricAvailability.PRESENT
        )

    values: dict[str, object] = {
        "top_motif_support": top_support,
        "motif_count": motif_count,
        "motif_opportunity_coverage": coverage_value,
        "ngram_order_max": max(_NGRAM_ORDERS),
        "max_gap_ticks": max_gap_ticks,
    }
    if motif_count == 0 and opportunity_windows > 0:
        availability = MetricAvailability.PRESENT

    doc = _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=spec.evidence_inputs,
        population=spec.population,
        denominator=spec.denominator,
        availability=availability,
        values=values,
        coverage=MetricCoverage(
            observed=matched_windows,
            expected=max(opportunity_windows, 1),
            ratio=coverage_value if coverage_value is not None else None,
        ),
        notes_code="repeated_conventions_ok",
    )
    _LOG.debug(
        "repeated_conventions_done",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "motif_count": motif_count,
            "action_count": len(ordered),
            "availability": availability.value,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return doc


def _distribution(counts: Mapping[str, int], vocab: Sequence[str]) -> np.ndarray:
    total = float(sum(counts.values()))
    if total <= 0.0:
        raise ValueError("empty_distribution")
    return np.asarray(
        [float(counts.get(kind, 0)) / total for kind in vocab], dtype=np.float64
    )


def compute_behavioral_specialization(
    actions: Sequence[AppliedActionRow],
    *,
    run_id: str,
    input_revision: str,
    window_start: int = 0,
    window_end: int,
    death_ticks: Mapping[str, int] | None = None,
) -> MetricDocument:
    """Per-agent entropy/concentration and divergence from the population."""
    started = time.perf_counter()
    spec = metric_specification(MetricFamilyId.BEHAVIORAL_SPECIALIZATION)
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    window_end = require_exact_nonneg_int("window_end", window_end)
    deaths = dict(death_ticks or {})
    ordered = _sorted_actions(
        actions,
        window_start=window_start,
        window_end=window_end,
        death_ticks=deaths,
    )
    _LOG.debug(
        "behavioral_specialization_start",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "action_count": len(ordered),
        },
    )
    if not ordered:
        _LOG.warning(
            "behavioral_specialization_empty",
            extra={
                "metric_family": spec.family_id.value,
                "algorithm_version": spec.algorithm_version,
                "code": "no_agents_with_actions",
            },
        )
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=spec.evidence_inputs,
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="no_agents_with_actions",
        )

    by_agent: dict[str, Counter[str]] = {}
    for row in ordered:
        by_agent.setdefault(row.agent_id, Counter())[row.action_kind] += 1

    # Exclude zero-mass agents (already implicit).
    agent_ids = sorted(by_agent)
    population_counts: Counter[str] = Counter()
    for agent_id in agent_ids:
        population_counts.update(by_agent[agent_id])
    used_vocab = tuple(kind for kind in _VOCAB if population_counts.get(kind, 0) > 0)
    if not used_vocab:
        _LOG.error(
            "behavioral_specialization_vocab",
            extra={
                "metric_family": spec.family_id.value,
                "algorithm_version": spec.algorithm_version,
                "code": "empty_vocabulary",
            },
        )
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=spec.evidence_inputs,
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="empty_vocabulary",
        )

    pop_dist = _distribution(population_counts, used_vocab)
    entropies: list[float] = []
    normalized: list[float] = []
    herfindahls: list[float] = []
    divergences: list[float] = []

    for agent_id in agent_ids:
        counts = by_agent[agent_id]
        agent_vocab = tuple(kind for kind in used_vocab if counts.get(kind, 0) > 0)
        dist = _distribution(counts, used_vocab)
        # Shannon over positive probs via SciPy (zeros ignored by entropy).
        h = float(scipy_entropy(dist, base=2))
        if not math.isfinite(h):
            _LOG.error(
                "behavioral_specialization_non_finite",
                extra={
                    "metric_family": spec.family_id.value,
                    "algorithm_version": spec.algorithm_version,
                    "code": "non_finite_entropy",
                },
            )
            raise ValueError("non_finite_entropy")
        entropies.append(h)
        denom_bits = math.log2(len(agent_vocab)) if len(agent_vocab) > 1 else 0.0
        if len(agent_vocab) <= 1:
            normalized.append(0.0)
        else:
            normalized.append(h / denom_bits)
        herfindahls.append(float(np.dot(dist, dist)))
        if len(agent_ids) >= 2:
            # SciPy returns JS *distance* (sqrt); square for divergence.
            distance = float(jensenshannon(dist, pop_dist, base=2))
            if not math.isfinite(distance):
                _LOG.error(
                    "behavioral_specialization_non_finite",
                    extra={
                        "metric_family": spec.family_id.value,
                        "algorithm_version": spec.algorithm_version,
                        "code": "non_finite_js",
                    },
                )
                raise ValueError("non_finite_js")
            divergences.append(distance * distance)

    mean_norm = _q(float(np.mean(np.asarray(normalized, dtype=np.float64))))
    mean_hhi = _q(float(np.mean(np.asarray(herfindahls, dtype=np.float64))))
    if len(agent_ids) == 1:
        mean_js: float | None = None
        availability = MetricAvailability.PARTIAL
    else:
        mean_js = _q(float(np.mean(np.asarray(divergences, dtype=np.float64))))
        availability = MetricAvailability.PRESENT

    values: dict[str, object] = {
        "mean_normalized_entropy": mean_norm,
        "mean_herfindahl": mean_hhi,
        "mean_js_divergence": mean_js,
        "agents_scored": len(agent_ids),
    }
    doc = _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=spec.evidence_inputs,
        population=spec.population,
        denominator=spec.denominator,
        availability=availability,
        values=values,
        coverage=MetricCoverage(
            observed=len(agent_ids), expected=len(agent_ids), ratio=1.0
        ),
        notes_code="behavioral_specialization_ok",
    )
    _LOG.debug(
        "behavioral_specialization_done",
        extra={
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "run_id": run_id,
            "agents_scored": len(agent_ids),
            "availability": availability.value,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return doc
