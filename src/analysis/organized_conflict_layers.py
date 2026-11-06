# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Three separated detached layers for organized conflict."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from analysis.organized_conflict_contract import (
    CONFLICT_FORBIDDEN_RESULT_FIELDS,
    ConflictAlignment,
)

__all__ = [
    "ConflictAnalyticalRow",
    "ConflictLayerView",
    "ConflictObjectiveRow",
    "ConflictSubjectiveRow",
    "assert_conflict_layer_separation",
    "project_conflict_layers",
]

_FORBIDDEN = CONFLICT_FORBIDDEN_RESULT_FIELDS | frozenset(
    {"owner_id", "owner_token", "truth_value", "guilt"}
)


def _check_names(value: object, *, allowed: frozenset[str]) -> None:
    names = set(getattr(value, "__dataclass_fields__", {}))
    for name in names:
        if name in _FORBIDDEN and name not in allowed:
            raise ValueError(f"conflict_layer_leakage:{name}")


@dataclass(frozen=True, slots=True)
class ConflictObjectiveRow:
    """Objective counts only. No owner, no candidate id."""

    tick: int
    hostile_event_count: int = 0
    assistance_event_count: int = 0
    movement_event_count: int = 0
    capture_event_count: int = 0
    structure_event_count: int = 0
    contact_event_count: int = 0

    def __post_init__(self) -> None:
        _check_names(self, allowed=frozenset())


@dataclass(frozen=True, slots=True)
class ConflictSubjectiveRow:
    """Owner-token counts only. No analytical candidate id."""

    owner_token: str
    plan_count: int = 0
    participation_count: int = 0
    interpretation_count: int = 0
    outcome_count: int = 0

    def __post_init__(self) -> None:
        if type(self.owner_token) is not str or not self.owner_token:
            raise TypeError("ConflictSubjectiveRow.owner_token must be a token")


@dataclass(frozen=True, slots=True)
class ConflictAnalyticalRow:
    """Researcher-only analytical candidate row."""

    candidate_id: str
    classification: str
    participant_tokens: tuple[str, ...] = ()
    opponent_tokens: tuple[str, ...] = ()
    side_count: int = 0
    hostile_event_count: int = 0
    active_window_count: int = 0
    sustained: bool = False
    org_ids: tuple[str, ...] = ()
    macro_society_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id.startswith("oc-"):
            raise ValueError("conflict_layer_leakage:candidate_id")
        _check_names(self, allowed=frozenset())


@dataclass(frozen=True, slots=True)
class ConflictLayerView:
    """Projection keeping objective, subjective, and analytical rows separate."""

    objective: tuple[ConflictObjectiveRow, ...] = ()
    subjective: tuple[ConflictSubjectiveRow, ...] = ()
    analytical: tuple[ConflictAnalyticalRow, ...] = ()
    coverage: ConflictAlignment = ConflictAlignment.NOT_APPLICABLE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "objective",
            tuple(sorted(self.objective, key=lambda row: row.tick)),
        )
        object.__setattr__(
            self,
            "subjective",
            tuple(sorted(self.subjective, key=lambda row: row.owner_token)),
        )
        object.__setattr__(
            self,
            "analytical",
            tuple(sorted(self.analytical, key=lambda row: row.candidate_id)),
        )


def assert_conflict_layer_separation(view: ConflictLayerView) -> None:
    """Fail hard on owner/candidate leakage or forbidden result fields."""

    if type(view) is not ConflictLayerView:
        raise TypeError("view must be ConflictLayerView")
    for row in view.objective:
        names = set(row.__dataclass_fields__)
        if names & {"owner_token", "owner_id", "candidate_id"}:
            raise ValueError("conflict_layer_leakage:objective")
    for row in view.subjective:
        names = set(row.__dataclass_fields__)
        if "candidate_id" in names:
            raise ValueError("conflict_layer_leakage:subjective")
    for row in view.analytical:
        names = set(row.__dataclass_fields__)
        leaked = names & _FORBIDDEN
        if leaked:
            raise ValueError(f"conflict_layer_leakage:{sorted(leaked)[0]}")


def project_conflict_layers(
    rows: object,
    candidates: Sequence[object],
    alignment: Sequence[object] | None = None,
) -> ConflictLayerView:
    """Project harvested rows and detected candidates into three layers."""

    objective: dict[int, ConflictObjectiveRow] = {}
    for event in getattr(rows, "objective_events", ()) or ():
        bucket = objective.get(event.tick, ConflictObjectiveRow(tick=event.tick))
        updates = {
            "hostile_event_count": bucket.hostile_event_count
            + (
                1
                if event.event_class in {"attack", "structure_opposition", "death"}
                else 0
            ),
            "assistance_event_count": bucket.assistance_event_count
            + (1 if event.event_class == "assistance" else 0),
            "movement_event_count": bucket.movement_event_count
            + (1 if event.event_class in {"movement", "co_movement"} else 0),
            "capture_event_count": bucket.capture_event_count
            + (1 if event.event_class == "custody_capture" else 0),
            "structure_event_count": bucket.structure_event_count
            + (1 if event.event_class == "structure_opposition" else 0),
            "contact_event_count": bucket.contact_event_count
            + (1 if event.event_class == "contact" else 0),
        }
        objective[event.tick] = ConflictObjectiveRow(tick=event.tick, **updates)

    subjective: list[ConflictSubjectiveRow] = []
    for owner in getattr(rows, "owner_tokens", ()) or ():
        subjective.append(
            ConflictSubjectiveRow(
                owner_token=owner,
                plan_count=sum(
                    1
                    for row in getattr(rows, "owner_plans", ())
                    if getattr(row, "coordinator_ref", None) == owner
                ),
                participation_count=sum(
                    1
                    for row in getattr(rows, "owner_participations", ())
                    if getattr(row, "participant_ref", None) == owner
                ),
                interpretation_count=len(getattr(rows, "owner_interpretations", ())),
                outcome_count=len(getattr(rows, "owner_outcomes", ())),
            )
        )

    analytical: list[ConflictAnalyticalRow] = []
    for candidate in candidates:
        analytical.append(
            ConflictAnalyticalRow(
                candidate_id=getattr(candidate, "candidate_id", ""),
                classification=str(getattr(candidate, "classification", "")),
                participant_tokens=tuple(
                    getattr(candidate, "participant_tokens", ()) or ()
                ),
                opponent_tokens=tuple(getattr(candidate, "opponent_tokens", ()) or ()),
                side_count=int(getattr(candidate, "side_count", 0)),
                hostile_event_count=int(getattr(candidate, "hostile_event_count", 0)),
                active_window_count=int(getattr(candidate, "active_window_count", 0)),
                sustained=bool(getattr(candidate, "sustained", False)),
                org_ids=tuple(getattr(candidate, "org_ids", ()) or ()),
                macro_society_ids=tuple(
                    getattr(candidate, "macro_society_ids", ()) or ()
                ),
            )
        )

    view = ConflictLayerView(
        objective=tuple(objective.values()),
        subjective=tuple(subjective),
        analytical=tuple(analytical),
        coverage=getattr(rows, "coverage", ConflictAlignment.NOT_APPLICABLE),
    )
    assert_conflict_layer_separation(view)
    return view
