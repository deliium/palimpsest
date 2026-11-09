"""Eight-domain evidence adapters for inter-society relation panels.

Adapters harvest detached counts and tokens only. Missing lanes report
availability; zeros are never invented as hostility or trust. Cultural
similarity emits only the closed Task-1 value keys.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from analysis.inter_society_relations_contract import (
    INTER_SOCIETY_DOMAIN_KEYS,
    InterSocietyAvailability,
    InterSocietyDomain,
    InterSocietyRelationsError,
    assert_no_forbidden_fields,
    ordered_society_pair,
    validate_cultural_similarity_keys,
)
from analysis.numerical import quantize_float
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "InterSocietyDomainPanel",
    "InterSocietyEvidenceInputs",
    "InterSocietyEvidenceRow",
    "build_domain_panels",
    "harvest_domain_evidence_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.inter_society_relations.evidence"
)


@dataclass(frozen=True, slots=True)
class InterSocietyEvidenceInputs:
    """Optional detached inputs for one society pair in one window.

    Each domain sequence may be absent (``None``) or empty. Empty/absent is
    ``absent`` availability — never coerced to a zero hostility or trust score.
    """

    cooperation_event_count: int | None = None
    hostility_event_count: int | None = None
    exchange_event_count: int | None = None
    migration_event_count: int | None = None
    trust_edge_count: int | None = None
    agreement_event_count: int | None = None
    conflict_event_count: int | None = None
    cultural_overlap_count: int | None = None
    cultural_union_count: int | None = None
    cultural_trait_mean_pairwise_similarity: float | None = None
    cultural_semantic_mean_pairwise_similarity: float | None = None
    cultural_naming_mean_pairwise_similarity: float | None = None
    domain_coverage: Mapping[str, str] | None = None
    unresolved_join_count: int = 0


@dataclass(frozen=True, slots=True)
class InterSocietyEvidenceRow:
    """One objective evidence token; never an ``isr-`` or relationship score."""

    domain: InterSocietyDomain
    tick: int
    event_count: int
    token: str
    coverage: InterSocietyAvailability

    def __post_init__(self) -> None:
        if not isinstance(self.domain, InterSocietyDomain):
            raise InterSocietyRelationsError("inter_society_relations_invalid_domain")
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self,
            "event_count",
            require_exact_nonneg_int("event_count", self.event_count),
        )
        object.__setattr__(self, "token", require_stable_id("token", self.token))
        if not isinstance(self.coverage, InterSocietyAvailability):
            raise InterSocietyRelationsError(
                "inter_society_relations_analysis_invalid_input"
            )
        if self.token.startswith("isr-"):
            raise InterSocietyRelationsError("inter_society_relations_layer_leak")


@dataclass(frozen=True, slots=True)
class InterSocietyDomainPanel:
    """Counts, coverage, and availability for one domain — never a strength score."""

    domain: InterSocietyDomain
    event_count: int
    availability: InterSocietyAvailability
    coverage_observed: int
    coverage_expected: int
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.domain, InterSocietyDomain):
            raise InterSocietyRelationsError("inter_society_relations_invalid_domain")
        object.__setattr__(
            self,
            "event_count",
            require_exact_nonneg_int("event_count", self.event_count),
        )
        if not isinstance(self.availability, InterSocietyAvailability):
            raise InterSocietyRelationsError(
                "inter_society_relations_analysis_invalid_input"
            )
        object.__setattr__(
            self,
            "coverage_observed",
            require_exact_nonneg_int("coverage_observed", self.coverage_observed),
        )
        object.__setattr__(
            self,
            "coverage_expected",
            require_exact_nonneg_int("coverage_expected", self.coverage_expected),
        )
        values = dict(self.values)
        assert_no_forbidden_fields(values, path=f"domain.{self.domain.value}")
        if self.domain is InterSocietyDomain.CULTURAL_SIMILARITY:
            validate_cultural_similarity_keys(values)
        object.__setattr__(self, "values", values)


def _coverage_hint(
    inputs: InterSocietyEvidenceInputs, domain: InterSocietyDomain
) -> InterSocietyAvailability | None:
    if inputs.domain_coverage is None:
        return None
    raw = inputs.domain_coverage.get(domain.value)
    if raw is None:
        return None
    try:
        return InterSocietyAvailability(raw)
    except ValueError as exc:
        raise InterSocietyRelationsError(
            "inter_society_relations_analysis_invalid_input"
        ) from exc


def _count_availability(
    count: int | None,
    *,
    hint: InterSocietyAvailability | None,
) -> tuple[int, InterSocietyAvailability, int, int]:
    if count is None:
        availability = hint or InterSocietyAvailability.ABSENT
        return 0, availability, 0, 0
    value = require_exact_nonneg_int("event_count", count)
    if hint is not None:
        availability = hint
    elif value > 0:
        availability = InterSocietyAvailability.PRESENT
    else:
        # Present-but-empty evidence is partial coverage, not invented hostility.
        availability = InterSocietyAvailability.PARTIAL
    return (
        value,
        availability,
        1 if availability is not InterSocietyAvailability.ABSENT else 0,
        1,
    )


def _cultural_panel(inputs: InterSocietyEvidenceInputs) -> InterSocietyDomainPanel:
    hint = _coverage_hint(inputs, InterSocietyDomain.CULTURAL_SIMILARITY)
    overlap = inputs.cultural_overlap_count
    union = inputs.cultural_union_count
    if overlap is None and union is None:
        availability = hint or InterSocietyAvailability.ABSENT
        values: dict[str, object] = {"availability": availability.value}
        if availability is InterSocietyAvailability.ABSENT:
            _LOG.warning(
                "inter_society_relations_domain_absent domain=cultural_similarity"
            )
        return InterSocietyDomainPanel(
            domain=InterSocietyDomain.CULTURAL_SIMILARITY,
            event_count=0,
            availability=availability,
            coverage_observed=0,
            coverage_expected=0,
            values=values,
        )
    overlap_n = require_exact_nonneg_int("cultural_overlap_count", overlap or 0)
    union_n = require_exact_nonneg_int("cultural_union_count", union or 0)
    if union_n < overlap_n:
        raise InterSocietyRelationsError(
            "inter_society_relations_analysis_invalid_input"
        )
    jaccard = quantize_float(overlap_n / union_n) if union_n > 0 else None
    values = {
        "overlap_count": overlap_n,
        "union_count": union_n,
        "jaccard": jaccard,
        "availability": (hint or InterSocietyAvailability.PRESENT).value,
    }
    if inputs.cultural_trait_mean_pairwise_similarity is not None:
        values["trait_mean_pairwise_similarity"] = quantize_float(
            float(inputs.cultural_trait_mean_pairwise_similarity)
        )
    if inputs.cultural_semantic_mean_pairwise_similarity is not None:
        values["semantic_mean_pairwise_similarity"] = quantize_float(
            float(inputs.cultural_semantic_mean_pairwise_similarity)
        )
    if inputs.cultural_naming_mean_pairwise_similarity is not None:
        values["naming_mean_pairwise_similarity"] = quantize_float(
            float(inputs.cultural_naming_mean_pairwise_similarity)
        )
    availability = hint or (
        InterSocietyAvailability.PRESENT
        if union_n > 0
        else InterSocietyAvailability.PARTIAL
    )
    values["availability"] = availability.value
    return InterSocietyDomainPanel(
        domain=InterSocietyDomain.CULTURAL_SIMILARITY,
        event_count=overlap_n,
        availability=availability,
        coverage_observed=1,
        coverage_expected=1,
        values=values,
    )


def build_domain_panels(
    inputs: InterSocietyEvidenceInputs,
) -> tuple[InterSocietyDomainPanel, ...]:
    """Build all eight domain panels from optional detached counts."""
    if type(inputs) is not InterSocietyEvidenceInputs:
        raise InterSocietyRelationsError(
            "inter_society_relations_analysis_invalid_input"
        )

    count_domains: tuple[tuple[InterSocietyDomain, int | None], ...] = (
        (InterSocietyDomain.COOPERATION, inputs.cooperation_event_count),
        (InterSocietyDomain.HOSTILITY, inputs.hostility_event_count),
        (InterSocietyDomain.EXCHANGE, inputs.exchange_event_count),
        (InterSocietyDomain.MIGRATION, inputs.migration_event_count),
        (InterSocietyDomain.TRUST_PROXY, inputs.trust_edge_count),
        (InterSocietyDomain.AGREEMENT, inputs.agreement_event_count),
        (InterSocietyDomain.CONFLICT, inputs.conflict_event_count),
    )
    panels: list[InterSocietyDomainPanel] = []
    availability_histogram: dict[str, int] = {
        InterSocietyAvailability.PRESENT.value: 0,
        InterSocietyAvailability.PARTIAL.value: 0,
        InterSocietyAvailability.ABSENT.value: 0,
    }
    for domain, count in count_domains:
        event_count, availability, observed, expected = _count_availability(
            count, hint=_coverage_hint(inputs, domain)
        )
        if availability is InterSocietyAvailability.ABSENT:
            _LOG.warning(
                "inter_society_relations_domain_absent domain=%s", domain.value
            )
        elif availability is InterSocietyAvailability.PARTIAL:
            _LOG.warning(
                "inter_society_relations_domain_partial domain=%s", domain.value
            )
        availability_histogram[availability.value] += 1
        panels.append(
            InterSocietyDomainPanel(
                domain=domain,
                event_count=event_count,
                availability=availability,
                coverage_observed=observed,
                coverage_expected=expected,
                values={
                    "event_count": event_count,
                    "availability": availability.value,
                },
            )
        )
    cultural = _cultural_panel(inputs)
    availability_histogram[cultural.availability.value] += 1
    panels.append(cultural)
    if inputs.unresolved_join_count > 0:
        _LOG.warning(
            "inter_society_relations_unresolved_joins count=%s",
            inputs.unresolved_join_count,
        )
    _LOG.debug(
        "inter_society_relations_evidence_panels domain_count=%s "
        "availability_present=%s availability_partial=%s availability_absent=%s",
        len(panels),
        availability_histogram[InterSocietyAvailability.PRESENT.value],
        availability_histogram[InterSocietyAvailability.PARTIAL.value],
        availability_histogram[InterSocietyAvailability.ABSENT.value],
    )
    assert set(panel.domain.value for panel in panels) == INTER_SOCIETY_DOMAIN_KEYS
    return tuple(sorted(panels, key=lambda panel: panel.domain.value))


def harvest_domain_evidence_rows(
    *,
    society_a: str,
    society_b: str,
    tick: int,
    inputs: InterSocietyEvidenceInputs,
) -> tuple[InterSocietyEvidenceRow, ...]:
    """Project countable domain events into objective evidence rows."""
    left, right = ordered_society_pair(society_a, society_b)
    tick_n = require_exact_nonneg_int("tick", tick)
    panels = build_domain_panels(inputs)
    rows: list[InterSocietyEvidenceRow] = []
    _ = (left, right)  # endpoints validated; tokens stay objective-only
    for panel in panels:
        if panel.availability is InterSocietyAvailability.ABSENT:
            continue
        token = require_stable_id(
            "token", f"ev-{panel.domain.value}-{tick_n}-{panel.event_count}"
        )
        rows.append(
            InterSocietyEvidenceRow(
                domain=panel.domain,
                tick=tick_n,
                event_count=panel.event_count,
                token=token,
                coverage=panel.availability,
            )
        )
    _LOG.debug(
        "inter_society_relations_evidence_rows count=%s",
        len(rows),
    )
    return tuple(sorted(rows, key=lambda row: (row.tick, row.domain.value, row.token)))
