"""Codec v24 disaster_state checkpoint transport."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from simulation.disease_config import DiseaseMechanicsSpec
from simulation.ecological_resources_checkpoint import checkpoint_section_from_rows
from simulation.persistence import SnapshotExtensions
from world._disasters import DisasterState
from world.disasters import DISASTER_RULE_ID_PATTERN, MAX_DISASTER_RULES
from world.environment import EnvironmentalDynamicsSpec
from world.identifiers import EntityId

__all__ = [
    "DISASTER_STATE_KEY",
    "DisasterStateSection",
    "build_v24_checkpoint_extensions",
    "decode_disaster_state_section",
    "encode_disaster_state_section",
    "section_from_disaster_state",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.disasters_checkpoint")
DISASTER_STATE_KEY: Final[str] = "disaster_state"
_SECTION_KEYS: Final[frozenset[str]] = frozenset(
    {"policy_sha256", "overexploitation_active", "applied_rule_ids"}
)


@dataclass(frozen=True, slots=True)
class DisasterStateSection:
    """Mandatory v24 ``disaster_state`` checkpoint sibling."""

    policy_sha256: str
    overexploitation_active: bool
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.policy_sha256) is not str or len(self.policy_sha256) != 64:
            raise ValueError("disaster_checkpoint_policy_digest_invalid")
        if any(ch not in "0123456789abcdef" for ch in self.policy_sha256):
            raise ValueError("disaster_checkpoint_policy_digest_invalid")
        if type(self.overexploitation_active) is not bool:
            raise ValueError("disaster_checkpoint_overexploitation_invalid")
        if isinstance(self.applied_rule_ids, (str, bytes)) or not isinstance(
            self.applied_rule_ids, tuple
        ):
            raise TypeError("DisasterStateSection.applied_rule_ids must be a tuple")
        if len(self.applied_rule_ids) > MAX_DISASTER_RULES:
            raise ValueError("disaster_checkpoint_applied_ids_count")
        seen: set[str] = set()
        previous = ""
        for rule_id in self.applied_rule_ids:
            if type(rule_id) is not str or not DISASTER_RULE_ID_PATTERN.fullmatch(
                rule_id
            ):
                raise ValueError("disaster_checkpoint_applied_id_invalid")
            if rule_id in seen:
                raise ValueError("disaster_checkpoint_applied_ids_duplicate")
            if previous and rule_id < previous:
                raise ValueError("disaster_checkpoint_applied_ids_order")
            seen.add(rule_id)
            previous = rule_id

    def to_disaster_state(self) -> DisasterState:
        return DisasterState(
            policy_sha256=self.policy_sha256,
            overexploitation_active=self.overexploitation_active,
            applied_rule_ids=self.applied_rule_ids,
        )


def section_from_disaster_state(state: DisasterState) -> DisasterStateSection:
    if type(state) is not DisasterState:
        raise TypeError("state must be DisasterState")
    return DisasterStateSection(
        policy_sha256=state.policy_sha256,
        overexploitation_active=state.overexploitation_active,
        applied_rule_ids=state.applied_rule_ids,
    )


def encode_disaster_state_section(section: DisasterStateSection) -> dict[str, object]:
    if type(section) is not DisasterStateSection:
        raise TypeError("section must be DisasterStateSection")
    return {
        DISASTER_STATE_KEY: {
            "policy_sha256": section.policy_sha256,
            "overexploitation_active": section.overexploitation_active,
            "applied_rule_ids": list(section.applied_rule_ids),
        }
    }


def decode_disaster_state_section(value: object) -> DisasterStateSection:
    if not isinstance(value, Mapping):
        raise ValueError("disaster_checkpoint_section_invalid")
    if set(value) != _SECTION_KEYS:
        raise ValueError("disaster_checkpoint_section_keys")
    raw_ids = value["applied_rule_ids"]
    if isinstance(raw_ids, (str, bytes)) or not isinstance(raw_ids, list):
        raise ValueError("disaster_checkpoint_applied_ids_invalid")
    policy_sha256 = value["policy_sha256"]
    overexploitation_active = value["overexploitation_active"]
    if type(policy_sha256) is not str:
        raise ValueError("disaster_checkpoint_policy_digest_invalid")
    if type(overexploitation_active) is not bool:
        raise ValueError("disaster_checkpoint_overexploitation_invalid")
    return DisasterStateSection(
        policy_sha256=policy_sha256,
        overexploitation_active=overexploitation_active,
        applied_rule_ids=tuple(raw_ids),
    )


def build_v24_checkpoint_extensions(
    *,
    state: Any,
    lifecycle_records: Sequence[object],
    kinship_edges: Sequence[object],
    dependency_need_registers: Sequence[object],
    environmental_dynamics: EnvironmentalDynamicsSpec,
    disease_spec: DiseaseMechanicsSpec | None,
    travel_network_active: bool,
    infrastructure_networks_active: bool,
    measurement_active: bool,
) -> SnapshotExtensions:
    """Build the exact v24 extension map from one committed/candidate boundary.

    Ecology damage rows, dynamics, and ``disaster_state`` are mandatory.
    Infrastructure and travel use explicit presence: omit when inactive, encode
    ``[]`` when active-empty. Measurement and disease follow their own bindings.
    """
    if type(environmental_dynamics) is not EnvironmentalDynamicsSpec:
        raise TypeError("environmental_dynamics must be EnvironmentalDynamicsSpec")
    for name, flag in (
        ("travel_network_active", travel_network_active),
        ("infrastructure_networks_active", infrastructure_networks_active),
        ("measurement_active", measurement_active),
    ):
        if type(flag) is not bool:
            raise TypeError(f"{name} must be bool")
    if state.ecological_resources is None:
        raise ValueError("v24 requires ecological_resources state rows")
    if state.ecological_policy_digest is None:
        raise ValueError("v24 requires ecological_policy_digest")
    if state.disaster_state is None:
        raise ValueError("v24 requires disaster_state")

    production_rows: SnapshotExtensions = {
        "structures": tuple(state.structures.values()),
        "production_jobs": tuple(state.production_jobs.values()),
        "tool_marks": tuple(state.tool_marks.values()),
        "active_hazards": tuple(state.active_hazards),
        "artifacts": tuple(state.artifacts.values()),
        "lifecycle_records": tuple(lifecycle_records),
        "kinship_edges": tuple(kinship_edges),
        "dependency_need_registers": tuple(dependency_need_registers),
        "repositories": tuple(state.repositories.values()),
        "corpse_custody_item_ids": tuple(
            sorted(state.corpse_custody_item_ids, key=lambda item: item.value)
        ),
        "exchange_offers": tuple(state.exchange_offers),
        "collective_projects": tuple(state.collective_projects.values()),
        "ecological_resources": checkpoint_section_from_rows(
            policy_sha256=state.ecological_policy_digest,
            rows=tuple(
                (
                    row.resource_id,
                    row.minimum_capacity_tenths,
                    row.damage_tenths,
                )
                for row in state.ecological_resources.values()
            ),
        ),
        "environmental_dynamics": environmental_dynamics,
        "disaster_state": section_from_disaster_state(state.disaster_state),
    }

    if infrastructure_networks_active:
        production_rows["infrastructure"] = (
            ()
            if state.infrastructure is None
            else tuple(
                sorted(
                    state.infrastructure.values(),
                    key=lambda asset: asset.asset_id.value,
                )
            )
        )

    if state.regions_migration is not None:
        production_rows["regions_migration"] = state.regions_migration
        production_rows["journeys"] = (
            None if state.journeys is None else tuple(state.journeys.values())
        )

    if travel_network_active:
        if not infrastructure_networks_active:
            raise ValueError("v24 travel_network requires infrastructure binding")
        production_rows["travel_network"] = tuple(state.travel_network)

    instruments = tuple(
        sorted(
            state.instrument_states.values(),
            key=lambda row: row.item_id.value,
        )
    )
    references = tuple(
        sorted(
            state.measurement_references.values(),
            key=lambda row: row.item_id.value,
        )
    )
    if measurement_active or instruments or references:
        production_rows["instrument_states"] = instruments
        production_rows["measurement_references"] = references

    if disease_spec is not None:
        from simulation.disease_checkpoint import (
            DiseaseCheckpointRow,
            DiseaseCheckpointSection,
            policy_sha256_for_spec,
        )

        disease_rows: Mapping[EntityId, Any] = state.disease_state or {}
        production_rows["disease_mechanics"] = DiseaseCheckpointSection(
            rows=tuple(
                DiseaseCheckpointRow(
                    body_id=entity_id,
                    phase=row.phase.value,
                    due_tick=row.due_tick,
                    symptomatic=row.symptomatic,
                )
                for entity_id, row in sorted(
                    disease_rows.items(), key=lambda item: item[0].value
                )
            ),
            policy_sha256=policy_sha256_for_spec(disease_spec),
        )

    _LOG.debug(
        "v24_checkpoint_extensions managed_count=%s travel=%s infrastructure=%s "
        "measurement=%s disease=%s applied_count=%s",
        len(state.ecological_resources),
        travel_network_active,
        infrastructure_networks_active,
        measurement_active or bool(instruments or references),
        disease_spec is not None,
        len(state.disaster_state.applied_rule_ids),
    )
    return production_rows
