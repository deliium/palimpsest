"""Read teaching audits and practice events after a run.

Analysis-only. This module does not fold teaching opportunities or apply
teaching belief updates, and those updaters do not import analysis.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

__all__ = [
    "CULTURAL_TRANSMISSION_METRIC_VERSION",
    "CulturalTransmissionMetricResult",
    "compute_cultural_transmission",
]

CULTURAL_TRANSMISSION_METRIC_VERSION: Final[str] = "cultural_transmission@1"
_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.cultural_transmission_metrics"
)
_DOMAINS: Final[tuple[str, ...]] = (
    "foraging",
    "navigation",
    "resource_detection",
    "crafting",
    "building",
    "healing",
    "communication",
    "teaching",
)
_LOW_BELOW: Final[float] = 0.34
_HIGH_AT: Final[float] = 0.67


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def _text(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _band_for_level(level: float) -> str:
    quantized = _quantize(level)
    if quantized < _LOW_BELOW:
        return "low"
    if quantized < _HIGH_AT:
        return "uncertain"
    return "high"


def _level_of(row: object) -> float | None:
    raw = getattr(row, "band_or_level", None)
    if type(raw) is not str:
        return None
    try:
        level = float(raw)
    except ValueError:
        return None
    if level != level:
        return None
    return _quantize(level)


@dataclass(frozen=True, slots=True)
class CulturalTransmissionMetricResult:
    """Harvested transmission measures. A missing side stays unmatched."""

    version: str
    availability: str
    advice_count: int
    belief_matches_advice: int
    misinformation_count: int
    objective_gains_without_practice: int | None
    unmatched_count: int
    normalized_entropy: float | None
    js_divergence: float | None


def _distributions(
    audits: Sequence[object],
) -> dict[str, tuple[float, ...]] | None:
    vectors: dict[str, dict[str, float]] = {}
    saw_objective = False
    for row in audits:
        if _text(getattr(row, "store", "")) != "objective":
            continue
        saw_objective = True
        agent = _text(getattr(row, "agent_id", ""))
        domain = _text(getattr(row, "domain", ""))
        level = _level_of(row)
        if not agent or domain not in _DOMAINS or level is None:
            continue
        vectors.setdefault(agent, {})[domain] = level
    if not saw_objective:
        return None
    positive = {
        agent: levels
        for agent, levels in vectors.items()
        if sum(levels.values()) > 0.0
    }
    if not positive:
        return {}
    return {
        agent: tuple(levels.get(domain, 0.0) for domain in _DOMAINS)
        for agent, levels in positive.items()
    }


def _normalized_entropy(vector: tuple[float, ...]) -> float:
    total = sum(vector)
    if total <= 0.0:
        return 0.0
    entropy = 0.0
    for level in vector:
        if level <= 0.0:
            continue
        probability = level / total
        entropy -= probability * math.log(probability)
    return entropy / math.log(len(vector))


def _as_distribution(vector: tuple[float, ...]) -> tuple[float, ...] | None:
    total = sum(vector)
    if total <= 0.0:
        return None
    return tuple(item / total for item in vector)


def _kl(source: tuple[float, ...], other: tuple[float, ...]) -> float:
    value = 0.0
    for probability, target in zip(source, other, strict=True):
        if probability <= 0.0:
            continue
        if target <= 0.0:
            return math.inf
        value += probability * math.log(probability / target)
    return value


def _js_to_mixture(
    distribution: tuple[float, ...],
    mixture: tuple[float, ...],
) -> float:
    midpoint = tuple(
        (left + right) / 2.0 for left, right in zip(distribution, mixture, strict=True)
    )
    return 0.5 * _kl(distribution, midpoint) + 0.5 * _kl(mixture, midpoint)


def _mean_divergence(vectors: dict[str, tuple[float, ...]]) -> float | None:
    if len(vectors) < 2:
        return None
    distributions: list[tuple[float, ...]] = []
    for row in vectors.values():
        distribution = _as_distribution(row)
        if distribution is None:
            return None
        distributions.append(distribution)
    width = len(_DOMAINS)
    mixture = tuple(
        sum(row[index] for row in distributions) / len(distributions)
        for index in range(width)
    )
    if sum(mixture) <= 0.0:
        return None
    return _quantize(
        sum(_js_to_mixture(row, mixture) for row in distributions) / len(distributions)
    )


def compute_cultural_transmission(
    audits: Sequence[object],
    practice_events: Sequence[object] | None,
    *,
    explain_low_below: float = _LOW_BELOW,
) -> CulturalTransmissionMetricResult:
    """Summarize harvested rows. Empty objective mass is unknown, not zero."""
    advice_count = 0
    matches = 0
    misinformation = 0
    unmatched = 0
    beliefs: dict[tuple[str, str], str] = {}
    objectives: dict[tuple[str, str, int], float] = {}
    for row in audits:
        store = _text(getattr(row, "store", ""))
        agent = _text(getattr(row, "agent_id", ""))
        domain = _text(getattr(row, "domain", ""))
        if store == "belief":
            level = _level_of(row)
            if level is None:
                unmatched += 1
                continue
            beliefs[(agent, domain)] = _band_for_level(level)
        elif store == "objective":
            level = _level_of(row)
            if level is None:
                unmatched += 1
                continue
            tick = getattr(row, "tick", None)
            if type(tick) is not int:
                unmatched += 1
                continue
            objectives[(agent, domain, tick)] = level
    gains: int | None = 0 if practice_events is not None else None
    practiced: set[tuple[str, str]] = set()
    if practice_events is not None:
        for event in practice_events:
            agent = _text(getattr(event, "agent_id", ""))
            domain = _text(getattr(event, "domain", ""))
            if not agent or not domain:
                unmatched += 1
                continue
            practiced.add((agent, domain))
    for row in audits:
        store = _text(getattr(row, "store", ""))
        if store == "advice":
            advice_count += 1
            token = _text(getattr(row, "token", ""))
            agent = _text(getattr(row, "agent_id", ""))
            domain = _text(getattr(row, "domain", ""))
            band = _text(getattr(row, "band_or_level", ""))
            if token == "explain":
                believed = beliefs.get((agent, domain))
                if believed is None:
                    unmatched += 1
                elif believed == band:
                    matches += 1
                if band == "high":
                    source = getattr(row, "source_agent_id", None)
                    tick = getattr(row, "tick", None)
                    if source is None or type(tick) is not int:
                        unmatched += 1
                    else:
                        source_level = objectives.get((_text(source), domain, tick))
                        if source_level is None:
                            unmatched += 1
                        elif source_level < explain_low_below:
                            misinformation += 1
        elif store == "objective" and gains is not None:
            level = _level_of(row)
            agent = _text(getattr(row, "agent_id", ""))
            domain = _text(getattr(row, "domain", ""))
            if level is None:
                continue
            if level > 0.0 and (agent, domain) not in practiced:
                gains += 1
    vectors = _distributions(audits)
    if vectors is None or vectors == {}:
        availability = "unknown"
        entropy = None
        divergence = None
    else:
        availability = "present"
        entropy = _quantize(
            sum(_normalized_entropy(row) for row in vectors.values()) / len(vectors)
        )
        divergence = _mean_divergence(vectors)
        if divergence is None:
            unmatched += 1
    _LOG.debug(
        "cultural_transmission advice_count=%s misinformation_count=%s",
        advice_count,
        misinformation,
    )
    return CulturalTransmissionMetricResult(
        version=CULTURAL_TRANSMISSION_METRIC_VERSION,
        availability=availability,
        advice_count=advice_count,
        belief_matches_advice=matches,
        misinformation_count=misinformation,
        objective_gains_without_practice=gains,
        unmatched_count=unmatched,
        normalized_entropy=entropy,
        js_divergence=divergence,
    )
