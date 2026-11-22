"""Exact opt-in runner configuration seam for abstract disease mechanics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final

from world.identifiers import EntityId

__all__ = [
    "DISEASE_MECHANICS_KEY",
    "DISEASE_POLICY_ID",
    "DiseaseConfigError",
    "DiseaseMechanicsSpec",
    "decode_disease_mechanics",
    "encode_disease_mechanics",
]

_LOGGER: Final[logging.Logger] = logging.getLogger("simulation.disease_config")

DISEASE_MECHANICS_KEY: Final[str] = "disease_mechanics"
DISEASE_POLICY_ID: Final[str] = "disease-mechanics.v1"

_SPEC_KEYS: Final[frozenset[str]] = frozenset(
    {
        "policy_id",
        "initial_latent_entity_ids",
        "exposure_chance_milli",
        "transmission_chance_milli",
        "symptom_chance_milli",
        "mortality_chance_milli",
        "latent_ticks",
        "active_ticks",
        "immunity_after_recovery",
    }
)
_CHANCE_FIELDS: Final[tuple[str, ...]] = (
    "exposure_chance_milli",
    "transmission_chance_milli",
    "symptom_chance_milli",
    "mortality_chance_milli",
)
_TICK_FIELDS: Final[tuple[str, ...]] = ("latent_ticks", "active_ticks")
_MAX_CHANCE_MILLI: Final[int] = 1000
_MIN_PHASE_TICKS: Final[int] = 1
_MAX_PHASE_TICKS: Final[int] = 1024


class DiseaseConfigError(ValueError):
    """Strict configuration failure with a stable code and JSON-like path."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{path}: {code}")


def _fail(code: str, path: str) -> DiseaseConfigError:
    _LOGGER.error(
        "disease_config_invalid path=%s reason_code=%s",
        path,
        code,
    )
    return DiseaseConfigError(code, path)


def _require_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail("disease_spec_invalid", path)
    return value


def _require_keys(value: dict[str, Any], keys: frozenset[str], path: str) -> None:
    if set(value) != keys:
        raise _fail("disease_spec_invalid", path)


def _require_milli(value: object, path: str) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise _fail("disease_chance_invalid", path)
    if value < 0 or value > _MAX_CHANCE_MILLI:
        raise _fail("disease_chance_invalid", path)
    return value


def _require_phase_ticks(value: object, path: str) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise _fail("disease_ticks_invalid", path)
    if value < _MIN_PHASE_TICKS or value > _MAX_PHASE_TICKS:
        raise _fail("disease_ticks_invalid", path)
    return value


def _require_entity_ids(value: object, path: str) -> tuple[EntityId, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
        value, (tuple, list)
    ):
        raise _fail("disease_founder_invalid", path)
    decoded: list[EntityId] = []
    raw_values: list[str] = []
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        try:
            if type(item) is EntityId:
                entity_id = item
            elif type(item) is str:
                entity_id = EntityId(item)
            else:
                raise _fail("disease_founder_invalid", item_path)
        except DiseaseConfigError:
            raise
        except (TypeError, ValueError) as exc:
            raise _fail("disease_founder_invalid", item_path) from exc
        decoded.append(entity_id)
        raw_values.append(entity_id.value)
    if raw_values != sorted(raw_values):
        raise _fail("disease_founder_invalid", path)
    if len(set(raw_values)) != len(raw_values):
        raise _fail("disease_founder_invalid", path)
    return tuple(decoded)


