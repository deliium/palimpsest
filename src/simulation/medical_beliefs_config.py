"""Exact opt-in runner configuration seam for subjective medical beliefs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final

from agents.cognition.medical_beliefs import MEDICAL_BELIEFS_POLICY_ID

__all__ = [
    "MEDICAL_BELIEFS_KEY",
    "MEDICAL_BELIEFS_POLICY_ID",
    "MedicalBeliefsConfigError",
    "MedicalBeliefsSpec",
    "decode_medical_beliefs",
    "encode_medical_beliefs",
]

_LOGGER: Final[logging.Logger] = logging.getLogger(
    "simulation.medical_beliefs_config"
)

MEDICAL_BELIEFS_KEY: Final[str] = "medical_beliefs"

_SPEC_KEYS: Final[frozenset[str]] = frozenset({"policy_id"})


class MedicalBeliefsConfigError(ValueError):
    """Strict configuration failure with a stable code and JSON-like path."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{path}: {code}")


def _fail(code: str, path: str) -> MedicalBeliefsConfigError:
    _LOGGER.error(
        "medical_beliefs_config_invalid path=%s reason_code=%s",
        path,
        code,
    )
    return MedicalBeliefsConfigError(code, path)


def _require_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail("medical_beliefs_spec_invalid", path)
    return value


def _require_keys(value: dict[str, Any], keys: frozenset[str], path: str) -> None:
    if set(value) != keys:
        raise _fail("medical_beliefs_spec_invalid", path)


@dataclass(frozen=True, slots=True)
class MedicalBeliefsSpec:
    """Exact opt-in subjective medical-belief policy for one run."""

    policy_id: str

    def __post_init__(self) -> None:
        if self.policy_id != MEDICAL_BELIEFS_POLICY_ID:
            raise _fail(
                "medical_beliefs_policy_invalid",
                f"{MEDICAL_BELIEFS_KEY}.policy_id",
            )
        _LOGGER.debug(
            "medical_beliefs_configured policy_id=%s",
            self.policy_id,
        )


def encode_medical_beliefs(spec: MedicalBeliefsSpec) -> dict[str, object]:
    """Encode the exact ``medical_beliefs`` sibling object."""
    if type(spec) is not MedicalBeliefsSpec:
        raise TypeError("spec must be MedicalBeliefsSpec")
    _LOGGER.debug("medical_beliefs_encode policy_id=%s", spec.policy_id)
    return {"policy_id": spec.policy_id}


def decode_medical_beliefs(value: object) -> MedicalBeliefsSpec:
    """Decode the exact ``medical_beliefs`` sibling object."""
    path = f"$.{MEDICAL_BELIEFS_KEY}"
    record = _require_mapping(value, path)
    _require_keys(record, _SPEC_KEYS, path)
    policy_id = record["policy_id"]
    if type(policy_id) is not str:
        raise _fail("medical_beliefs_policy_invalid", f"{path}.policy_id")
    return MedicalBeliefsSpec(policy_id=policy_id)
