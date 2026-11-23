"""Neutral ecological-resources checkpoint transport (codec v23)."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from simulation.ecological_resources_config import ECOLOGICAL_RESOURCES_KEY
from world.identifiers import EntityId

__all__ = [
    "EcologicalResourcesCheckpointRow",
    "EcologicalResourcesCheckpointSection",
    "checkpoint_section_from_rows",
    "decode_ecological_resources_checkpoint_section",
    "encode_ecological_resources_checkpoint_section",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.ecological_resources_checkpoint"
)
_SCHEMA: Final[str] = "ecological-resources-checkpoint-v1"


@dataclass(frozen=True, slots=True)
class EcologicalResourcesCheckpointRow:
    """One sorted managed-node damage row for checkpoint transport."""

    resource_id: EntityId
    minimum_capacity_tenths: int
    damage_tenths: int

    def __post_init__(self) -> None:
        if type(self.resource_id) is not EntityId:
            raise TypeError(
                "EcologicalResourcesCheckpointRow.resource_id must be EntityId"
            )
        if type(self.minimum_capacity_tenths) is not int or isinstance(
            self.minimum_capacity_tenths, bool
        ):
            raise ValueError("ecology_checkpoint_floor_invalid")
        if self.minimum_capacity_tenths < 1 or self.minimum_capacity_tenths > 10000:
            raise ValueError("ecology_checkpoint_floor_invalid")
        if type(self.damage_tenths) is not int or isinstance(self.damage_tenths, bool):
            raise ValueError("ecology_checkpoint_damage_invalid")
        if self.damage_tenths < 0:
            raise ValueError("ecology_checkpoint_damage_invalid")


@dataclass(frozen=True, slots=True)
class EcologicalResourcesCheckpointSection:
    """Mandatory v23 ecological_resources checkpoint sibling."""

    schema_version: str
    policy_sha256: str
    rows: tuple[EcologicalResourcesCheckpointRow, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA:
            raise ValueError("ecology_checkpoint_schema_invalid")
        if type(self.policy_sha256) is not str or len(self.policy_sha256) != 64:
            raise ValueError("ecology_checkpoint_policy_digest_invalid")
        if any(ch not in "0123456789abcdef" for ch in self.policy_sha256):
            raise ValueError("ecology_checkpoint_policy_digest_invalid")
        if isinstance(self.rows, (str, bytes)) or not isinstance(self.rows, tuple):
            raise TypeError("EcologicalResourcesCheckpointSection.rows must be a tuple")
        if not self.rows or len(self.rows) > 128:
            raise ValueError("ecology_checkpoint_rows_count")
        ids = [row.resource_id.value for row in self.rows]
        if ids != sorted(ids) or len(set(ids)) != len(ids):
            raise ValueError("ecology_checkpoint_rows_order")
        for row in self.rows:
            if type(row) is not EcologicalResourcesCheckpointRow:
                raise TypeError("ecology_checkpoint_row_type")


def checkpoint_section_from_rows(
    *,
    policy_sha256: str,
    rows: Sequence[tuple[EntityId, int, int]],
) -> EcologicalResourcesCheckpointSection:
    """Build a sorted checkpoint section from ``(id, floor, damage)`` triples."""
    built = [
        EcologicalResourcesCheckpointRow(
            resource_id=resource_id,
            minimum_capacity_tenths=floor,
            damage_tenths=damage,
        )
        for resource_id, floor, damage in rows
    ]
    ordered = tuple(sorted(built, key=lambda item: item.resource_id.value))
    section = EcologicalResourcesCheckpointSection(
        schema_version=_SCHEMA,
        policy_sha256=policy_sha256,
        rows=ordered,
    )
    _LOG.debug("ecology_checkpoint_section_ready managed_count=%s", len(ordered))
    return section


def encode_ecological_resources_checkpoint_section(
    section: EcologicalResourcesCheckpointSection,
) -> dict[str, object]:
    if type(section) is not EcologicalResourcesCheckpointSection:
        raise TypeError("section must be EcologicalResourcesCheckpointSection")
    return {
        ECOLOGICAL_RESOURCES_KEY: {
            "schema_version": section.schema_version,
            "policy_sha256": section.policy_sha256,
            "rows": [
                {
                    "resource_id": row.resource_id.value,
                    "minimum_capacity_tenths": row.minimum_capacity_tenths,
                    "damage_tenths": row.damage_tenths,
                }
                for row in section.rows
            ],
        }
    }


def decode_ecological_resources_checkpoint_section(
    value: object,
) -> EcologicalResourcesCheckpointSection:
    if not isinstance(value, Mapping):
        raise ValueError("ecology_checkpoint_invalid")
    if set(value) == {ECOLOGICAL_RESOURCES_KEY}:
        inner = value[ECOLOGICAL_RESOURCES_KEY]
    elif "schema_version" in value and "policy_sha256" in value and "rows" in value:
        inner = value
    else:
        raise ValueError("ecology_checkpoint_invalid")
    if not isinstance(inner, Mapping):
        raise ValueError("ecology_checkpoint_invalid")
    if set(inner) != {"schema_version", "policy_sha256", "rows"}:
        raise ValueError("ecology_checkpoint_invalid")
    raw_rows = inner["rows"]
    if not isinstance(raw_rows, list):
        raise ValueError("ecology_checkpoint_rows_invalid")
    rows: list[EcologicalResourcesCheckpointRow] = []
    for item in raw_rows:
        if not isinstance(item, Mapping):
            raise ValueError("ecology_checkpoint_row_invalid")
        if set(item) != {
            "resource_id",
            "minimum_capacity_tenths",
            "damage_tenths",
        }:
            raise ValueError("ecology_checkpoint_row_invalid")
        floor = item["minimum_capacity_tenths"]
        damage = item["damage_tenths"]
        if type(floor) is not int or isinstance(floor, bool):
            raise ValueError("ecology_checkpoint_floor_invalid")
        if type(damage) is not int or isinstance(damage, bool):
            raise ValueError("ecology_checkpoint_damage_invalid")
        rows.append(
            EcologicalResourcesCheckpointRow(
                resource_id=EntityId(str(item["resource_id"])),
                minimum_capacity_tenths=floor,
                damage_tenths=damage,
            )
        )
    return EcologicalResourcesCheckpointSection(
        schema_version=str(inner["schema_version"]),
        policy_sha256=str(inner["policy_sha256"]),
        rows=tuple(rows),
    )
