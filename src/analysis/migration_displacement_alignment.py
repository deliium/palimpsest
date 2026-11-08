# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Researcher-only alignment of owner cause beliefs with analytical labels.

Alignment never reaches cognition, prompts, memory, world state, observer
semantics, or stop selectors. Missing or partial evidence is ``unresolved``,
never ``inconsistent``. This module imports no cognition, runtime, experiments,
API, persistence, or observer module.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.migration_displacement_contract import MIGRATION_ALIGNMENTS
from analysis.migration_displacement_rows import (
    NONE_TOKEN,
    MigrationAlignmentRow,
    MigrationCauseRow,
    MigrationOutcomeRow,
    MigrationWaveRow,
)

__all__ = ["MIGRATION_ALIGNMENTS", "align_migration_interpretations"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.migration_displacement.alignment"
)

_KIND_BASES: Final[dict[str, frozenset[str]]] = {
    "conflict": frozenset({"immediate_threat", "coercion", "route_denial"}),
    "resource_scarcity": frozenset({"resource_deprivation"}),
    "environmental_hazard": frozenset({"environmental_hazard"}),
}
_DISPLACEMENT_KINDS: Final[frozenset[str]] = frozenset(
    {"conflict", "resource_scarcity", "environmental_hazard"}
)
_OPPORTUNITY_KINDS: Final[frozenset[str]] = frozenset({"opportunity", "social_network"})


def _judge(
    cause: MigrationCauseRow,
    wave: MigrationWaveRow,
    settled: bool,
) -> tuple[str, str]:
    """Return ``(alignment, basis)`` for one owner cause against one wave."""
    if cause.status != "active" or cause.cause_kind == "unknown":
        return "unresolved", "cause_not_usable"
    label = wave.displacement_classification
    if label == "unknown":
        return "unresolved", "wave_unclassified"
    if wave.coverage != "complete":
        return "unresolved", "partial_coverage"
    kind = cause.cause_kind
    bases = _KIND_BASES.get(kind)
    if bases is not None and bases & set(wave.displacement_bases):
        return "consistent", "displacement_basis"
    if kind in _OPPORTUNITY_KINDS and label in {"mixed", "not_displacement_like"}:
        return "consistent", "opportunity_support"
    if kind in _OPPORTUNITY_KINDS and settled:
        return "consistent", "outcome_settled"
    if kind == "institution":
        return "consistent", "institution_support"
    if kind in _DISPLACEMENT_KINDS and label == "not_displacement_like":
        return "inconsistent", "contradicting_wave_label"
    if kind in _OPPORTUNITY_KINDS and label == "displacement_like":
        return "inconsistent", "contradicting_wave_label"
    return "unresolved", "base_mismatch"


def _combine(results: Sequence[tuple[str, str]]) -> tuple[str, str]:
    consistent = [item for item in results if item[0] == "consistent"]
    inconsistent = [item for item in results if item[0] == "inconsistent"]
    if consistent and inconsistent:
        return "unresolved", "mixed_evidence"
    if consistent:
        return min(consistent, key=lambda item: item[1])
    if inconsistent:
        return min(inconsistent, key=lambda item: item[1])
    return min(results, key=lambda item: item[1])


def align_migration_interpretations(
    causes: Sequence[MigrationCauseRow],
    waves: Sequence[MigrationWaveRow],
    outcomes: Sequence[MigrationOutcomeRow],
) -> tuple[MigrationAlignmentRow, ...]:
    """Classify each owner against each wave it took part in.

    ``consistent`` when an owner cause maps to the analytical displacement basis
    or outcome class; ``inconsistent`` only on positive contradiction;
    ``unresolved`` when evidence is missing or coverage is partial;
    ``not_applicable`` when the owner is not a wave participant.
    """
    settled_by_owner = {
        item.participant_token for item in outcomes if item.classification == "settled"
    }
    by_owner: dict[str, list[MigrationCauseRow]] = {}
    for cause in causes:
        by_owner.setdefault(cause.owner_token, []).append(cause)
    rows: dict[tuple[str, str], MigrationAlignmentRow] = {}
    wave_members: set[str] = set()
    for wave in waves:
        for owner in wave.participant_tokens:
            wave_members.add(owner)
            owner_causes = by_owner.get(owner, [])
            if owner_causes:
                alignment, basis = _combine(
                    [
                        _judge(cause, wave, owner in settled_by_owner)
                        for cause in owner_causes
                    ]
                )
            else:
                alignment, basis = "unresolved", "no_owner_cause"
            rows[(owner, wave.wave_token)] = MigrationAlignmentRow(
                owner_token=owner,
                candidate_token=wave.wave_token,
                alignment=alignment,
                basis=basis.replace("_", "-"),
            )
    for owner in by_owner:
        if owner not in wave_members:
            rows[(owner, NONE_TOKEN)] = MigrationAlignmentRow(
                owner_token=owner,
                candidate_token=NONE_TOKEN,
                alignment="not_applicable",
                basis="no-candidate",
            )
    ordered = tuple(rows[key] for key in sorted(rows))
    unresolved = sum(1 for item in ordered if item.alignment == "unresolved")
    if unresolved:
        _LOG.debug("migration_alignment_unresolved count=%s", unresolved)
    return ordered
