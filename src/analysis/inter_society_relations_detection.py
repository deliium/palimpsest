"""Detect contemporaneous ``msoc-`` society pairs and assemble ISR harvests.

Fewer than two contemporaneous candidates yields an empty pair set. Overlapping
membership is legal. Harvest reuses already-derived macro-society candidates
in-process and does not require a prior publication artifact.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Final

from analysis.inter_society_relations_contract import (
    InterSocietyRelationsError,
    ordered_society_pair,
)
from analysis.inter_society_relations_evidence import (
    InterSocietyEvidenceInputs,
    InterSocietyEvidenceRow,
    build_domain_panels,
    harvest_domain_evidence_rows,
)
from analysis.inter_society_relations_identity import mint_inter_society_pair
from analysis.inter_society_relations_layers import (
    InterSocietyLayerView,
    InterSocietyPairCandidate,
    project_inter_society_layers,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "InterSocietyMacroCandidate",
    "InterSocietyRelationsAnalysis",
    "detect_inter_society_pairs",
    "harvest_inter_society_relations",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.inter_society_relations.detection"
)


@dataclass(frozen=True, slots=True)
class InterSocietyMacroCandidate:
    """Minimal contemporaneous macro-society endpoint for pair detection."""

    society_id: str
    member_ids: tuple[str, ...]
    window_tick: int

    def __post_init__(self) -> None:
        society = require_stable_id("society_id", self.society_id)
        if not society.startswith("msoc-"):
            raise InterSocietyRelationsError("inter_society_relations_invalid_pair")
        object.__setattr__(self, "society_id", society)
        members = tuple(
            sorted(
                {require_stable_id("member_id", member) for member in self.member_ids}
            )
        )
        object.__setattr__(self, "member_ids", members)
        object.__setattr__(
            self,
            "window_tick",
            require_exact_nonneg_int("window_tick", self.window_tick),
        )


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsAnalysis:
    """Stable analysis object for MetricComputationInputs and publication."""

    window_tick: int
    pairs: tuple[InterSocietyPairCandidate, ...]
    layers: InterSocietyLayerView
    pair_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "window_tick",
            require_exact_nonneg_int("window_tick", self.window_tick),
        )
        object.__setattr__(
            self, "pair_count", require_exact_nonneg_int("pair_count", self.pair_count)
        )
        if self.pair_count != len(self.pairs):
            raise InterSocietyRelationsError(
                "inter_society_relations_analysis_invalid_input"
            )


def detect_inter_society_pairs(
    candidates: Sequence[InterSocietyMacroCandidate],
    *,
    evidence_by_pair: Mapping[tuple[str, str], InterSocietyEvidenceInputs]
    | None = None,
) -> tuple[InterSocietyPairCandidate, ...]:
    """Build ordered contemporaneous pairs; empty when fewer than two societies."""
    by_tick: dict[int, list[InterSocietyMacroCandidate]] = {}
    for candidate in candidates:
        if type(candidate) is not InterSocietyMacroCandidate:
            raise InterSocietyRelationsError(
                "inter_society_relations_analysis_invalid_input"
            )
        by_tick.setdefault(candidate.window_tick, []).append(candidate)

    evidence_map = evidence_by_pair or {}
    pairs: list[InterSocietyPairCandidate] = []
    for tick, group in sorted(by_tick.items()):
        unique: dict[str, InterSocietyMacroCandidate] = {}
        for item in group:
            unique[item.society_id] = item
        societies = sorted(unique.values(), key=lambda item: item.society_id)
        if len(societies) < 2:
            _LOG.debug(
                "inter_society_relations_detection empty_pair_inventory tick=%s "
                "candidate_count=%s",
                tick,
                len(societies),
            )
            continue
        for left, right in combinations(societies, 2):
            society_a, society_b = ordered_society_pair(
                left.society_id, right.society_id
            )
            inputs = evidence_map.get(
                (society_a, society_b), InterSocietyEvidenceInputs()
            )
            panels = build_domain_panels(inputs)
            pairs.append(
                mint_inter_society_pair(
                    society_a=society_a,
                    society_b=society_b,
                    window_tick=tick,
                    panels=panels,
                    members_a=left.member_ids,
                    members_b=right.member_ids,
                )
            )
    ordered = tuple(sorted(pairs, key=lambda pair: (pair.window_tick, pair.pair_id)))
    _LOG.debug(
        "inter_society_relations_detection candidate_ticks=%s pair_count=%s",
        len(by_tick),
        len(ordered),
    )
    return ordered


def harvest_inter_society_relations(
    candidates: Sequence[InterSocietyMacroCandidate],
    *,
    evidence_by_pair: Mapping[tuple[str, str], InterSocietyEvidenceInputs]
    | None = None,
    window_tick: int | None = None,
) -> InterSocietyRelationsAnalysis:
    """Compose evidence + detection into a stable analysis harvest object."""
    _LOG.info("inter_society_relations_harvest_start")
    pairs = detect_inter_society_pairs(candidates, evidence_by_pair=evidence_by_pair)
    evidence_map = evidence_by_pair or {}
    objective_rows: list[InterSocietyEvidenceRow] = []
    for pair in pairs:
        inputs = evidence_map.get(
            (pair.society_a, pair.society_b), InterSocietyEvidenceInputs()
        )
        objective_rows.extend(
            harvest_domain_evidence_rows(
                society_a=pair.society_a,
                society_b=pair.society_b,
                tick=pair.window_tick,
                inputs=inputs,
            )
        )
    layers = project_inter_society_layers(
        objective_rows=tuple(objective_rows),
        analytical_pairs=pairs,
    )
    tick = (
        require_exact_nonneg_int("window_tick", window_tick)
        if window_tick is not None
        else (max((pair.window_tick for pair in pairs), default=0))
    )
    analysis = InterSocietyRelationsAnalysis(
        window_tick=tick,
        pairs=pairs,
        layers=layers,
        pair_count=len(pairs),
    )
    _LOG.info(
        "inter_society_relations_harvest_finish pair_count=%s",
        analysis.pair_count,
    )
    return analysis
