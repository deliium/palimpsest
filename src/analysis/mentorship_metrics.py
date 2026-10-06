"""Analysis-only mentorship fidelity / mutation / bond metrics.

Families:
- ``mentorship_fidelity@1``
- ``mentorship_mutation@1``
- ``mentorship_bonds@1``

Never feed cognition; never overload ``cultural_transmission@1``.
"""

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
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from world.identifiers import require_stable_id

__all__ = [
    "MENTORSHIP_BONDS_METRIC_VERSION",
    "MENTORSHIP_FIDELITY_METRIC_VERSION",
    "MENTORSHIP_MUTATION_METRIC_VERSION",
    "compute_mentorship_bonds",
    "compute_mentorship_fidelity",
    "compute_mentorship_mutation",
]

MENTORSHIP_FIDELITY_METRIC_VERSION: Final[str] = "mentorship_fidelity@1"
MENTORSHIP_MUTATION_METRIC_VERSION: Final[str] = "mentorship_mutation@1"
MENTORSHIP_BONDS_METRIC_VERSION: Final[str] = "mentorship_bonds@1"

_LOG: Final[logging.Logger] = logging.getLogger("analysis.mentorship")
_LAYER: Final[str] = "research_analytics"


class MentorshipMetricError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        _LOG.error("mentorship_metric_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


def _document(
    spec: MetricSpecification,
    run_id: str,
    revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    *,
    notes_code: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
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
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="mentorship",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


def _audit_rows(audits: Sequence[object]) -> tuple[object, ...]:
    if isinstance(audits, (set, frozenset, Mapping, str)) or not isinstance(
        audits, Sequence
    ):
        raise MentorshipMetricError("audits_not_ordered")
    rows: list[object] = []
    for audit in audits:
        if type(audit).__name__ != "MentorshipAudit":
            raise MentorshipMetricError("invalid_audit_type")
        rows.append(audit)
    return tuple(rows)


def compute_mentorship_fidelity(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Share of non-mutated hops and mean hop depth across teaching lineages."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _audit_rows(audits)
    _LOG.info(
        "mentorship_metric_compute run_id=%s family_id=%s audit_count=%s",
        document_run,
        MetricFamilyId.MENTORSHIP_FIDELITY.value,
        len(rows),
    )
    spec = metric_specification(MetricFamilyId.MENTORSHIP_FIDELITY)
    if spec.version_identifier != MENTORSHIP_FIDELITY_METRIC_VERSION:
        raise MentorshipMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_mentorship_audits",
        )
    hop_sum = 0.0
    faithful = 0
    for row in rows:
        hop_sum += int(getattr(row, "hop_index", 0))
        if not bool(getattr(row, "mutated", False)):
            faithful += 1
    fidelity = faithful / len(rows)
    mean_hop = hop_sum / len(rows)
    max_hop = max(int(getattr(row, "hop_index", 0)) for row in rows)
    values: dict[str, object] = {
        "layer": _LAYER,
        "audit_count": len(rows),
        "faithful_share": quantize_float(fidelity),
        "mean_hop_index": quantize_float(mean_hop),
        "max_hop_index": max_hop,
    }
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(rows),
        expected=len(rows),
    )


def compute_mentorship_mutation(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Mutation rate and mean hop index of mutated taught-content rows."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _audit_rows(audits)
    _LOG.info(
        "mentorship_metric_compute run_id=%s family_id=%s audit_count=%s",
        document_run,
        MetricFamilyId.MENTORSHIP_MUTATION.value,
        len(rows),
    )
    spec = metric_specification(MetricFamilyId.MENTORSHIP_MUTATION)
    if spec.version_identifier != MENTORSHIP_MUTATION_METRIC_VERSION:
        raise MentorshipMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_mentorship_audits",
        )
    mutated_rows = [row for row in rows if bool(getattr(row, "mutated", False))]
    rate = len(mutated_rows) / len(rows)
    mean_mut_hop = (
        0.0
        if not mutated_rows
        else sum(int(getattr(row, "hop_index", 0)) for row in mutated_rows)
        / len(mutated_rows)
    )
    values = {
        "layer": _LAYER,
        "audit_count": len(rows),
        "mutated_count": len(mutated_rows),
        "mutation_rate": quantize_float(rate),
        "mean_mutated_hop_index": quantize_float(mean_mut_hop),
    }
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(rows),
        expected=len(rows),
    )


def compute_mentorship_bonds(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    ledgers: Sequence[object] | None = None,
) -> MetricDocument:
    """Bond formation / role mix from audits; optional ledger strength bands."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _audit_rows(audits)
    _LOG.info(
        "mentorship_metric_compute run_id=%s family_id=%s audit_count=%s",
        document_run,
        MetricFamilyId.MENTORSHIP_BONDS.value,
        len(rows),
    )
    spec = metric_specification(MetricFamilyId.MENTORSHIP_BONDS)
    if spec.version_identifier != MENTORSHIP_BONDS_METRIC_VERSION:
        raise MentorshipMetricError("unsupported_metric_version")
    pair_keys: set[tuple[str, str]] = set()
    role_counts: Counter[str] = Counter()
    for row in rows:
        owner = getattr(getattr(row, "owner_id", None), "value", None)
        partner = getattr(getattr(row, "partner_agent_id", None), "value", None)
        role = getattr(getattr(row, "role", None), "value", None)
        if type(owner) is str and type(partner) is str:
            pair_keys.add((owner, partner))
        if type(role) is str:
            role_counts[role] += 1
    bond_count_from_ledgers = 0
    strength_mass = 0.0
    if ledgers is not None:
        if isinstance(ledgers, (set, frozenset, Mapping, str)) or not isinstance(
            ledgers, Sequence
        ):
            raise MentorshipMetricError("ledgers_not_ordered")
        for ledger in ledgers:
            if type(ledger).__name__ != "MentorshipLedger":
                raise MentorshipMetricError("invalid_ledger_type")
            bonds = getattr(ledger, "bonds", ())
            bond_count_from_ledgers += len(bonds)
            for bond in bonds:
                strength_mass += float(getattr(bond, "strength", 0.0))
    active_bonds = bond_count_from_ledgers or len(pair_keys)
    if active_bonds == 0 and not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_mentorship_bonds",
        )
    mean_strength = (
        0.0
        if bond_count_from_ledgers == 0
        else strength_mass / bond_count_from_ledgers
    )
    values = {
        "layer": _LAYER,
        "active_bond_count": active_bonds,
        "directed_pair_count": len(pair_keys),
        "apprentice_audit_count": int(role_counts.get("apprentice", 0)),
        "mentor_audit_count": int(role_counts.get("mentor", 0)),
        "mean_bond_strength": quantize_float(mean_strength),
    }
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=max(len(rows), active_bonds),
        expected=max(len(rows), active_bonds),
    )
