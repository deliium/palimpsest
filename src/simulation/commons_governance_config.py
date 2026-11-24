"""Exact opt-in runner configuration seam for voluntary commons governance."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final

from world.identifiers import EntityId

__all__ = [
    "COMMONS_GOVERNANCE_KEY",
    "COMMONS_GOVERNANCE_POLICY_ID",
    "CommonsGovernanceConfigError",
    "CommonsGovernanceSpec",
    "decode_commons_governance",
    "encode_commons_governance",
]

_LOGGER: Final[logging.Logger] = logging.getLogger(
    "simulation.commons_governance_config"
)

COMMONS_GOVERNANCE_KEY: Final[str] = "commons_governance"
COMMONS_GOVERNANCE_POLICY_ID: Final[str] = "commons-governance.v1"

_SPEC_KEYS: Final[frozenset[str]] = frozenset({"policy_id", "stock_ids"})
_MIN_STOCKS: Final[int] = 1
_MAX_STOCKS: Final[int] = 8


class CommonsGovernanceConfigError(ValueError):
    """Strict configuration failure with a stable code and JSON-like path."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{path}: {code}")


def _fail(code: str, path: str) -> CommonsGovernanceConfigError:
    _LOGGER.error(
        "commons_governance_config_invalid path=%s reason_code=%s",
        path,
        code,
    )
    return CommonsGovernanceConfigError(code, path)


def _require_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail("commons_governance_spec_invalid", path)
    return value


def _require_keys(value: dict[str, Any], keys: frozenset[str], path: str) -> None:
    if set(value) != keys:
        raise _fail("commons_governance_spec_invalid", path)


def _decode_stock_ids(raw: object, path: str) -> tuple[EntityId, ...]:
    if isinstance(raw, (str, bytes)) or not isinstance(raw, list):
        raise _fail("commons_governance_spec_invalid", path)
    if not (_MIN_STOCKS <= len(raw) <= _MAX_STOCKS):
        raise _fail("commons_governance_stock_count_invalid", path)
    decoded: list[EntityId] = []
    for index, item in enumerate(raw):
        item_path = f"{path}[{index}]"
        if type(item) is not str:
            raise _fail("commons_governance_spec_invalid", item_path)
        if item == "":
            raise _fail("commons_governance_spec_invalid", item_path)
        try:
            decoded.append(EntityId(item))
        except Exception as exc:
            raise _fail("commons_governance_spec_invalid", item_path) from exc
    values = [entity.value for entity in decoded]
    if values != sorted(values):
        raise _fail("commons_governance_stock_order_invalid", path)
    if len(set(values)) != len(values):
        raise _fail("commons_governance_stock_duplicate", path)
    return tuple(decoded)


@dataclass(frozen=True, slots=True)
class CommonsGovernanceSpec:
    """Exact opt-in commons-governance research stock selector for one run."""

    policy_id: str
    stock_ids: tuple[EntityId, ...]

    def __post_init__(self) -> None:
        if self.policy_id != COMMONS_GOVERNANCE_POLICY_ID:
            raise _fail(
                "commons_governance_policy_invalid",
                f"{COMMONS_GOVERNANCE_KEY}.policy_id",
            )
        if isinstance(self.stock_ids, (str, bytes)) or not isinstance(
            self.stock_ids, tuple
        ):
            raise TypeError("stock_ids must be a tuple of EntityId")
        if not (_MIN_STOCKS <= len(self.stock_ids) <= _MAX_STOCKS):
            raise _fail(
                "commons_governance_stock_count_invalid",
                f"{COMMONS_GOVERNANCE_KEY}.stock_ids",
            )
        decoded: list[EntityId] = []
        for stock_id in self.stock_ids:
            if type(stock_id) is not EntityId:
                raise TypeError("stock_ids must contain EntityId values")
            if stock_id.value == "":
                raise _fail(
                    "commons_governance_spec_invalid",
                    f"{COMMONS_GOVERNANCE_KEY}.stock_ids",
                )
            decoded.append(stock_id)
        values = [entity.value for entity in decoded]
        if values != sorted(values):
            raise _fail(
                "commons_governance_stock_order_invalid",
                f"{COMMONS_GOVERNANCE_KEY}.stock_ids",
            )
        if len(set(values)) != len(values):
            raise _fail(
                "commons_governance_stock_duplicate",
                f"{COMMONS_GOVERNANCE_KEY}.stock_ids",
            )
        object.__setattr__(self, "stock_ids", tuple(decoded))
        _LOGGER.debug(
            "commons_governance_configured policy_id=%s stock_count=%s",
            self.policy_id,
            len(self.stock_ids),
        )


def encode_commons_governance(spec: CommonsGovernanceSpec) -> dict[str, object]:
    """Encode the exact ``commons_governance`` sibling object."""
    if type(spec) is not CommonsGovernanceSpec:
        raise TypeError("spec must be CommonsGovernanceSpec")
    _LOGGER.debug(
        "commons_governance_encode policy_id=%s stock_count=%s",
        spec.policy_id,
        len(spec.stock_ids),
    )
    return {
        "policy_id": spec.policy_id,
        "stock_ids": [stock_id.value for stock_id in spec.stock_ids],
    }


def decode_commons_governance(value: object) -> CommonsGovernanceSpec:
    """Decode the exact ``commons_governance`` sibling object."""
    path = f"$.{COMMONS_GOVERNANCE_KEY}"
    record = _require_mapping(value, path)
    _require_keys(record, _SPEC_KEYS, path)
    policy_id = record["policy_id"]
    if type(policy_id) is not str:
        raise _fail("commons_governance_policy_invalid", f"{path}.policy_id")
    stock_ids = _decode_stock_ids(record["stock_ids"], f"{path}.stock_ids")
    return CommonsGovernanceSpec(policy_id=policy_id, stock_ids=stock_ids)
