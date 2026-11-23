"""Exact opt-in runner configuration seam for bounded ecological resources."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from world.identifiers import EntityId
from world.values import round_physical

__all__ = [
    "ECOLOGICAL_RESOURCES_KEY",
    "ECOLOGICAL_RESOURCES_POLICY_ID",
    "EcologicalResourceNodeSpec",
    "EcologicalResourcesConfigError",
    "EcologicalResourcesSpec",
    "decode_ecological_resources",
    "encode_ecological_resources",
    "policy_sha256_for_ecological_resources",
    "require_exact_tenths",
]

_LOGGER: Final[logging.Logger] = logging.getLogger(
    "simulation.ecological_resources_config"
)

ECOLOGICAL_RESOURCES_KEY: Final[str] = "ecological_resources"
ECOLOGICAL_RESOURCES_POLICY_ID: Final[str] = "ecological-resources.v1"

_SPEC_KEYS: Final[frozenset[str]] = frozenset({"policy_id", "nodes"})
_NODE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "resource_id",
        "minimum_capacity_tenths",
        "withdrawal_allowance_tenths",
        "recovery_tenths_per_idle_tick",
    }
)
_MIN_NODES: Final[int] = 1
_MAX_NODES: Final[int] = 128
_MIN_POSITIVE_TENTHS: Final[int] = 1
_MAX_TENTHS: Final[int] = 10000
_MIN_ALLOWANCE_TENTHS: Final[int] = 0


class EcologicalResourcesConfigError(ValueError):
    """Strict configuration failure with a stable code and JSON-like path."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{path}: {code}")


def _fail(code: str, path: str) -> EcologicalResourcesConfigError:
    _LOGGER.error(
        "ecological_resources_config_invalid path=%s reason_code=%s",
        path,
        code,
    )
    return EcologicalResourcesConfigError(code, path)


def _require_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail("ecological_resources_spec_invalid", path)
    return value


def _require_keys(value: dict[str, Any], keys: frozenset[str], path: str) -> None:
    if set(value) != keys:
        raise _fail("ecological_resources_spec_invalid", path)


