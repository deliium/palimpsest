"""Detached, metadata-only semantic stability, drift, and divergence analysis.

Rows carry owner ids, surface digests, and opaque referent digests only. Ledgers
are duck-typed at the harvest boundary; no subjective ledger type is imported
here and no raw token, message body, or narration enters a document. These
metrics describe recorded sense changes and never force convergence.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import (
    jensen_shannon_divergence,
    library_versions,
    quantize_float,
)
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "SEMANTIC_DIVERGENCE_METRIC_VERSION",
    "SEMANTIC_DRIFT_METRIC_VERSION",
    "SEMANTIC_STABILITY_METRIC_VERSION",
    "SemanticAnalysisError",
    "SemanticAnalysisInputs",
    "SemanticDivergenceResult",
    "SemanticDriftResult",
    "SemanticSenseRow",
    "SemanticStabilityResult",
    "SemanticUsageRow",
    "compute_semantic_divergence",
    "compute_semantic_divergence_metric",
    "compute_semantic_drift",
    "compute_semantic_drift_metric",
    "compute_semantic_stability",
    "compute_semantic_stability_metric",
    "semantic_analysis_inputs_from_harvest",
    "semantic_sense_rows_from_ledgers",
    "semantic_term_digest",
    "semantic_usage_rows_from_ledgers",
]

SEMANTIC_STABILITY_METRIC_VERSION: Final[str] = "semantic_stability@1"
SEMANTIC_DRIFT_METRIC_VERSION: Final[str] = "semantic_drift@1"
SEMANTIC_DIVERGENCE_METRIC_VERSION: Final[str] = "semantic_divergence@1"

_TERM_SOURCES: Final[frozenset[str]] = frozenset({"label", "composition"})
_TRIGGERS: Final[frozenset[str]] = frozenset({"promoted", "shifted", "merged"})
_CHANNELS: Final[frozenset[str]] = frozenset(
    {"observed", "communicated", "remembered", "self_use"}
)
_LOG: Final[logging.Logger] = logging.getLogger("analysis.semantic_drift")


class SemanticAnalysisError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


def _surface_digest(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def semantic_term_digest(
    term_source: str,
    *,
    label_token: str | None = None,
    kind: str | None = None,
    parts: Sequence[str] | None = None,
) -> str:
    """Stable cross-owner surface digest of a label or binary composition."""
    if term_source not in _TERM_SOURCES:
        raise SemanticAnalysisError("invalid_term_source")
    if term_source == "label":
        if not isinstance(label_token, str) or not label_token:
            raise SemanticAnalysisError("invalid_label_token")
        return _surface_digest(f"label|{label_token}")
    if not isinstance(kind, str) or not kind:
        raise SemanticAnalysisError("invalid_composition_kind")
    checked = tuple(parts or ())
    if len(checked) != 2 or any(
        not isinstance(item, str) or not item for item in checked
    ):
        raise SemanticAnalysisError("invalid_composition_parts")
    return _surface_digest(
        "composition|"
        f"{kind}|{_surface_digest(checked[0])}|{_surface_digest(checked[1])}"
    )


def _referent_digest(referent_kind: str, referent_id: str) -> str:
    return _surface_digest(f"referent|{referent_kind}|{referent_id}")


def _symbolic_referent_digest(associated_ids: Sequence[str]) -> str | None:
    ordered = tuple(item for item in associated_ids if isinstance(item, str) and item)
    if not ordered:
        return None
    return _surface_digest("composition-referent|" + "|".join(ordered))


@dataclass(frozen=True, slots=True)
class SemanticSenseRow:
    owner_id: str
    term_digest: str
    term_source: str
    referent_kind: str | None
    referent_digest: str | None
    associated_digests: tuple[str, ...]
    tick: int
    sense_revision: int
    trigger: str

    def __post_init__(self) -> None:
        for name in ("owner_id", "term_digest"):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        if self.term_source not in _TERM_SOURCES:
            raise SemanticAnalysisError("invalid_term_source")
        if self.referent_kind is not None:
            object.__setattr__(
                self,
                "referent_kind",
                require_stable_id("referent_kind", self.referent_kind),
            )
        if self.referent_digest is not None:
            object.__setattr__(
                self,
                "referent_digest",
                require_stable_id("referent_digest", self.referent_digest),
            )
        associated = tuple(self.associated_digests)
        for item in associated:
            require_stable_id("associated_digest", item)
        object.__setattr__(self, "associated_digests", associated)
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self,
            "sense_revision",
            require_exact_nonneg_int("sense_revision", self.sense_revision),
        )
        if self.trigger not in _TRIGGERS:
            raise SemanticAnalysisError("invalid_trigger")


@dataclass(frozen=True, slots=True)
class SemanticUsageRow:
    owner_id: str
    term_digest: str
    term_source: str
    tick: int
    channel: str
    actor_digest: str | None
    referent_digest: str | None

    def __post_init__(self) -> None:
        for name in ("owner_id", "term_digest"):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        if self.term_source not in _TERM_SOURCES:
            raise SemanticAnalysisError("invalid_term_source")
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        if self.channel not in _CHANNELS:
            raise SemanticAnalysisError("invalid_channel")
        if self.actor_digest is not None:
            object.__setattr__(
                self,
                "actor_digest",
                require_stable_id("actor_digest", self.actor_digest),
            )
        if self.referent_digest is not None:
            object.__setattr__(
                self,
                "referent_digest",
                require_stable_id("referent_digest", self.referent_digest),
            )


@dataclass(frozen=True, slots=True)
class SemanticAnalysisInputs:
    senses: Sequence[SemanticSenseRow] = ()
    usages: Sequence[SemanticUsageRow] = ()
    communities: Sequence[object] = ()
    generation_index_by_owner: Mapping[str, int] | None = None
    expected_owner_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "senses", tuple(self.senses))
        object.__setattr__(self, "usages", tuple(self.usages))
        object.__setattr__(self, "communities", tuple(self.communities))
        generations: dict[str, int] = {}
        for key, value in dict(self.generation_index_by_owner or {}).items():
            owner = require_stable_id("generation_owner", key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SemanticAnalysisError("invalid_generation_index")
            generations[owner] = value
        object.__setattr__(
            self, "generation_index_by_owner", generations or None
        )
        object.__setattr__(
            self,
            "expected_owner_count",
            require_exact_nonneg_int("expected_owner_count", self.expected_owner_count),
        )


@dataclass(frozen=True, slots=True)
class SemanticStabilityResult:
    term_count: int
    observed_term_count: int
    stable_referent_count: int
    stable_association_count: int
    retained_transition_count: int
    transition_count: int
    mean_sense_revision: float | None
    cross_generation_term_count: int
    cross_generation_stable_count: int
    availability: MetricAvailability
    coverage: MetricCoverage


@dataclass(frozen=True, slots=True)
class SemanticDriftResult:
    transition_count: int
    referent_switch_count: int
    association_change_count: int
    mean_jaccard_distance: float | None
    mean_ticks_between_changes: float | None
    revision_count: int
    multi_referent_term_count: int
    usage_context_count: int
    channel_counts: tuple[tuple[str, int], ...]
    drift_rate: float | None
    availability: MetricAvailability
    coverage: MetricCoverage


@dataclass(frozen=True, slots=True)
class SemanticDivergenceResult:
    group_count: int
    generation_count: int
    between_group_divergence: float | None
    within_group_divergence: float | None
    between_generation_divergence: float | None
    within_generation_divergence: float | None
    cross_generation_continuity: float | None
    pairwise_divergence: float | None
    unknown_referent_count: int
    availability: MetricAvailability
    coverage: MetricCoverage


def _coverage(observed: int, expected: int | None) -> MetricCoverage:
    resolved = 0 if expected is None else max(expected, 0)
    ratio = None if resolved <= 0 else quantize_float(min(1.0, observed / resolved))
    return MetricCoverage(observed=observed, expected=resolved, ratio=ratio)


def _ledgers(ledgers: object) -> tuple[object, ...]:
    if ledgers is None:
        return ()
    if isinstance(ledgers, Mapping):
        return tuple(ledgers.values())
    if isinstance(ledgers, Sequence) and not isinstance(ledgers, (str, bytes)):
        return tuple(ledgers)
    return ()


def _naming_sense_rows(ledgers: object) -> list[SemanticSenseRow]:
    rows: list[SemanticSenseRow] = []
    for ledger in _ledgers(ledgers):
        for binding in getattr(ledger, "bindings", ()) or ():
            token = getattr(binding, "label_token", None)
            if not isinstance(token, str) or not token:
                continue
            term_digest = semantic_term_digest("label", label_token=token)
            referent_kind = getattr(
                getattr(binding, "referent_kind", None), "value", None
            )
            for record in getattr(binding, "sense_history", ()) or ():
                kind = getattr(getattr(record, "referent_kind", None), "value", None)
                referent_id = getattr(record, "referent_id", None)
                if not isinstance(kind, str) or not isinstance(referent_id, str):
                    continue
                associated = tuple(
                    _referent_digest(kind, item)
                    for item in getattr(record, "associated_ids", ()) or ()
                    if isinstance(item, str) and item
                )
                rows.append(
                    SemanticSenseRow(
                        owner_id=require_stable_id(
                            "owner_id",
                            getattr(
                                getattr(binding, "owner_id", None), "value", ""
                            ),
                        ),
                        term_digest=term_digest,
                        term_source="label",
                        referent_kind=kind or referent_kind,
                        referent_digest=_referent_digest(kind, referent_id),
                        associated_digests=associated,
                        tick=getattr(record, "tick", 0),
                        sense_revision=getattr(binding, "sense_revision", 0),
                        trigger=getattr(getattr(record, "trigger", None), "value", ""),
                    )
                )
    return rows


def _symbolic_sense_rows(ledgers: object) -> list[SemanticSenseRow]:
    rows: list[SemanticSenseRow] = []
    for ledger in _ledgers(ledgers):
        for composition in getattr(ledger, "compositions", ()) or ():
            parts = tuple(getattr(composition, "parts", ()) or ())
            kind = getattr(getattr(composition, "kind", None), "value", None)
            if len(parts) != 2 or not isinstance(kind, str):
                continue
            term_digest = semantic_term_digest(
                "composition", kind=kind, parts=parts
            )
            for record in getattr(composition, "sense_history", ()) or ():
                record_kind = getattr(
                    getattr(record, "referent_kind", None), "value", None
                )
                associated_ids = tuple(
                    item
                    for item in getattr(record, "associated_ids", ()) or ()
                    if isinstance(item, str) and item
                )
                associated = tuple(
                    _referent_digest(record_kind or "unspecified", item)
                    for item in associated_ids
                )
                rows.append(
                    SemanticSenseRow(
                        owner_id=require_stable_id(
                            "owner_id",
                            getattr(
                                getattr(composition, "owner_id", None), "value", ""
                            ),
                        ),
                        term_digest=term_digest,
                        term_source="composition",
                        referent_kind=record_kind,
                        referent_digest=_symbolic_referent_digest(associated_ids),
                        associated_digests=associated,
                        tick=getattr(record, "tick", 0),
                        sense_revision=getattr(composition, "sense_revision", 0),
                        trigger=getattr(getattr(record, "trigger", None), "value", ""),
                    )
                )
    return rows


def _latest_referent(
    history: Sequence[object], tick: int
) -> str | None:
    selected: object | None = None
    for record in history:
        if getattr(record, "tick", -1) <= tick:
            selected = record
        else:
            break
    if selected is None:
        return None
    kind = getattr(getattr(selected, "referent_kind", None), "value", None)
    if not isinstance(kind, str):
        return None
    if hasattr(selected, "referent_id"):
        referent_id = getattr(selected, "referent_id", None)
        if not isinstance(referent_id, str) or not referent_id:
            return None
        return _referent_digest(kind, referent_id)
    associated = tuple(
        item
        for item in getattr(selected, "associated_ids", ()) or ()
        if isinstance(item, str) and item
    )
    return _symbolic_referent_digest(associated)


def _actor_digest(evidence: object) -> str | None:
    actor = getattr(evidence, "actor_id", None)
    if actor is None:
        actor = getattr(evidence, "speaker_id", None)
    value = getattr(actor, "value", None)
    if not isinstance(value, str) or not value:
        return None
    return _surface_digest(f"actor|{value}")


def _naming_usage_rows(ledgers: object) -> list[SemanticUsageRow]:
    rows: list[SemanticUsageRow] = []
    for ledger in _ledgers(ledgers):
        for binding in getattr(ledger, "bindings", ()) or ():
            token = getattr(binding, "label_token", None)
            if not isinstance(token, str) or not token:
                continue
            term_digest = semantic_term_digest("label", label_token=token)
            owner_id = require_stable_id(
                "owner_id", getattr(getattr(binding, "owner_id", None), "value", "")
            )
            history = tuple(getattr(binding, "sense_history", ()) or ())
            for evidence in getattr(binding, "evidence", ()) or ():
                tick = getattr(evidence, "tick", None)
                if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
                    continue
                channel = getattr(getattr(evidence, "channel", None), "value", None)
                if not isinstance(channel, str) or channel not in _CHANNELS:
                    continue
                rows.append(
                    SemanticUsageRow(
                        owner_id=owner_id,
                        term_digest=term_digest,
                        term_source="label",
                        tick=tick,
                        channel=channel,
                        actor_digest=_actor_digest(evidence),
                        referent_digest=_latest_referent(history, tick),
                    )
                )
    return rows


def _symbolic_usage_rows(ledgers: object) -> list[SemanticUsageRow]:
    rows: list[SemanticUsageRow] = []
    for ledger in _ledgers(ledgers):
        for composition in getattr(ledger, "compositions", ()) or ():
            parts = tuple(getattr(composition, "parts", ()) or ())
            kind = getattr(getattr(composition, "kind", None), "value", None)
            if len(parts) != 2 or not isinstance(kind, str):
                continue
            term_digest = semantic_term_digest(
                "composition", kind=kind, parts=parts
            )
            owner_id = require_stable_id(
                "owner_id",
                getattr(getattr(composition, "owner_id", None), "value", ""),
            )
            history = tuple(getattr(composition, "sense_history", ()) or ())
            for evidence in getattr(composition, "evidence", ()) or ():
                tick = getattr(evidence, "tick", None)
                if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
                    continue
                channel = getattr(getattr(evidence, "channel", None), "value", None)
                if not isinstance(channel, str) or channel not in _CHANNELS:
                    continue
                rows.append(
                    SemanticUsageRow(
                        owner_id=owner_id,
                        term_digest=term_digest,
                        term_source="composition",
                        tick=tick,
                        channel=channel,
                        actor_digest=_actor_digest(evidence),
                        referent_digest=_latest_referent(history, tick),
                    )
                )
    return rows


def semantic_sense_rows_from_ledgers(
    *,
    naming_ledgers: object = None,
    symbolic_ledgers: object = None,
) -> tuple[SemanticSenseRow, ...]:
    rows = [
        *_naming_sense_rows(naming_ledgers),
        *_symbolic_sense_rows(symbolic_ledgers),
    ]
    rows.sort(
        key=lambda item: (
            item.owner_id,
            item.term_source,
            item.term_digest,
            item.tick,
        )
    )
    _LOG.debug(
        "semantic_sense_rows_built row_count=%s label_count=%s composition_count=%s",
        len(rows),
        sum(1 for item in rows if item.term_source == "label"),
        sum(1 for item in rows if item.term_source == "composition"),
    )
    return tuple(rows)


def semantic_usage_rows_from_ledgers(
    *,
    naming_ledgers: object = None,
    symbolic_ledgers: object = None,
) -> tuple[SemanticUsageRow, ...]:
    rows = [
        *_naming_usage_rows(naming_ledgers),
        *_symbolic_usage_rows(symbolic_ledgers),
    ]
    rows.sort(
        key=lambda item: (
            item.owner_id,
            item.term_source,
            item.term_digest,
            item.tick,
        )
    )
    _LOG.debug("semantic_usage_rows_built row_count=%s", len(rows))
    return tuple(rows)


def semantic_analysis_inputs_from_harvest(
    *,
    naming_ledgers: object = None,
    symbolic_ledgers: object = None,
    events: Sequence[object] = (),
    communities: Sequence[object] = (),
    generation_index_by_owner: Mapping[str, int] | None = None,
    expected_owner_count: int = 0,
) -> SemanticAnalysisInputs:
    """Compose detached semantic inputs. Events are reserved and may be empty."""
    del events
    senses = semantic_sense_rows_from_ledgers(
        naming_ledgers=naming_ledgers, symbolic_ledgers=symbolic_ledgers
    )
    usages = semantic_usage_rows_from_ledgers(
        naming_ledgers=naming_ledgers, symbolic_ledgers=symbolic_ledgers
    )
    _LOG.info(
        "semantic_analysis_harvest sense_count=%s usage_count=%s",
        len(senses),
        len(usages),
    )
    return SemanticAnalysisInputs(
        senses=senses,
        usages=usages,
        communities=communities,
        generation_index_by_owner=generation_index_by_owner,
        expected_owner_count=expected_owner_count,
    )


def _community_map(communities: Sequence[object]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for community in communities:
        community_id = getattr(community, "community_id", None)
        for person in getattr(community, "person_ids", ()) or ():
            key = getattr(person, "value", None) or str(person)
            mapping[key] = str(community_id)
    return mapping


def _term_histories(
    senses: Sequence[SemanticSenseRow],
) -> dict[tuple[str, str, str], list[SemanticSenseRow]]:
    grouped: dict[tuple[str, str, str], list[SemanticSenseRow]] = defaultdict(list)
    for row in senses:
        grouped[(row.owner_id, row.term_source, row.term_digest)].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: (item.tick, item.sense_revision, item.trigger))
    return grouped


def _validate_inputs(inputs: SemanticAnalysisInputs) -> None:
    if type(inputs) is not SemanticAnalysisInputs:
        raise SemanticAnalysisError("invalid_inputs")
    for sense in inputs.senses:
        if type(sense) is not SemanticSenseRow:
            raise SemanticAnalysisError("invalid_sense_row")
    for usage in inputs.usages:
        if type(usage) is not SemanticUsageRow:
            raise SemanticAnalysisError("invalid_usage_row")


def compute_semantic_stability(
    inputs: SemanticAnalysisInputs,
) -> SemanticStabilityResult:
    """Summarize retention and sense persistence, never a target."""
    _validate_inputs(inputs)
    histories = _term_histories(inputs.senses)
    observed = {(source, digest) for _, source, digest in histories}
    term_count = len(observed)
    stable_referent = 0
    stable_association = 0
    retained = 0
    transitions = 0
    revisions: list[int] = []
    multi_observation_terms = 0
    for rows in histories.values():
        if len(rows) < 2:
            if rows:
                revisions.append(max(item.sense_revision for item in rows))
            continue
        multi_observation_terms += 1
        first, last = rows[0], rows[-1]
        if (
            first.referent_digest is not None
            and last.referent_digest is not None
            and first.referent_digest == last.referent_digest
        ):
            stable_referent += 1
        if first.associated_digests == last.associated_digests:
            stable_association += 1
        for left, right in pairwise(rows):
            transitions += 1
            if (
                left.referent_digest is not None
                and left.referent_digest == right.referent_digest
                and left.associated_digests == right.associated_digests
            ):
                retained += 1
        revisions.append(max(item.sense_revision for item in rows))
    generation_map = dict(inputs.generation_index_by_owner or {})
    cross_generation_term_count = 0
    cross_generation_stable = 0
    if generation_map:
        by_term: dict[tuple[str, str], dict[int, str | None]] = defaultdict(dict)
        for row in inputs.senses:
            generation = generation_map.get(row.owner_id)
            if generation is None or row.referent_digest is None:
                continue
            by_term[(row.term_source, row.term_digest)][generation] = (
                row.referent_digest
            )
        for generations in by_term.values():
            if len(generations) < 2:
                continue
            cross_generation_term_count += 1
            ordered = [generations[key] for key in sorted(generations)]
            if ordered[0] is not None and ordered[0] == ordered[-1]:
                cross_generation_stable += 1
    owners = {row.owner_id for row in inputs.senses}
    availability = (
        MetricAvailability.PRESENT
        if multi_observation_terms > 0
        else MetricAvailability.ABSENT
    )
    result = SemanticStabilityResult(
        term_count=term_count,
        observed_term_count=len(histories),
        stable_referent_count=stable_referent,
        stable_association_count=stable_association,
        retained_transition_count=retained,
        transition_count=transitions,
        mean_sense_revision=(
            None if not revisions else quantize_float(sum(revisions) / len(revisions))
        ),
        cross_generation_term_count=cross_generation_term_count,
        cross_generation_stable_count=cross_generation_stable,
        availability=availability,
        coverage=_coverage(len(owners), inputs.expected_owner_count),
    )
    _LOG.info(
        "semantic_stability_computed availability=%s term_count=%s",
        result.availability.value,
        result.term_count,
    )
    return result


def _jaccard_distance(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 0.0
    return quantize_float(1.0 - (len(left_set & right_set) / len(union)))


def compute_semantic_drift(inputs: SemanticAnalysisInputs) -> SemanticDriftResult:
    """Describe recorded transitions and usage contexts, never a target."""
    _validate_inputs(inputs)
    histories = _term_histories(inputs.senses)
    transitions = 0
    referent_switches = 0
    association_changes = 0
    distances: list[float] = []
    change_ticks: list[int] = []
    revisions = 0
    multi_referent_terms = 0
    for rows in histories.values():
        revisions += max((item.sense_revision for item in rows), default=0)
        referents = {
            item.referent_digest for item in rows if item.referent_digest is not None
        }
        if len(referents) >= 2:
            multi_referent_terms += 1
        for left, right in pairwise(rows):
            transitions += 1
            distances.append(
                _jaccard_distance(left.associated_digests, right.associated_digests)
            )
            changed = False
            if (
                left.referent_digest is not None
                and right.referent_digest is not None
                and left.referent_digest != right.referent_digest
            ):
                referent_switches += 1
                changed = True
            if left.associated_digests != right.associated_digests:
                association_changes += 1
                changed = True
            if changed:
                change_ticks.append(max(0, right.tick - left.tick))
    channels = Counter(row.channel for row in inputs.usages)
    owners = {row.owner_id for row in inputs.senses}
    drift_rate = (
        None
        if transitions == 0
        else quantize_float(referent_switches / transitions)
    )
    result = SemanticDriftResult(
        transition_count=transitions,
        referent_switch_count=referent_switches,
        association_change_count=association_changes,
        mean_jaccard_distance=(
            None if not distances else quantize_float(sum(distances) / len(distances))
        ),
        mean_ticks_between_changes=(
            None
            if not change_ticks
            else quantize_float(sum(change_ticks) / len(change_ticks))
        ),
        revision_count=revisions,
        multi_referent_term_count=multi_referent_terms,
        usage_context_count=len(inputs.usages),
        channel_counts=tuple(sorted(channels.items())),
        drift_rate=drift_rate,
        availability=(
            MetricAvailability.PRESENT
            if inputs.senses or inputs.usages
            else MetricAvailability.ABSENT
        ),
        coverage=_coverage(len(owners), inputs.expected_owner_count),
    )
    _LOG.info(
        "semantic_drift_computed availability=%s transitions=%s",
        result.availability.value,
        result.transition_count,
    )
    return result


def _distributions(
    senses: Sequence[SemanticSenseRow],
    group_for: Mapping[str, str],
) -> dict[tuple[str, str], dict[str, Counter[str]]]:
    distributions: dict[tuple[str, str], dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    for row in senses:
        if row.referent_digest is None:
            continue
        group = group_for.get(row.owner_id)
        if group is None:
            continue
        distributions[(row.term_source, row.term_digest)][group][
            row.referent_digest
        ] += 1
    return distributions


def _pairwise_mean(values: Sequence[float]) -> float | None:
    return None if not values else quantize_float(sum(values) / len(values))


def _between(
    distributions: dict[tuple[str, str], dict[str, Counter[str]]],
) -> list[float]:
    values: list[float] = []
    for groups in distributions.values():
        names = sorted(groups)
        for index, left in enumerate(names):
            for right in names[index + 1 :]:
                digests = sorted(set(groups[left]) | set(groups[right]))
                divergence = jensen_shannon_divergence(
                    [groups[left][item] for item in digests],
                    [groups[right][item] for item in digests],
                )
                if divergence is not None:
                    values.append(quantize_float(divergence))
    return values


def _within(
    senses: Sequence[SemanticSenseRow],
    group_for: Mapping[str, str],
) -> list[float]:
    by_group: dict[
        tuple[str, str], dict[str, dict[str, Counter[str]]]
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))
    for row in senses:
        if row.referent_digest is None:
            continue
        group = group_for.get(row.owner_id)
        if group is None:
            continue
        by_group[(row.term_source, row.term_digest)][group][row.owner_id][
            row.referent_digest
        ] += 1
    values: list[float] = []
    for groups in by_group.values():
        for owners in groups.values():
            names = sorted(owners)
            for index, left in enumerate(names):
                for right in names[index + 1 :]:
                    digests = sorted(set(owners[left]) | set(owners[right]))
                    divergence = jensen_shannon_divergence(
                        [owners[left][item] for item in digests],
                        [owners[right][item] for item in digests],
                    )
                    if divergence is not None:
                        values.append(quantize_float(divergence))
    return values


def compute_semantic_divergence(
    inputs: SemanticAnalysisInputs,
) -> SemanticDivergenceResult:
    """Compare referent distributions across groups and generations."""
    _validate_inputs(inputs)
    community_map = _community_map(inputs.communities)
    generation_map = {
        key: str(value)
        for key, value in dict(inputs.generation_index_by_owner or {}).items()
    }
    unknown = sum(1 for row in inputs.senses if row.referent_digest is None)
    if not community_map and not generation_map:
        return SemanticDivergenceResult(
            group_count=0,
            generation_count=0,
            between_group_divergence=None,
            within_group_divergence=None,
            between_generation_divergence=None,
            within_generation_divergence=None,
            cross_generation_continuity=None,
            pairwise_divergence=None,
            unknown_referent_count=unknown,
            availability=MetricAvailability.ABSENT,
            coverage=_coverage(0, inputs.expected_owner_count),
        )
    group_dist = _distributions(inputs.senses, community_map)
    generation_dist = _distributions(inputs.senses, generation_map)
    between_groups = _between(group_dist)
    within_groups = _within(inputs.senses, community_map)
    between_generations = _between(generation_dist)
    within_generations = _within(inputs.senses, generation_map)
    continuity: float | None = None
    if generation_map:
        by_term: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
        for row in inputs.senses:
            generation = generation_map.get(row.owner_id)
            if generation is None or row.referent_digest is None:
                continue
            by_term[(row.term_source, row.term_digest)][generation] = (
                row.referent_digest
            )
        eligible = [values for values in by_term.values() if len(values) >= 2]
        if eligible:
            stable = sum(
                1
                for values in eligible
                if values[sorted(values)[0]] == values[sorted(values)[-1]]
            )
            continuity = quantize_float(stable / len(eligible))
    all_values = [
        *between_groups,
        *within_groups,
        *between_generations,
        *within_generations,
    ]
    owners = {row.owner_id for row in inputs.senses}
    result = SemanticDivergenceResult(
        group_count=len({item for item in community_map.values()}),
        generation_count=len({item for item in generation_map.values()}),
        between_group_divergence=_pairwise_mean(between_groups),
        within_group_divergence=_pairwise_mean(within_groups),
        between_generation_divergence=_pairwise_mean(between_generations),
        within_generation_divergence=_pairwise_mean(within_generations),
        cross_generation_continuity=continuity,
        pairwise_divergence=_pairwise_mean(all_values),
        unknown_referent_count=unknown,
        availability=MetricAvailability.PRESENT,
        coverage=_coverage(len(owners), inputs.expected_owner_count),
    )
    _LOG.info(
        "semantic_divergence_computed availability=%s group_count=%s "
        "generation_count=%s",
        result.availability.value,
        result.group_count,
        result.generation_count,
    )
    return result


def _document(
    *,
    family: MetricFamilyId,
    values: Mapping[str, object],
    availability: MetricAvailability,
    coverage: MetricCoverage,
    run_id: str,
    input_revision: str,
    source_kind: str,
) -> MetricDocument:
    spec = metric_specification(family)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=require_stable_id("run_id", run_id),
        input_revision=require_stable_id("input_revision", input_revision),
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind=source_kind,
            source_ids=(),
            notes_code="descriptive_semantic",
        ),
    )


def compute_semantic_stability_metric(
    result: SemanticStabilityResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if type(result) is not SemanticStabilityResult:
        raise SemanticAnalysisError("invalid_result")
    values: dict[str, object] = {
        "term_count": result.term_count,
        "observed_term_count": result.observed_term_count,
        "stable_referent_count": result.stable_referent_count,
        "stable_association_count": result.stable_association_count,
        "retained_transition_count": result.retained_transition_count,
        "transition_count": result.transition_count,
        "cross_generation_term_count": result.cross_generation_term_count,
        "cross_generation_stable_count": result.cross_generation_stable_count,
    }
    if result.transition_count:
        values["retention_rate"] = quantize_float(
            result.retained_transition_count / result.transition_count
        )
    if result.mean_sense_revision is not None:
        values["mean_sense_revision"] = result.mean_sense_revision
    if result.cross_generation_term_count:
        values["cross_generation_stability_rate"] = quantize_float(
            result.cross_generation_stable_count / result.cross_generation_term_count
        )
    return _document(
        family=MetricFamilyId.SEMANTIC_STABILITY,
        values=values,
        availability=result.availability,
        coverage=result.coverage,
        run_id=run_id,
        input_revision=input_revision,
        source_kind="semantic_stability",
    )


def compute_semantic_drift_metric(
    result: SemanticDriftResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if type(result) is not SemanticDriftResult:
        raise SemanticAnalysisError("invalid_result")
    values: dict[str, object] = {
        "transition_count": result.transition_count,
        "referent_switch_count": result.referent_switch_count,
        "association_change_count": result.association_change_count,
        "revision_count": result.revision_count,
        "multi_referent_term_count": result.multi_referent_term_count,
        "usage_context_count": result.usage_context_count,
    }
    for channel, count in result.channel_counts:
        values[f"channel_{channel}_count"] = count
    if result.drift_rate is not None:
        values["drift_rate"] = result.drift_rate
    if result.mean_jaccard_distance is not None:
        values["mean_jaccard_distance"] = result.mean_jaccard_distance
    if result.mean_ticks_between_changes is not None:
        values["mean_ticks_between_changes"] = result.mean_ticks_between_changes
    return _document(
        family=MetricFamilyId.SEMANTIC_DRIFT,
        values=values,
        availability=result.availability,
        coverage=result.coverage,
        run_id=run_id,
        input_revision=input_revision,
        source_kind="semantic_drift",
    )


def compute_semantic_divergence_metric(
    result: SemanticDivergenceResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if type(result) is not SemanticDivergenceResult:
        raise SemanticAnalysisError("invalid_result")
    values: dict[str, object] = {
        "group_count": result.group_count,
        "generation_count": result.generation_count,
        "unknown_referent_count": result.unknown_referent_count,
    }
    for name, value in (
        ("between_group_divergence", result.between_group_divergence),
        ("within_group_divergence", result.within_group_divergence),
        ("between_generation_divergence", result.between_generation_divergence),
        ("within_generation_divergence", result.within_generation_divergence),
        ("cross_generation_continuity", result.cross_generation_continuity),
        ("pairwise_divergence", result.pairwise_divergence),
    ):
        if value is not None:
            values[name] = value
    return _document(
        family=MetricFamilyId.SEMANTIC_DIVERGENCE,
        values=values,
        availability=result.availability,
        coverage=result.coverage,
        run_id=run_id,
        input_revision=input_revision,
        source_kind="semantic_divergence",
    )
