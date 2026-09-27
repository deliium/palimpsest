"""Researcher-only relationship summaries. Ordinary frames do not import this."""

from __future__ import annotations

import logging
from collections import defaultdict

from observer.contracts import ObserverDimensionScore, ObserverRelationshipSummary
from observer.version import OBSERVER_PROTOCOL_VERSION

_LOGGER = logging.getLogger("observer.relationships")


def project_relationship_summaries(
    rows: tuple[tuple[str, str, str, float], ...],
) -> tuple[ObserverRelationshipSummary, ...]:
    """Group ``(owner_id, target_id, dimension, value)`` without re-quantizing."""
    grouped: dict[tuple[str, str], list[ObserverDimensionScore]] = defaultdict(list)
    for owner_id, target_id, dimension, value in rows:
        grouped[(owner_id, target_id)].append(
            ObserverDimensionScore(dimension=dimension, value=value)
        )
    summaries = tuple(
        ObserverRelationshipSummary(
            owner_id=owner_id,
            target_id=target_id,
            dimensions=tuple(scores),
            protocol_version=OBSERVER_PROTOCOL_VERSION,
        )
        for (owner_id, target_id), scores in sorted(grouped.items())
    )
    owners = {owner_id for owner_id, _target in grouped}
    for owner_id in sorted(owners):
        target_count = sum(1 for key in grouped if key[0] == owner_id)
        _LOGGER.debug(
            "relationship_summary_projected owner_id=%s target_count=%s",
            owner_id,
            target_count,
        )
    return summaries


__all__ = ["project_relationship_summaries"]
