"""Researcher-only subjective label overlays. Ordinary frames do not import this."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from observer.version import OBSERVER_PROTOCOL_VERSION

_LOGGER = logging.getLogger("observer.labels")

_LABEL_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_STRENGTH_BANDS = frozenset({"candidate", "low", "mid", "high"})
_LABEL_SOURCE: Literal["agent_perspective"] = "agent_perspective"
_LAYER: Literal["subjective_labels"] = "subjective_labels"


@dataclass(frozen=True, slots=True)
class SubjectiveLabelReading:
    """One additive row: objective identity beside one agent's private label."""

    objective_id: str
    objective_display_name: str
    referent_kind: str
    label_token: str
    label_display: str
    sense_revision: int
    strength_band: str
    label_source: Literal["agent_perspective"] = _LABEL_SOURCE

    def __post_init__(self) -> None:
        if type(self.objective_id) is not str:
            raise TypeError("objective_id must be str")
        if type(self.objective_display_name) is not str:
            raise TypeError("objective_display_name must be str")
        if type(self.referent_kind) is not str or not self.referent_kind:
            raise TypeError("referent_kind must be non-empty str")
        if type(self.label_token) is not str or _LABEL_TOKEN_RE.fullmatch(
            self.label_token
        ) is None:
            raise TypeError("label_token must be a closed snake_case token")
        if type(self.label_display) is not str or not self.label_display:
            raise TypeError("label_display must be non-empty str")
        if isinstance(self.sense_revision, bool) or type(self.sense_revision) is not int:
            raise TypeError("sense_revision must be int")
        if self.sense_revision < 0:
            raise ValueError("sense_revision must be non-negative")
        if self.strength_band not in _STRENGTH_BANDS:
            raise ValueError("strength_band must be a closed band")
        if self.label_source != _LABEL_SOURCE:
            raise ValueError("label_source must be agent_perspective")


@dataclass(frozen=True, slots=True)
class SubjectiveLabelOverlay:
    """Additive perspective layer. Never mutates the objective frame."""

    agent_id: str
    readings: tuple[SubjectiveLabelReading, ...]
    layer: Literal["subjective_labels"] = _LAYER
    protocol_version: str = OBSERVER_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if type(self.agent_id) is not str or not self.agent_id:
            raise TypeError("agent_id must be non-empty str")
        if self.layer != _LAYER:
            raise ValueError("layer must be subjective_labels")
        if self.protocol_version != OBSERVER_PROTOCOL_VERSION:
            raise ValueError("unsupported_observer_protocol")
        object.__setattr__(self, "readings", tuple(self.readings))
        for reading in self.readings:
            if type(reading) is not SubjectiveLabelReading:
                raise TypeError("readings entries must be SubjectiveLabelReading")


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    if type(raw) is not str or not raw:
        raise TypeError("closed enum token must be non-empty str")
    return raw


def _label_display(token: str) -> str:
    return " ".join(part.capitalize() for part in token.split("_") if part)


def _strength_band(status: str, strength: float) -> str:
    if status == "candidate":
        return "candidate"
    if strength < 0.40:
        return "low"
    if strength < 0.70:
        return "mid"
    return "high"


def _top_candidate_id(binding: object) -> str:
    candidates = getattr(binding, "candidates", ()) or ()
    best_id = ""
    best_confidence = -1.0
    for candidate in candidates:
        entity_id = getattr(candidate, "entity_id", None)
        confidence = getattr(candidate, "confidence", None)
        if not isinstance(entity_id, str) or not entity_id:
            continue
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            continue
        score = float(confidence)
        if score > best_confidence:
            best_confidence = score
            best_id = entity_id
    return best_id


def project_subjective_label_overlay(
    agent_id: str,
    rows: Sequence[object],
    objective_display_index: Mapping[str, str] | None = None,
) -> SubjectiveLabelOverlay:
    """Project duck-typed owner bindings into an additive overlay layer."""
    if type(agent_id) is not str or not agent_id:
        raise TypeError("agent_id must be non-empty str")
    index = {} if objective_display_index is None else dict(objective_display_index)
    readings: list[SubjectiveLabelReading] = []
    for binding in rows:
        token = getattr(binding, "label_token", None)
        if type(token) is not str or _LABEL_TOKEN_RE.fullmatch(token) is None:
            continue
        kind = _enum_value(getattr(binding, "referent_kind", None))
        status = _enum_value(getattr(binding, "status", "candidate"))
        strength_raw = getattr(binding, "strength", 0.0)
        if isinstance(strength_raw, bool) or not isinstance(strength_raw, (int, float)):
            continue
        strength = float(strength_raw)
        revision = getattr(binding, "sense_revision", 0)
        if isinstance(revision, bool) or type(revision) is not int or revision < 0:
            continue
        objective_id = _top_candidate_id(binding)
        display = ""
        if objective_id:
            mapped = index.get(objective_id)
            display = mapped if isinstance(mapped, str) else ""
        readings.append(
            SubjectiveLabelReading(
                objective_id=objective_id,
                objective_display_name=display,
                referent_kind=kind,
                label_token=token,
                label_display=_label_display(token),
                sense_revision=revision,
                strength_band=_strength_band(status, strength),
            )
        )
    overlay = SubjectiveLabelOverlay(
        agent_id=agent_id,
        readings=tuple(readings),
    )
    _LOGGER.debug(
        "subjective_label_overlay_projected agent_id=%s row_count=%s",
        agent_id,
        len(overlay.readings),
    )
    return overlay


__all__ = [
    "SubjectiveLabelOverlay",
    "SubjectiveLabelReading",
    "project_subjective_label_overlay",
]