def _require_strict_int(
    value: object,
    *,
    path: str,
    code: str,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise _fail(code, path)
    if value < minimum or value > maximum:
        raise _fail(code, path)
    return value


def require_exact_tenths(value: object, *, path: str, code: str) -> int:
    """Convert a physical quantity to tenths; reject off-grid inputs."""
    if isinstance(value, bool) or type(value) not in (int, float):
        raise _fail(code, path)
    number = float(value)  # type: ignore[arg-type]
    if not math.isfinite(number):
        raise _fail(code, path)
    rounded = round_physical(number)
    if rounded != number:
        raise _fail(code, path)
    return round(rounded * 10.0)


def _require_entity_id(value: object, path: str) -> EntityId:
    try:
        if type(value) is EntityId:
            return value
        if type(value) is str:
            return EntityId(value)
    except (TypeError, ValueError) as exc:
        raise _fail("ecological_resources_node_invalid", path) from exc
    raise _fail("ecological_resources_node_invalid", path)


@dataclass(frozen=True, slots=True)
class EcologicalResourceNodeSpec:
    """One explicitly managed renewable resource node."""

    resource_id: EntityId
    minimum_capacity_tenths: int
    withdrawal_allowance_tenths: int
    recovery_tenths_per_idle_tick: int

    def __post_init__(self) -> None:
        if type(self.resource_id) is not EntityId:
            raise TypeError("resource_id must be EntityId")
        object.__setattr__(
            self,
            "minimum_capacity_tenths",
            _require_strict_int(
                self.minimum_capacity_tenths,
                path=f"{ECOLOGICAL_RESOURCES_KEY}.nodes.minimum_capacity_tenths",
                code="ecological_resources_floor_invalid",
                minimum=_MIN_POSITIVE_TENTHS,
                maximum=_MAX_TENTHS,
            ),
        )
        object.__setattr__(
            self,
            "withdrawal_allowance_tenths",
            _require_strict_int(
                self.withdrawal_allowance_tenths,
                path=f"{ECOLOGICAL_RESOURCES_KEY}.nodes.withdrawal_allowance_tenths",
                code="ecological_resources_allowance_invalid",
                minimum=_MIN_ALLOWANCE_TENTHS,
                maximum=_MAX_TENTHS,
            ),
        )
        object.__setattr__(
            self,
            "recovery_tenths_per_idle_tick",
            _require_strict_int(
                self.recovery_tenths_per_idle_tick,
                path=(
                    f"{ECOLOGICAL_RESOURCES_KEY}.nodes."
                    "recovery_tenths_per_idle_tick"
                ),
                code="ecological_resources_recovery_invalid",
                minimum=_MIN_POSITIVE_TENTHS,
                maximum=_MAX_TENTHS,
            ),
        )


@dataclass(frozen=True, slots=True)
class EcologicalResourcesSpec:
    """Exact opt-in ecological resource policy for one run."""

    policy_id: str
    nodes: tuple[EcologicalResourceNodeSpec, ...]

    def __post_init__(self) -> None:
        if self.policy_id != ECOLOGICAL_RESOURCES_POLICY_ID:
            raise _fail(
                "ecological_resources_policy_invalid",
                f"{ECOLOGICAL_RESOURCES_KEY}.policy_id",
            )
        if isinstance(self.nodes, (str, bytes)) or not isinstance(
            self.nodes, tuple
        ):
            raise TypeError("nodes must be a tuple of EcologicalResourceNodeSpec")
        if not (_MIN_NODES <= len(self.nodes) <= _MAX_NODES):
            raise _fail(
                "ecological_resources_node_count_invalid",
                f"{ECOLOGICAL_RESOURCES_KEY}.nodes",
            )
        decoded: list[EcologicalResourceNodeSpec] = []
        for node in self.nodes:
            if type(node) is not EcologicalResourceNodeSpec:
                raise TypeError(
                    "nodes must contain EcologicalResourceNodeSpec values"
                )
            # Re-run field validation through construction.
            decoded.append(
                EcologicalResourceNodeSpec(
                    resource_id=node.resource_id,
                    minimum_capacity_tenths=node.minimum_capacity_tenths,
                    withdrawal_allowance_tenths=node.withdrawal_allowance_tenths,
                    recovery_tenths_per_idle_tick=node.recovery_tenths_per_idle_tick,
                )
            )
        ids = [node.resource_id.value for node in decoded]
        if ids != sorted(ids):
            raise _fail(
                "ecological_resources_node_order_invalid",
                f"{ECOLOGICAL_RESOURCES_KEY}.nodes",
            )
        if len(set(ids)) != len(ids):
            raise _fail(
                "ecological_resources_node_duplicate",
                f"{ECOLOGICAL_RESOURCES_KEY}.nodes",
            )
        object.__setattr__(self, "nodes", tuple(decoded))
        _LOGGER.debug(
            "ecological_resources_configured policy_id=%s managed_count=%s",
            self.policy_id,
            len(self.nodes),
        )


def encode_ecological_resources(spec: EcologicalResourcesSpec) -> dict[str, object]:
    """Encode the exact ``ecological_resources`` sibling object."""
    if type(spec) is not EcologicalResourcesSpec:
        raise TypeError("spec must be EcologicalResourcesSpec")
    nodes = [
        {
            "resource_id": node.resource_id.value,
            "minimum_capacity_tenths": node.minimum_capacity_tenths,
            "withdrawal_allowance_tenths": node.withdrawal_allowance_tenths,
            "recovery_tenths_per_idle_tick": node.recovery_tenths_per_idle_tick,
        }
        for node in spec.nodes
    ]
    _LOGGER.debug(
        "ecological_resources_encode managed_count=%s",
        len(spec.nodes),
    )
    return {
        "policy_id": spec.policy_id,
        "nodes": nodes,
    }


def decode_ecological_resources(value: object) -> EcologicalResourcesSpec:
    """Decode the exact ``ecological_resources`` sibling object."""
    path = f"$.{ECOLOGICAL_RESOURCES_KEY}"
    record = _require_mapping(value, path)
    _require_keys(record, _SPEC_KEYS, path)
    policy_id = record["policy_id"]
    if type(policy_id) is not str:
        raise _fail("ecological_resources_policy_invalid", f"{path}.policy_id")
    raw_nodes = record["nodes"]
    if isinstance(raw_nodes, (str, bytes)) or not isinstance(raw_nodes, list):
        raise _fail("ecological_resources_spec_invalid", f"{path}.nodes")
    nodes: list[EcologicalResourceNodeSpec] = []
    for index, raw in enumerate(raw_nodes):
        node_path = f"{path}.nodes[{index}]"
        node_record = _require_mapping(raw, node_path)
        _require_keys(node_record, _NODE_KEYS, node_path)
        nodes.append(
            EcologicalResourceNodeSpec(
                resource_id=_require_entity_id(
                    node_record["resource_id"],
                    f"{node_path}.resource_id",
                ),
                minimum_capacity_tenths=_require_strict_int(
                    node_record["minimum_capacity_tenths"],
                    path=f"{node_path}.minimum_capacity_tenths",
                    code="ecological_resources_floor_invalid",
                    minimum=_MIN_POSITIVE_TENTHS,
                    maximum=_MAX_TENTHS,
                ),
                withdrawal_allowance_tenths=_require_strict_int(
                    node_record["withdrawal_allowance_tenths"],
                    path=f"{node_path}.withdrawal_allowance_tenths",
                    code="ecological_resources_allowance_invalid",
                    minimum=_MIN_ALLOWANCE_TENTHS,
                    maximum=_MAX_TENTHS,
                ),
                recovery_tenths_per_idle_tick=_require_strict_int(
                    node_record["recovery_tenths_per_idle_tick"],
                    path=f"{node_path}.recovery_tenths_per_idle_tick",
                    code="ecological_resources_recovery_invalid",
                    minimum=_MIN_POSITIVE_TENTHS,
                    maximum=_MAX_TENTHS,
                ),
            )
        )
    return EcologicalResourcesSpec(policy_id=policy_id, nodes=tuple(nodes))


def policy_sha256_for_ecological_resources(spec: EcologicalResourcesSpec) -> str:
    """Hash the exact canonical ecological_resources encoding."""
    if type(spec) is not EcologicalResourcesSpec:
        raise TypeError("spec must be EcologicalResourcesSpec")
    payload = encode_ecological_resources(spec)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    digest = hashlib.sha256(canonical).hexdigest()
    _LOGGER.debug(
        "ecological_resources_policy_digest_ready managed_count=%s",
        len(spec.nodes),
    )
    return digest


def node_parameter_mapping(
    spec: EcologicalResourcesSpec,
) -> Mapping[EntityId, tuple[int, int]]:
    """Read-only mapping of resource_id → (allowance_tenths, recovery_tenths)."""
    if type(spec) is not EcologicalResourcesSpec:
        raise TypeError("spec must be EcologicalResourcesSpec")
    return {
        node.resource_id: (
            node.withdrawal_allowance_tenths,
            node.recovery_tenths_per_idle_tick,
        )
        for node in spec.nodes
    }
