"""Sibling metric families for corpse custody. Labels are not world facts."""

from __future__ import annotations

import logging
from collections import Counter
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
from analysis.possession_succession import (
    PossessionLedgerSnapshot,
    classify_possession_episodes,
)
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from world.events import WorldEvent
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.possession_succession_metrics"
)
_LAYER: Final[str] = "research_inference"
_CORPSE: Final[str] = "corpse"

POSSESSION_CUSTODY_OUTCOMES_METRIC_VERSION: Final[str] = (
    "possession_custody_outcomes@1"
)
POSSESSION_CLAIM_CONFLICT_METRIC_VERSION: Final[str] = "possession_claim_conflict@1"
INHERITANCE_CONVENTION_DISTRIBUTION_METRIC_VERSION: Final[str] = (
    "inheritance_convention_distribution@1"
)


def assemble_possession_succession_metrics(
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    input_revision: str,
    spec: object | None,
    as_of_tick: int,
    ledgers: Sequence[PossessionLedgerSnapshot] = (),
    children_of: Mapping[str, frozenset[str]] | None = None,
    caregivers_of: Mapping[str, frozenset[str]] | None = None,
    co_members_of: Mapping[str, frozenset[str]] | None = None,
) -> tuple[MetricDocument, ...]:
    """Three families. An absent spec yields an empty harvest."""
    if spec is None:
        return ()
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    episodes = classify_possession_episodes(
        events,
        as_of_tick=tick,
        ledgers=ledgers,
        children_of=children_of,
        caregivers_of=caregivers_of,
        co_members_of=co_members_of,
    )
    documents = (
        _custody(episodes, document_run, revision),
        _conflict(episodes, document_run, revision),
        _conventions(episodes, document_run, revision),
    )
    _LOG.debug(
        "possession_succession_metrics_assembled family_ids=%s row_counts=%s",
        [document.metric_family for document in documents],
        [len(episodes), len(episodes), len(episodes)],
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
            source_kind="possession_succession",
            source_ids=(run_id,),
            notes_code="ok",
        ),
    )


def _custody(episodes, run_id: str, revision: str) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.POSSESSION_CUSTODY_OUTCOMES)
    if spec.version_identifier != POSSESSION_CUSTODY_OUTCOMES_METRIC_VERSION:
        raise ValueError("unsupported_metric_version")
    corpse = 0
    taken = 0
    voluntary = 0
    for episode in episodes:
        for _item_id, holder in episode.physical_possession:
            if holder == _CORPSE:
                corpse += 1
            else:
                taken += 1
        if episode.voluntary_transfer:
            voluntary += 1
    return _document(
        spec,
        run_id,
        revision,
        {
            "layer": _LAYER,
            "episode_count": len(episodes),
            "corpse_item_count": corpse,
            "taken_item_count": taken,
            "voluntary_transfer_episode_count": voluntary,
        },
        observed=len(episodes),
    )


def _conflict(episodes, run_id: str, revision: str) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.POSSESSION_CLAIM_CONFLICT)
    if spec.version_identifier != POSSESSION_CLAIM_CONFLICT_METRIC_VERSION:
        raise ValueError("unsupported_metric_version")
    return _document(
        spec,
        run_id,
        revision,
        {
            "layer": _LAYER,
            "episode_count": len(episodes),
            "conflict_episode_count": sum(episode.conflict for episode in episodes),
            "claim_count": sum(len(episode.legitimacy_claims) for episode in episodes),
        },
        observed=len(episodes),
    )


def _conventions(episodes, run_id: str, revision: str) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.INHERITANCE_CONVENTION_DISTRIBUTION)
    if spec.version_identifier != INHERITANCE_CONVENTION_DISTRIBUTION_METRIC_VERSION:
        raise ValueError("unsupported_metric_version")
    counts = Counter(episode.convention_token for episode in episodes)
    histogram = ",".join(
        f"{token}:{count}" for token, count in sorted(counts.items())
    )
    return _document(
        spec,
        run_id,
        revision,
        {
            "layer": _LAYER,
            "contested_count": counts.get("contested", 0),
            "unformed_count": counts.get("unformed", 0),
            "convention_histogram": histogram,
        },
        observed=len(episodes),
    )
