"""Three strictly separated macro-society representations.

Objective population structure is counts only. Owner-scoped subjective claims
stay owner-local. Only the analytical layer owns ``msoc-`` identities.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.macro_society_contract import (
    MacroSocietyError,
    MacroSocietyLane,
)
from analysis.macro_society_detection import MacroSocietyWindowResult
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MacroSocietyLayerView",
    "MacroSocietyObjectiveRow",
    "MacroSocietySubjectiveRow",
    "assert_layer_separation",
    "project_macro_society_layers",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.macro_society_layers")
_ANALYTICAL_PREFIX: Final[str] = "msoc-"


def _field(row: object, *names: str) -> object | None:
    for name in names:
        if isinstance(row, Mapping):
            value = row.get(name)
        else:
            value = getattr(row, name, None)
        if value is not None:
            return value
    return None


@dataclass(frozen=True, slots=True)
class MacroSocietyObjectiveRow:
    """Population counts per region and boundary; never a membership list."""

    region_id: str
    tick: int
    population_count: int
    cohort_id: str | None = None
    stage_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "region_id", require_stable_id("region_id", self.region_id)
        )
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        count = require_exact_nonneg_int("population_count", self.population_count)
        object.__setattr__(self, "population_count", count)
        for name in ("cohort_id", "stage_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_stable_id(name, value))


@dataclass(frozen=True, slots=True)
class MacroSocietySubjectiveRow:
    """One owner-local claim; never another owner's claim or a candidate id."""

    owner_id: str
    lane: MacroSocietyLane
    local_token_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "owner_id", require_stable_id("owner_id", self.owner_id)
        )
        if not isinstance(self.lane, MacroSocietyLane):
            raise MacroSocietyError("macro_society_unknown_lane")
        token = require_stable_id("local_token_id", self.local_token_id)
        if token.startswith(_ANALYTICAL_PREFIX):
            raise MacroSocietyError("macro_society_subjective_identity_leak")
        object.__setattr__(self, "local_token_id", token)


@dataclass(frozen=True, slots=True)
class MacroSocietyLayerView:
    """The three representations for one window."""

    objective_rows: tuple[MacroSocietyObjectiveRow, ...]
    subjective_rows: tuple[MacroSocietySubjectiveRow, ...]
    candidate_ids: tuple[str, ...]
    windows: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "objective_rows",
            tuple(
                sorted(
                    self.objective_rows,
                    key=lambda item: (
                        item.tick,
                        item.region_id,
                        item.cohort_id or "",
                        item.stage_id or "",
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "subjective_rows",
            tuple(
                sorted(
                    self.subjective_rows,
                    key=lambda item: (
                        item.owner_id,
                        item.lane.value,
                        item.local_token_id,
                    ),
                )
            ),
        )
        ids = tuple(sorted(set(self.candidate_ids)))
        if len(ids) != len(self.candidate_ids):
            raise MacroSocietyError("macro_society_duplicate_candidate")
        object.__setattr__(self, "candidate_ids", ids)
        object.__setattr__(self, "windows", tuple(sorted(set(self.windows))))


def _objective_row(row: object) -> MacroSocietyObjectiveRow:
    if _field(row, "macro_society_id", "candidate_id") is not None:
        raise MacroSocietyError("macro_society_objective_identity_leak")
    region = _field(row, "region_id", "location_id")
    tick = _field(row, "tick")
    count = _field(row, "population_count", "population", "count")
    if region is None or tick is None or count is None:
        raise MacroSocietyError("macro_society_invalid_objective_row")
    return MacroSocietyObjectiveRow(
        region_id=region,  # type: ignore[arg-type]
        tick=tick,  # type: ignore[arg-type]
        population_count=count,  # type: ignore[arg-type]
        cohort_id=_field(row, "cohort_id"),  # type: ignore[arg-type]
        stage_id=_field(row, "stage_id"),  # type: ignore[arg-type]
    )


def _subjective_row(row: object) -> MacroSocietySubjectiveRow:
    owner = _field(row, "owner_id", "person_id")
    lane = _field(row, "lane")
    token = _field(row, "local_token_id", "token_id", "group_id")
    if owner is None or lane is None or token is None:
        raise MacroSocietyError("macro_society_invalid_subjective_row")
    try:
        lane_value = MacroSocietyLane(lane)
    except ValueError as exc:
        raise MacroSocietyError("macro_society_unknown_lane") from exc
    return MacroSocietySubjectiveRow(
        owner_id=owner,  # type: ignore[arg-type]
        lane=lane_value,
        local_token_id=token,  # type: ignore[arg-type]
    )


def project_macro_society_layers(
    *,
    window_result: MacroSocietyWindowResult,
    objective_rows: Sequence[object] | None = None,
    subjective_rows: Sequence[object] | None = None,
) -> MacroSocietyLayerView:
    """Project detached rows into the three strictly separated layers."""
    known = frozenset(window_result.known_person_ids)
    objective = tuple(_objective_row(row) for row in objective_rows or ())
    subjective = tuple(
        row
        for row in (_subjective_row(raw) for raw in subjective_rows or ())
        if row.owner_id in known
    )
    view = MacroSocietyLayerView(
        objective_rows=objective,
        subjective_rows=subjective,
        candidate_ids=tuple(
            candidate.candidate_key for candidate in window_result.candidates
        ),
        windows=(window_result.window_index,),
    )
    assert_layer_separation(view)
    _LOG.debug(
        "macro_society_layers window=%s objective=%s subjective=%s candidates=%s",
        window_result.window_index,
        len(view.objective_rows),
        len(view.subjective_rows),
        len(view.candidate_ids),
    )
    return view


def assert_layer_separation(view: MacroSocietyLayerView) -> None:
    """Fail closed when any layer leaks another layer's identity."""
    if type(view) is not MacroSocietyLayerView:
        raise MacroSocietyError("macro_society_invalid_layer_view")
    for row in view.objective_rows:
        for value in (row.region_id, row.cohort_id, row.stage_id):
            if isinstance(value, str) and value.startswith(_ANALYTICAL_PREFIX):
                raise MacroSocietyError("macro_society_objective_identity_leak")
    candidate_ids = set(view.candidate_ids)
    for row in view.subjective_rows:
        if row.local_token_id in candidate_ids:
            raise MacroSocietyError("macro_society_subjective_identity_leak")
        if row.local_token_id.startswith(_ANALYTICAL_PREFIX):
            raise MacroSocietyError("macro_society_subjective_identity_leak")
    if len(candidate_ids) != len(view.candidate_ids):
        raise MacroSocietyError("macro_society_duplicate_candidate")
