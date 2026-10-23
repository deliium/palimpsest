"""Strict canonical JSON codec for the path-dependence experiment recipe.

Documents are exact-key-set, duplicate-aware and bounded. Payloads are research
artifacts only; operational logs never receive command descriptors or digests.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from typing import Any, Final

from agents.models import AgentId
from experiments.path_dependence_models import (
    MAX_SPEC_DOCUMENT_BYTES,
    MAX_SPEC_DOCUMENT_DEPTH,
    PATH_DEPENDENCE_CAPTURE_POLICY,
    PATH_DEPENDENCE_EXPERIMENT_ID,
    PATH_DEPENDENCE_SPEC_SCHEMA_VERSION,
    ArmRole,
    CommonSetupCommand,
    ForkTickSchedule,
    GiveInterventionAction,
    OutcomeDomain,
    OutcomeSelector,
    OutcomeWindow,
    PathDependenceArm,
    PathDependenceSpec,
    PathDependenceValidationError,
    ProtocolContrast,
    ScheduledCommandIntervention,
    WaitInterventionAction,
)
from simulation.clock import Tick
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from world.actions import (
    AgentCommand,
    Drink,
    Eat,
    Give,
    Move,
    Sleep,
    Take,
    Wait,
)
from world.identifiers import EntityId

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.path_dependence_serialization"
)


class PathDependenceSerializationError(PathDependenceValidationError):
    """Strict codec failure with a stable reason code and JSON path."""

    def __init__(self, code: str, path: str) -> None:
        self.path = path
        super().__init__(code, f"{code}:{path}")


def _canonical_dumps(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PathDependenceSerializationError("duplicate_key", "$")
        result[key] = value
    return result


def _require_keys(data: Mapping[str, Any], required: set[str], *, path: str) -> None:
    keys = set(data)
    if required - keys:
        raise PathDependenceSerializationError("missing_field", path)
    if keys - required:
        raise PathDependenceSerializationError("invalid_fields", path)


def _require_depth(value: object, *, path: str, depth: int = 1) -> None:
    if depth > MAX_SPEC_DOCUMENT_DEPTH:
        raise PathDependenceSerializationError("document_too_deep", path)
    if isinstance(value, Mapping):
        for key, entry in value.items():
            if not isinstance(key, str):
                raise PathDependenceSerializationError("invalid_key", path)
            _require_depth(entry, path=f"{path}.{key}", depth=depth + 1)
    elif isinstance(value, list):
        for index, entry in enumerate(value):
            _require_depth(entry, path=f"{path}[{index}]", depth=depth + 1)


def _str(data: Mapping[str, Any], key: str, *, path: str) -> str:
    value = data[key]
    if type(value) is not str:
        raise PathDependenceSerializationError("invalid_string", f"{path}.{key}")
    return value


def _int(data: Mapping[str, Any], key: str, *, path: str) -> int:
    value = data[key]
    if isinstance(value, bool) or type(value) is not int:
        raise PathDependenceSerializationError("invalid_int", f"{path}.{key}")
    return value


def _list(data: Mapping[str, Any], key: str, *, path: str) -> list[Any]:
    value = data[key]
    if not isinstance(value, list):
        raise PathDependenceSerializationError("invalid_collection", f"{path}.{key}")
    return value


def _object(value: object, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PathDependenceSerializationError("invalid_object", path)
    return value


def _encode_command(command: AgentCommand) -> dict[str, object]:
    if isinstance(command, Move):
        return {"kind": "move", "destination_id": command.destination_id.value}
    if isinstance(command, Take):
        return {"kind": "take", "item_id": command.item_id.value}
    if isinstance(command, Eat):
        return {"kind": "eat", "item_id": command.item_id.value}
    if isinstance(command, Drink):
        return {"kind": "drink", "source_id": command.source_id.value}
    if isinstance(command, Sleep):
        return {"kind": "sleep"}
    if isinstance(command, Give):
        return {
            "kind": "give",
            "recipient_id": command.recipient_id.value,
            "item_id": command.item_id.value,
        }
    if isinstance(command, Wait):
        return {"kind": "wait"}
    raise PathDependenceSerializationError(
        "unsupported_intervention", "$.common_setup.command"
    )

def _decode_command(value: object, *, path: str) -> AgentCommand:
    data = _object(value, path=path)
    kind = _str(data, "kind", path=path)
    if kind == "move":
        _require_keys(data, {"kind", "destination_id"}, path=path)
        return Move(destination_id=EntityId(_str(data, "destination_id", path=path)))
    if kind == "take":
        _require_keys(data, {"kind", "item_id"}, path=path)
        return Take(item_id=EntityId(_str(data, "item_id", path=path)))
    if kind == "eat":
        _require_keys(data, {"kind", "item_id"}, path=path)
        return Eat(item_id=EntityId(_str(data, "item_id", path=path)))
    if kind == "drink":
        _require_keys(data, {"kind", "source_id"}, path=path)
        return Drink(source_id=EntityId(_str(data, "source_id", path=path)))
    if kind == "sleep":
        _require_keys(data, {"kind"}, path=path)
        return Sleep()
    if kind == "give":
        _require_keys(data, {"kind", "recipient_id", "item_id"}, path=path)
        return Give(
            recipient_id=EntityId(_str(data, "recipient_id", path=path)),
            item_id=EntityId(_str(data, "item_id", path=path)),
        )
    if kind == "wait":
        _require_keys(data, {"kind"}, path=path)
        return Wait()
    raise PathDependenceSerializationError("unsupported_intervention", path)


def _encode_action(action: object) -> dict[str, object]:
    if type(action) is GiveInterventionAction:
        return {
            "kind": "give",
            "item_id": action.item_id.value,
            "recipient_entity_id": action.recipient_entity_id.value,
        }
    if type(action) is WaitInterventionAction:
        return {"kind": "wait"}
    raise PathDependenceSerializationError(
        "unsupported_intervention", "$.action"
    )


def _decode_action(value: object, *, path: str) -> object:
    data = _object(value, path=path)
    kind = _str(data, "kind", path=path)
    if kind == "give":
        _require_keys(data, {"kind", "item_id", "recipient_entity_id"}, path=path)
        return GiveInterventionAction(
            item_id=EntityId(_str(data, "item_id", path=path)),
            recipient_entity_id=EntityId(
                _str(data, "recipient_entity_id", path=path)
            ),
        )
    if kind == "wait":
        _require_keys(data, {"kind"}, path=path)
        return WaitInterventionAction()
    raise PathDependenceSerializationError("unsupported_intervention", path)


def _encode_action_tuple(
    actions: tuple[ScheduledCommandIntervention, ...]
) -> list[dict[str, object]]:
    return [
        {
            "intervention_id": action.intervention_id,
            "actor_id": action.actor_id.value,
            "tick": action.tick.value,
            "action": _encode_action(action.action),
        }
        for action in actions
    ]


def encode_path_dependence_spec_document(spec: PathDependenceSpec) -> dict[str, object]:
    """Encode a spec to a JSON-ready exact-key mapping."""
    if type(spec) is not PathDependenceSpec:
        raise TypeError("encode_path_dependence_spec_document requires spec")
    return {
        "schema_version": spec.schema_version,
        "experiment_id": spec.experiment_id,
        "base": json.loads(encode_runner_config(spec.base).decode("utf-8")),
        "seeds": list(spec.seeds),
        "replicates_per_seed": spec.replicates_per_seed,
        "fork_ticks": [tick.value for tick in spec.fork_ticks],
        "horizon_tick": spec.horizon_tick.value,
        "arms": [
            {
                "arm_id": arm.arm_id,
                "label_code": arm.label_code,
                "role": arm.role.value,
                "schedule_by_fork_tick": [
                    {
                        "fork_tick": schedule.fork_tick.value,
                        "actions": _encode_action_tuple(schedule.actions),
                    }
                    for schedule in arm.schedule_by_fork_tick
                ],
            }
            for arm in spec.arms
        ],
        "contrasts": [
            {
                "contrast_id": contrast.contrast_id,
                "control_arm_id": contrast.control_arm_id,
                "treatment_arm_id": contrast.treatment_arm_id,
            }
            for contrast in spec.contrasts
        ],
        "windows": [
            {
                "window_id": window.window_id,
                "fork_tick": window.fork_tick.value,
                "start_tick": window.start_tick.value,
                "end_tick": window.end_tick.value,
                "generation_start": window.generation_start,
                "generation_end": window.generation_end,
                "absolute_tick_cap": (
                    None
                    if window.absolute_tick_cap is None
                    else window.absolute_tick_cap.value
                ),
            }
            for window in spec.windows
        ],
        "selectors": [
            {
                "selector_id": selector.selector_id,
                "domain": selector.domain.value,
                "window_id": selector.window_id,
            }
            for selector in spec.selectors
        ],
        "assignment_seed": spec.assignment_seed,
        "max_interventions_per_arm": spec.max_interventions_per_arm,
        "common_setup": [
            {
                "actor_id": command.actor_id.value,
                "tick": command.tick.value,
                "command": _encode_command(command.command),
            }
            for command in spec.common_setup
        ],
        "capture_policy": spec.capture_policy,
    }


def encode_path_dependence_spec(spec: PathDependenceSpec) -> bytes:
    """Encode a spec to strict canonical UTF-8 JSON bytes."""
    payload = _canonical_dumps(encode_path_dependence_spec_document(spec))
    if len(payload) > MAX_SPEC_DOCUMENT_BYTES:
        raise PathDependenceSerializationError("document_too_large", "$")
    return payload


def path_dependence_spec_fingerprint(spec: PathDependenceSpec) -> str:
    """Return the canonical SHA-256 identity of an encoded spec."""
    return hashlib.sha256(encode_path_dependence_spec(spec)).hexdigest()


def _decode_actions(
    value: object, *, path: str
) -> tuple[ScheduledCommandIntervention, ...]:
    if not isinstance(value, list):
        raise PathDependenceSerializationError("invalid_collection", path)
    actions: list[ScheduledCommandIntervention] = []
    for index, entry in enumerate(value):
        entry_path = f"{path}[{index}]"
        data = _object(entry, path=entry_path)
        _require_keys(
            data,
            {"intervention_id", "actor_id", "tick", "action"},
            path=entry_path,
        )
        actions.append(
            ScheduledCommandIntervention(
                intervention_id=_str(data, "intervention_id", path=entry_path),
                actor_id=AgentId(_str(data, "actor_id", path=entry_path)),
                tick=Tick(_int(data, "tick", path=entry_path)),
                action=_decode_action(
                    data["action"], path=f"{entry_path}.action"
                ),  # type: ignore[arg-type]
            )
        )
    return tuple(actions)


def _decode_window(value: object, *, path: str) -> OutcomeWindow:
    data = _object(value, path=path)
    _require_keys(
        data,
        {
            "window_id",
            "fork_tick",
            "start_tick",
            "end_tick",
            "generation_start",
            "generation_end",
            "absolute_tick_cap",
        },
        path=path,
    )
    raw_cap = data["absolute_tick_cap"]
    cap = None
    if raw_cap is not None:
        if isinstance(raw_cap, bool) or type(raw_cap) is not int:
            raise PathDependenceSerializationError(
                "invalid_int", f"{path}.absolute_tick_cap"
            )
        cap = Tick(raw_cap)
    generation_start = data["generation_start"]
    generation_end = data["generation_end"]
    if generation_start is not None and (
        isinstance(generation_start, bool) or type(generation_start) is not int
    ):
        raise PathDependenceSerializationError(
            "invalid_int", f"{path}.generation_start"
        )
    if generation_end is not None and (
        isinstance(generation_end, bool) or type(generation_end) is not int
    ):
        raise PathDependenceSerializationError(
            "invalid_int", f"{path}.generation_end"
        )
    return OutcomeWindow(
        window_id=_str(data, "window_id", path=path),
        fork_tick=Tick(_int(data, "fork_tick", path=path)),
        start_tick=Tick(_int(data, "start_tick", path=path)),
        end_tick=Tick(_int(data, "end_tick", path=path)),
        generation_start=generation_start,
        generation_end=generation_end,
        absolute_tick_cap=cap,
    )


def decode_path_dependence_spec(payload: bytes) -> PathDependenceSpec:
    """Decode strict bounded spec bytes into an immutable contract."""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("decode_path_dependence_spec requires bytes")
    raw = bytes(payload)
    if len(raw) > MAX_SPEC_DOCUMENT_BYTES:
        raise PathDependenceSerializationError("document_too_large", "$")
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
        data = decoder.decode(raw.decode("utf-8"))
    except PathDependenceSerializationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PathDependenceSerializationError("invalid_json", "$") from exc
    if not isinstance(data, dict):
        raise PathDependenceSerializationError("invalid_object", "$")
    _require_depth(data, path="$")
    _require_keys(
        data,
        {
            "schema_version",
            "experiment_id",
            "base",
            "seeds",
            "replicates_per_seed",
            "fork_ticks",
            "horizon_tick",
            "arms",
            "contrasts",
            "windows",
            "selectors",
            "assignment_seed",
            "max_interventions_per_arm",
            "common_setup",
            "capture_policy",
        },
        path="$",
    )
    if _str(data, "schema_version", path="$") != PATH_DEPENDENCE_SPEC_SCHEMA_VERSION:
        raise PathDependenceSerializationError("unsupported_base", "$.schema_version")
    if _str(data, "experiment_id", path="$") != PATH_DEPENDENCE_EXPERIMENT_ID:
        raise PathDependenceSerializationError("unsupported_base", "$.experiment_id")
    if _str(data, "capture_policy", path="$") != PATH_DEPENDENCE_CAPTURE_POLICY:
        raise PathDependenceSerializationError("unsupported_base", "$.capture_policy")

    base_value = data["base"]
    _object(base_value, path="$.base")
    try:
        base = decode_runner_config(_canonical_dumps(base_value))
    except Exception as exc:
        raise PathDependenceSerializationError("unsupported_base", "$.base") from exc

    seeds = _list(data, "seeds", path="$")
    for index, seed in enumerate(seeds):
        if isinstance(seed, bool) or type(seed) is not int:
            raise PathDependenceSerializationError(
                "invalid_int", f"$.seeds[{index}]"
            )
    forks = _list(data, "fork_ticks", path="$")
    for index, fork in enumerate(forks):
        if isinstance(fork, bool) or type(fork) is not int:
            raise PathDependenceSerializationError(
                "invalid_int", f"$.fork_ticks[{index}]"
            )

    arms_payload = _list(data, "arms", path="$")
    arms: list[PathDependenceArm] = []
    for index, entry in enumerate(arms_payload):
        entry_path = f"$.arms[{index}]"
        arm_data = _object(entry, path=entry_path)
        _require_keys(
            arm_data,
            {"arm_id", "label_code", "role", "schedule_by_fork_tick"},
            path=entry_path,
        )
        schedules_payload = _list(
            arm_data, "schedule_by_fork_tick", path=entry_path
        )
        schedules: list[ForkTickSchedule] = []
        for schedule_index, raw_schedule in enumerate(schedules_payload):
            schedule_path = f"{entry_path}.schedule_by_fork_tick[{schedule_index}]"
            schedule_data = _object(raw_schedule, path=schedule_path)
            _require_keys(
                schedule_data,
                {"fork_tick", "actions"},
                path=schedule_path,
            )
            schedules.append(
                ForkTickSchedule(
                    fork_tick=Tick(
                        _int(schedule_data, "fork_tick", path=schedule_path)
                    ),
                    actions=_decode_actions(
                        schedule_data["actions"], path=f"{schedule_path}.actions"
                    ),
                )
            )
        arms.append(
            PathDependenceArm(
                arm_id=_str(arm_data, "arm_id", path=entry_path),
                label_code=_str(arm_data, "label_code", path=entry_path),
                role=ArmRole(_str(arm_data, "role", path=entry_path)),
                schedule_by_fork_tick=tuple(schedules),
            )
        )

    contrasts_payload = _list(data, "contrasts", path="$")
    contrasts: list[ProtocolContrast] = []
    for index, entry in enumerate(contrasts_payload):
        entry_path = f"$.contrasts[{index}]"
        contrast_data = _object(entry, path=entry_path)
        _require_keys(
            contrast_data,
            {"contrast_id", "control_arm_id", "treatment_arm_id"},
            path=entry_path,
        )
        contrasts.append(
            ProtocolContrast(
                contrast_id=_str(contrast_data, "contrast_id", path=entry_path),
                control_arm_id=_str(
                    contrast_data, "control_arm_id", path=entry_path
                ),
                treatment_arm_id=_str(
                    contrast_data, "treatment_arm_id", path=entry_path
                ),
            )
        )

    windows_payload = _list(data, "windows", path="$")
    windows = tuple(
        _decode_window(entry, path=f"$.windows[{index}]")
        for index, entry in enumerate(windows_payload)
    )

    selectors_payload = _list(data, "selectors", path="$")
    selectors: list[OutcomeSelector] = []
    for index, entry in enumerate(selectors_payload):
        entry_path = f"$.selectors[{index}]"
        selector_data = _object(entry, path=entry_path)
        _require_keys(
            selector_data,
            {"selector_id", "domain", "window_id"},
            path=entry_path,
        )
        selectors.append(
            OutcomeSelector(
                selector_id=_str(selector_data, "selector_id", path=entry_path),
                domain=OutcomeDomain(_str(selector_data, "domain", path=entry_path)),
                window_id=_str(selector_data, "window_id", path=entry_path),
            )
        )

    setup_payload = _list(data, "common_setup", path="$")
    setup: list[CommonSetupCommand] = []
    for index, entry in enumerate(setup_payload):
        entry_path = f"$.common_setup[{index}]"
        setup_data = _object(entry, path=entry_path)
        _require_keys(
            setup_data, {"actor_id", "tick", "command"}, path=entry_path
        )
        setup.append(
            CommonSetupCommand(
                actor_id=AgentId(_str(setup_data, "actor_id", path=entry_path)),
                tick=Tick(_int(setup_data, "tick", path=entry_path)),
                command=_decode_command(
                    setup_data["command"], path=f"{entry_path}.command"
                ),
            )
        )

    spec = PathDependenceSpec(
        schema_version=_str(data, "schema_version", path="$"),
        experiment_id=_str(data, "experiment_id", path="$"),
        base=base,
        seeds=tuple(seeds),
        replicates_per_seed=_int(data, "replicates_per_seed", path="$"),
        fork_ticks=tuple(Tick(value) for value in forks),
        horizon_tick=Tick(_int(data, "horizon_tick", path="$")),
        arms=tuple(arms),
        contrasts=tuple(contrasts),
        windows=windows,
        selectors=tuple(selectors),
        assignment_seed=_int(data, "assignment_seed", path="$"),
        max_interventions_per_arm=_int(
            data, "max_interventions_per_arm", path="$"
        ),
        common_setup=tuple(setup),
        capture_policy=_str(data, "capture_policy", path="$"),
    )
    _LOG.debug(
        "path_dependence_spec_decoded arms=%s forks=%s selectors=%s",
        len(spec.arms),
        len(spec.fork_ticks),
        len(spec.selectors),
    )
    return spec


def action_schedule_digest(
    actions: tuple[ScheduledCommandIntervention, ...],
) -> str:
    """Return a canonical digest for one arm/F action schedule."""
    document = _encode_action_tuple(actions)
    return hashlib.sha256(_canonical_dumps(document)).hexdigest()


__all__ = [
    "PathDependenceSerializationError",
    "action_schedule_digest",
    "decode_path_dependence_spec",
    "encode_path_dependence_spec",
    "encode_path_dependence_spec_document",
    "path_dependence_spec_fingerprint",
]
