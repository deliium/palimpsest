"""Three strictly separated inter-society relation representations.

Objective evidence rows are counts/tokens only. Analytical pairs own ``isr-``
ids. Comparison views never leak pair identities into objective rows.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.inter_society_relations_contract import (
    INTER_SOCIETY_RELATIONS_ID_PREFIX,
    InterSocietyAvailability,
    InterSocietyDomain,
    InterSocietyLayer,
    InterSocietyRelationsError,
    require_inter_society_pair_id,
)
from analysis.inter_society_relations_evidence import (
    InterSocietyDomainPanel,
    InterSocietyEvidenceRow,
)
from world.identifiers import require_exact_nonneg_int

__all__ = [
    "InterSocietyComparisonView",
    "InterSocietyLayerView",
    "InterSocietyPairCandidate",
    "assert_layer_separation",
    "project_inter_society_layers",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.inter_society_relations.layers"
)
_ANALYTICAL_PREFIX: Final[str] = INTER_SOCIETY_RELATIONS_ID_PREFIX


@dataclass(frozen=True, slots=True)
class InterSocietyPairCandidate:
    """Analytical society-pair candidate; researcher label only."""

    pair_id: str
    society_a: str
    society_b: str
    window_tick: int
    status: str
    overlap_member_count: int
    panels: tuple[InterSocietyDomainPanel, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "pair_id", require_inter_society_pair_id(self.pair_id))
        object.__setattr__(
            self,
            "window_tick",
            require_exact_nonneg_int("window_tick", self.window_tick),
        )
        object.__setattr__(
            self,
            "overlap_member_count",
            require_exact_nonneg_int("overlap_member_count", self.overlap_member_count),
        )
        if not self.society_a.startswith("msoc-") or not self.society_b.startswith(
            "msoc-"
        ):
            raise InterSocietyRelationsError("inter_society_relations_invalid_pair")
        if self.society_a >= self.society_b:
            raise InterSocietyRelationsError("inter_society_relations_invalid_pair")
        domains = tuple(panel.domain for panel in self.panels)
        if len(set(domains)) != len(domains):
            raise InterSocietyRelationsError("inter_society_relations_duplicate_pair")


@dataclass(frozen=True, slots=True)
class InterSocietyComparisonView:
    """Per-domain deltas between two pairs or two windows — never a rank."""

    left_pair_id: str
    right_pair_id: str
    left_window_tick: int
    right_window_tick: int
    domain_deltas: tuple[tuple[str, int, str, str], ...]
    # (domain, count_delta, left_availability, right_availability)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "left_pair_id", require_inter_society_pair_id(self.left_pair_id)
        )
        object.__setattr__(
            self, "right_pair_id", require_inter_society_pair_id(self.right_pair_id)
        )
        object.__setattr__(
            self,
            "left_window_tick",
            require_exact_nonneg_int("left_window_tick", self.left_window_tick),
        )
        object.__setattr__(
            self,
            "right_window_tick",
            require_exact_nonneg_int("right_window_tick", self.right_window_tick),
        )


@dataclass(frozen=True, slots=True)
class InterSocietyLayerView:
    """The three representations for one harvest window."""

    objective_rows: tuple[InterSocietyEvidenceRow, ...]
    analytical_pairs: tuple[InterSocietyPairCandidate, ...]
    comparison_views: tuple[InterSocietyComparisonView, ...]
    layer: InterSocietyLayer = InterSocietyLayer.ANALYTICAL_PAIR

    def __post_init__(self) -> None:
        pair_ids = tuple(pair.pair_id for pair in self.analytical_pairs)
        if len(set(pair_ids)) != len(pair_ids):
            raise InterSocietyRelationsError("inter_society_relations_duplicate_pair")
        object.__setattr__(
            self,
            "analytical_pairs",
            tuple(sorted(self.analytical_pairs, key=lambda item: item.pair_id)),
        )
        object.__setattr__(
            self,
            "objective_rows",
            tuple(
                sorted(
                    self.objective_rows,
                    key=lambda item: (item.tick, item.domain.value, item.token),
                )
            ),
        )


def project_inter_society_layers(
    *,
    objective_rows: Sequence[InterSocietyEvidenceRow],
    analytical_pairs: Sequence[InterSocietyPairCandidate],
    comparison_views: Sequence[InterSocietyComparisonView] = (),
) -> InterSocietyLayerView:
    """Project rows into the three strictly separated layers."""
    view = InterSocietyLayerView(
        objective_rows=tuple(objective_rows),
        analytical_pairs=tuple(analytical_pairs),
        comparison_views=tuple(comparison_views),
    )
    assert_layer_separation(view)
    _LOG.debug(
        "inter_society_relations_layers objective=%s pairs=%s comparisons=%s",
        len(view.objective_rows),
        len(view.analytical_pairs),
        len(view.comparison_views),
    )
    return view


def assert_layer_separation(view: InterSocietyLayerView) -> None:
    """Fail closed when any layer leaks another layer's identity."""
    if type(view) is not InterSocietyLayerView:
        _LOG.error(
            "inter_society_relations_layer_leak "
            "reason_code=inter_society_relations_invalid_layer_view"
        )
        raise InterSocietyRelationsError("inter_society_relations_invalid_layer_view")
    pair_ids = {pair.pair_id for pair in view.analytical_pairs}
    for row in view.objective_rows:
        if row.token in pair_ids or row.token.startswith(_ANALYTICAL_PREFIX):
            _LOG.error(
                "inter_society_relations_layer_leak "
                "reason_code=inter_society_relations_layer_leak"
            )
            raise InterSocietyRelationsError("inter_society_relations_layer_leak")
        if not isinstance(row.domain, InterSocietyDomain):
            raise InterSocietyRelationsError("inter_society_relations_invalid_domain")
        if not isinstance(row.coverage, InterSocietyAvailability):
            raise InterSocietyRelationsError(
                "inter_society_relations_analysis_invalid_input"
            )
    for comparison in view.comparison_views:
        for field in (comparison.left_pair_id, comparison.right_pair_id):
            if not field.startswith(_ANALYTICAL_PREFIX):
                _LOG.error(
                    "inter_society_relations_layer_leak "
                    "reason_code=inter_society_relations_layer_leak"
                )
                raise InterSocietyRelationsError("inter_society_relations_layer_leak")
