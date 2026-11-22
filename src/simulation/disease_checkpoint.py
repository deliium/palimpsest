"""Neutral disease checkpoint transport (codec v22). Detached from world._disease."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from simulation.disease_config import (
    DISEASE_MECHANICS_KEY,
    DiseaseMechanicsSpec,
    encode_disease_mechanics,
)
from world.identifiers import EntityId

__all__ = [
    "DiseaseCheckpointRow",
    "DiseaseCheckpointSection",
    "decode_disease_checkpoint_section",
    "encode_disease_checkpoint_section",
    "policy_sha256_for_spec",
    "row_from_view",
    "row_to_view",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.disease_checkpoint")
_PHASES: Final[frozenset[str]] = frozenset({"latent", "active", "immune"})


@dataclass(frozen=True, slots=True)
class DiseaseCheckpointRow:
    """One sorted checkpoint disease row; no private module types."""

    body_id: EntityId
    phase: Literal["latent", "active", "immune"]
    due_tick: int | None = None
    symptomatic: bool | None = None

    def __post_init__(self) -> None:
        if type(self.body_id) is not EntityId:
            raise TypeError("DiseaseCheckpointRow.body_id must be EntityId")
        if self.phase not in _PHASES:
            raise ValueError("disease_checkpoint_row_phase_invalid")
        if self.phase == "immune":
            if self.due_tick is not None or self.symptomatic is not None:
                raise ValueError("disease_checkpoint_row_immune_shape")
            return
        if type(self.due_tick) is not int or isinstance(self.due_tick, bool):
            raise ValueError("disease_checkpoint_row_due_invalid")
        if self.due_tick < 0:
            raise ValueError("disease_checkpoint_row_due_invalid")
        if self.phase == "latent":
            if self.symptomatic is not None:
                raise ValueError("disease_checkpoint_row_latent_symptom")
            return
        if type(self.symptomatic) is not bool:
            raise ValueError("disease_checkpoint_row_active_symptom")


@dataclass(frozen=True, slots=True)
class DiseaseCheckpointSection:
    """Mandatory v22 disease_mechanics checkpoint sibling."""

    rows: tuple[DiseaseCheckpointRow, ...]
    policy_sha256: str

    def __post_init__(self) -> None:
        if isinstance(self.rows, (str, bytes)) or not isinstance(self.rows, tuple):
            raise TypeError("DiseaseCheckpointSection.rows must be a tuple")
        ids = [row.body_id.value for row in self.rows]
        if ids != sorted(ids) or len(set(ids)) != len(ids):
            raise ValueError("disease_checkpoint_rows_order")
        if type(self.policy_sha256) is not str or len(self.policy_sha256) != 64:
            raise ValueError("disease_checkpoint_policy_digest_invalid")
        if any(ch not in "0123456789abcdef" for ch in self.policy_sha256):
            raise ValueError("disease_checkpoint_policy_digest_invalid")


def policy_sha256_for_spec(spec: DiseaseMechanicsSpec) -> str:
    """Hash the exact canonical disease_mechanics encoding."""
    if type(spec) is not DiseaseMechanicsSpec:
        raise TypeError("spec must be DiseaseMechanicsSpec")
    payload = encode_disease_mechanics(spec)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    digest = hashlib.sha256(canonical).hexdigest()
    _LOG.debug(
        "disease_policy_digest_ready founder_count=%s",
        len(spec.initial_latent_entity_ids),
    )
    return digest


def encode_disease_checkpoint_section(
    section: DiseaseCheckpointSection,
) -> dict[str, object]:
    if type(section) is not DiseaseCheckpointSection:
        raise TypeError("section must be DiseaseCheckpointSection")
    rows: list[dict[str, object]] = []
    for row in section.rows:
        item: dict[str, object] = {
            "body_id": row.body_id.value,
            "phase": row.phase,
        }
        if row.due_tick is not None:
            item["due_tick"] = row.due_tick
        if row.symptomatic is not None:
            item["symptomatic"] = row.symptomatic
        rows.append(item)
    return {
        DISEASE_MECHANICS_KEY: {
            "rows": rows,
            "policy_sha256": section.policy_sha256,
        }
    }


def decode_disease_checkpoint_section(value: object) -> DiseaseCheckpointSection:
    if not isinstance(value, Mapping):
        raise ValueError("disease_checkpoint_section_invalid")
    if set(value) != {DISEASE_MECHANICS_KEY}:
        # Accept either the wrapper or the inner object for codec callers.
        if "rows" in value and "policy_sha256" in value and set(value) <= {
            "rows",
            "policy_sha256",
        }:
            inner = value
        else:
            raise ValueError("disease_checkpoint_section_invalid")
    else:
        inner = value[DISEASE_MECHANICS_KEY]
    if not isinstance(inner, Mapping):
        raise ValueError("disease_checkpoint_section_invalid")
    if set(inner) != {"rows", "policy_sha256"}:
        raise ValueError("disease_checkpoint_section_invalid")
    raw_rows = inner["rows"]
    if not isinstance(raw_rows, list):
        raise ValueError("disease_checkpoint_rows_invalid")
    rows: list[DiseaseCheckpointRow] = []
    for index, item in enumerate(raw_rows):
        if not isinstance(item, Mapping):
            raise ValueError("disease_checkpoint_row_invalid")
        allowed = {"body_id", "phase", "due_tick", "symptomatic"}
        if "body_id" not in item or "phase" not in item or not set(item) <= allowed:
            raise ValueError("disease_checkpoint_row_invalid")
        rows.append(
            DiseaseCheckpointRow(
                body_id=EntityId(str(item["body_id"])),
                phase=item["phase"],  # type: ignore[arg-type]
                due_tick=item.get("due_tick"),
                symptomatic=item.get("symptomatic"),
            )
        )
    return DiseaseCheckpointSection(
        rows=tuple(rows),
        policy_sha256=str(inner["policy_sha256"]),
    )


def row_to_view(row: DiseaseCheckpointRow | None) -> object | None:
    if row is None:
        return None
    from world.events import DiseaseRowView

    return DiseaseRowView(
        phase=row.phase,
        due_tick=row.due_tick,
        symptomatic=row.symptomatic,
    )


def row_from_view(view: object | None) -> DiseaseCheckpointRow | None:
    if view is None:
        return None
    from world.events import DiseaseRowView

    if type(view) is not DiseaseRowView:
        raise TypeError("view must be DiseaseRowView or None")
    # body_id is supplied by the enclosing effect; this helper is shape-only.
    raise TypeError("row_from_view requires body_id; use DiseaseCheckpointRow directly")


def checkpoint_rows_from_views(
    rows: Sequence[tuple[EntityId, Literal["latent", "active", "immune"], int | None, bool | None]],
) -> tuple[DiseaseCheckpointRow, ...]:
    """Build sorted checkpoint rows from detached tuples (engine-owned)."""
    built = [
        DiseaseCheckpointRow(
            body_id=body_id,
            phase=phase,
            due_tick=due_tick,
            symptomatic=symptomatic,
        )
        for body_id, phase, due_tick, symptomatic in rows
    ]
    return tuple(sorted(built, key=lambda item: item.body_id.value))