@dataclass(frozen=True, slots=True)
class DiseaseMechanicsSpec:
    """Exact opt-in disease channel parameters for one fictional condition."""

    policy_id: str
    initial_latent_entity_ids: tuple[EntityId, ...]
    exposure_chance_milli: int
    transmission_chance_milli: int
    symptom_chance_milli: int
    mortality_chance_milli: int
    latent_ticks: int
    active_ticks: int
    immunity_after_recovery: bool

    def __post_init__(self) -> None:
        if self.policy_id != DISEASE_POLICY_ID:
            raise _fail(
                "disease_policy_unsupported",
                f"{DISEASE_MECHANICS_KEY}.policy_id",
            )
        founders = _require_entity_ids(
            self.initial_latent_entity_ids,
            f"{DISEASE_MECHANICS_KEY}.initial_latent_entity_ids",
        )
        object.__setattr__(self, "initial_latent_entity_ids", founders)
        for field_name in _CHANCE_FIELDS:
            object.__setattr__(
                self,
                field_name,
                _require_milli(
                    getattr(self, field_name),
                    f"{DISEASE_MECHANICS_KEY}.{field_name}",
                ),
            )
        for field_name in _TICK_FIELDS:
            object.__setattr__(
                self,
                field_name,
                _require_phase_ticks(
                    getattr(self, field_name),
                    f"{DISEASE_MECHANICS_KEY}.{field_name}",
                ),
            )
        if type(self.immunity_after_recovery) is not bool:
            raise _fail(
                "disease_immunity_invalid",
                f"{DISEASE_MECHANICS_KEY}.immunity_after_recovery",
            )
        _LOGGER.info(
            "disease_mechanics_configured policy_id=%s founder_count=%s "
            "latent_ticks=%s active_ticks=%s immunity_after_recovery=%s",
            self.policy_id,
            len(self.initial_latent_entity_ids),
            self.latent_ticks,
            self.active_ticks,
            self.immunity_after_recovery,
        )
        _LOGGER.debug(
            "disease_mechanics_chances exposure_milli=%s transmission_milli=%s "
            "symptom_milli=%s mortality_milli=%s",
            self.exposure_chance_milli,
            self.transmission_chance_milli,
            self.symptom_chance_milli,
            self.mortality_chance_milli,
        )


def encode_disease_mechanics(spec: DiseaseMechanicsSpec) -> dict[str, object]:
    """Encode the exact ``disease_mechanics`` sibling object."""
    if type(spec) is not DiseaseMechanicsSpec:
        raise TypeError("spec must be DiseaseMechanicsSpec")
    _LOGGER.debug(
        "disease_mechanics_encode founder_count=%s",
        len(spec.initial_latent_entity_ids),
    )
    return {
        "policy_id": spec.policy_id,
        "initial_latent_entity_ids": [
            entity_id.value for entity_id in spec.initial_latent_entity_ids
        ],
        "exposure_chance_milli": spec.exposure_chance_milli,
        "transmission_chance_milli": spec.transmission_chance_milli,
        "symptom_chance_milli": spec.symptom_chance_milli,
        "mortality_chance_milli": spec.mortality_chance_milli,
        "latent_ticks": spec.latent_ticks,
        "active_ticks": spec.active_ticks,
        "immunity_after_recovery": spec.immunity_after_recovery,
    }


def decode_disease_mechanics(value: object) -> DiseaseMechanicsSpec:
    """Decode the exact ``disease_mechanics`` sibling object."""
    path = f"$.{DISEASE_MECHANICS_KEY}"
    record = _require_mapping(value, path)
    _require_keys(record, _SPEC_KEYS, path)
    policy_id = record["policy_id"]
    if type(policy_id) is not str:
        raise _fail("disease_policy_unsupported", f"{path}.policy_id")
    try:
        return DiseaseMechanicsSpec(
            policy_id=policy_id,
            initial_latent_entity_ids=_require_entity_ids(
                record["initial_latent_entity_ids"],
                f"{path}.initial_latent_entity_ids",
            ),
            exposure_chance_milli=_require_milli(
                record["exposure_chance_milli"],
                f"{path}.exposure_chance_milli",
            ),
            transmission_chance_milli=_require_milli(
                record["transmission_chance_milli"],
                f"{path}.transmission_chance_milli",
            ),
            symptom_chance_milli=_require_milli(
                record["symptom_chance_milli"],
                f"{path}.symptom_chance_milli",
            ),
            mortality_chance_milli=_require_milli(
                record["mortality_chance_milli"],
                f"{path}.mortality_chance_milli",
            ),
            latent_ticks=_require_phase_ticks(
                record["latent_ticks"],
                f"{path}.latent_ticks",
            ),
            active_ticks=_require_phase_ticks(
                record["active_ticks"],
                f"{path}.active_ticks",
            ),
            immunity_after_recovery=record["immunity_after_recovery"],
        )
    except DiseaseConfigError:
        raise
    except (TypeError, ValueError) as exc:
        raise _fail("disease_spec_invalid", path) from exc
