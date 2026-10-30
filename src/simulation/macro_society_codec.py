"""Canonical encoding for macro-society snapshots."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Final

from simulation.macro_society_models import (
    MAX_SNAPSHOT_BYTES,
    MacroSocietyArtifactError,
    MacroSocietyCandidateRecord,
    MacroSocietyCoverage,
    MacroSocietyLineageEdgeRecord,
    MacroSocietyObjectiveRow,
    MacroSocietySnapshot,
    MacroSocietyWindowRecord,
    require_publication_id,
)
from world.identifiers import require_stable_id

__all__ = [
    "compute_macro_society_publication_id",
    "decode_macro_society_snapshot",
    "decode_macro_society_value",
    "encode_macro_society_snapshot",
    "encode_macro_society_value",
    "macro_society_digest",
    "validate_macro_society_value",
]

_SNAPSHOT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "policy_version",
        "run_id",
        "input_revision",
        "generated_tick",
        "publication_id",
        "windows",
        "candidates",
        "edges",
        "objective_rows",
        "coverage",
        "provenance_code",
    }
)
_WINDOW_KEYS: Final[frozenset[str]] = frozenset(
    {
        "window_index",
        "tick_start",
        "tick_end",
        "candidate_ids",
        "overlap_person_count",
        "known_person_count",
        "lane_presence",
    }
)
_CANDIDATE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "macro_society_id",
        "creation_tick",
        "first_tick",
        "last_tick",
        "status",
        "member_ids",
        "lane_signature",
        "overlap_person_ids",
    }
)
_EDGE_KEYS: Final[frozenset[str]] = frozenset(
    {"from_id", "to_id", "kind", "from_tick", "to_tick", "jaccard"}
)
_OBJECTIVE_KEYS: Final[frozenset[str]] = frozenset(
    {"region_id", "tick", "population_count", "cohort_id", "stage_id"}
)
_COVERAGE_KEYS: Final[frozenset[str]] = frozenset({"observed", "expected", "ratio"})


def validate_macro_society_value(value: object) -> None:
    """Reject non-finite floats, non-string keys, and unsupported types."""
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MacroSocietyArtifactError("macro_society_invalid_value")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            validate_macro_society_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise MacroSocietyArtifactError("macro_society_invalid_value")
            validate_macro_society_value(item)
        return
    raise MacroSocietyArtifactError("macro_society_invalid_value")


def encode_macro_society_value(value: object) -> bytes:
    """Canonical compact JSON with one trailing newline."""
    validate_macro_society_value(value)
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return f"{encoded}\n".encode()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MacroSocietyArtifactError("macro_society_duplicate_key")
        result[key] = value
    return result


def _reject_constant(token: str) -> object:
    raise MacroSocietyArtifactError("macro_society_invalid_value")


def decode_macro_society_value(payload: bytes) -> object:
    """Strictly decode one canonical value."""
    if not isinstance(payload, (bytes, bytearray)):
        raise MacroSocietyArtifactError("macro_society_invalid_value")
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise MacroSocietyArtifactError("macro_society_size_limit")
    try:
        text = bytes(payload).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MacroSocietyArtifactError("macro_society_invalid_value") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except MacroSocietyArtifactError:
        raise
    except json.JSONDecodeError as exc:
        raise MacroSocietyArtifactError("macro_society_invalid_value") from exc
    validate_macro_society_value(value)
    return value


def macro_society_digest(value: object) -> str:
    """SHA-256 hex over the canonical encoding of ``value``."""
    return hashlib.sha256(encode_macro_society_value(value)).hexdigest()


def _snapshot_payload(snapshot: MacroSocietySnapshot) -> dict[str, object]:
    return {
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "run_id": snapshot.run_id,
        "input_revision": snapshot.input_revision,
        "generated_tick": snapshot.generated_tick,
        "publication_id": snapshot.publication_id,
        "windows": [
            {
                "window_index": window.window_index,
                "tick_start": window.tick_start,
                "tick_end": window.tick_end,
                "candidate_ids": list(window.candidate_ids),
                "overlap_person_count": window.overlap_person_count,
                "known_person_count": window.known_person_count,
                "lane_presence": [
                    [lane, present] for lane, present in window.lane_presence
                ],
            }
            for window in snapshot.windows
        ],
        "candidates": [
            {
                "macro_society_id": candidate.macro_society_id,
                "creation_tick": candidate.creation_tick,
                "first_tick": candidate.first_tick,
                "last_tick": candidate.last_tick,
                "status": candidate.status,
                "member_ids": list(candidate.member_ids),
                "lane_signature": list(candidate.lane_signature),
                "overlap_person_ids": list(candidate.overlap_person_ids),
            }
            for candidate in snapshot.candidates
        ],
        "edges": [
            {
                "from_id": edge.from_id,
                "to_id": edge.to_id,
                "kind": edge.kind,
                "from_tick": edge.from_tick,
                "to_tick": edge.to_tick,
                "jaccard": edge.jaccard,
            }
            for edge in snapshot.edges
        ],
        "objective_rows": [
            {
                "region_id": row.region_id,
                "tick": row.tick,
                "population_count": row.population_count,
                "cohort_id": row.cohort_id,
                "stage_id": row.stage_id,
            }
            for row in snapshot.objective_rows
        ],
        "coverage": {
            "observed": snapshot.coverage.observed,
            "expected": snapshot.coverage.expected,
            "ratio": snapshot.coverage.ratio,
        },
        "provenance_code": snapshot.provenance_code,
    }


def encode_macro_society_snapshot(snapshot: MacroSocietySnapshot) -> bytes:
    """Encode one snapshot and enforce the byte cap."""
    if type(snapshot) is not MacroSocietySnapshot:
        raise MacroSocietyArtifactError("macro_society_invalid_snapshot")
    payload = encode_macro_society_value(_snapshot_payload(snapshot))
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise MacroSocietyArtifactError("macro_society_size_limit")
    return payload


def _require_keys(
    data: object, expected: frozenset[str], *, code: str = "macro_society_unknown_field"
) -> dict[str, object]:
    if not isinstance(data, dict):
        raise MacroSocietyArtifactError("macro_society_invalid_value")
    keys = set(data)
    if keys - expected:
        raise MacroSocietyArtifactError(code)
    if expected - keys:
        raise MacroSocietyArtifactError("macro_society_missing_field")
    return data


def _string(value: object, *, name: str = "value") -> str:
    if not isinstance(value, str):
        raise MacroSocietyArtifactError("macro_society_invalid_value")
    return require_stable_id(name, value)


def _optional_string(value: object, *, name: str = "value") -> str | None:
    if value is None:
        return None
    return _string(value, name=name)


def _list(value: object, *, name: str = "value") -> list[object]:
    if not isinstance(value, list):
        raise MacroSocietyArtifactError("macro_society_invalid_value")
    return value


def _lane_pair(pair: object) -> tuple[str, bool]:
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise MacroSocietyArtifactError("macro_society_invalid_value")
    lane, present = pair
    return _string(lane, name="lane"), bool(present)


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise MacroSocietyArtifactError("macro_society_invalid_value")
    return tuple(value)


def decode_macro_society_snapshot(payload: bytes) -> MacroSocietySnapshot:
    """Strictly decode one snapshot with exact key sets."""
    data = _require_keys(decode_macro_society_value(payload), _SNAPSHOT_KEYS)
    windows = tuple(
        MacroSocietyWindowRecord(
            window_index=item["window_index"],  # type: ignore[arg-type]
            tick_start=item["tick_start"],  # type: ignore[arg-type]
            tick_end=item["tick_end"],  # type: ignore[arg-type]
            candidate_ids=_string_list(item["candidate_ids"]),
            overlap_person_count=item["overlap_person_count"],  # type: ignore[arg-type]
            known_person_count=item["known_person_count"],  # type: ignore[arg-type]
            lane_presence=tuple(
                _lane_pair(pair) for pair in _list(item["lane_presence"])
            ),
        )
        for item in (
            _require_keys(raw, _WINDOW_KEYS) for raw in _list(data["windows"])
        )
    )
    candidates = tuple(
        MacroSocietyCandidateRecord(
            macro_society_id=_string(item["macro_society_id"], name="macro_society_id"),
            creation_tick=item["creation_tick"],  # type: ignore[arg-type]
            first_tick=item["first_tick"],  # type: ignore[arg-type]
            last_tick=item["last_tick"],  # type: ignore[arg-type]
            status=_string(item["status"], name="status"),
            member_ids=_string_list(item["member_ids"]),
            lane_signature=_string_list(item["lane_signature"]),
            overlap_person_ids=_string_list(item["overlap_person_ids"]),
        )
        for item in (
            _require_keys(raw, _CANDIDATE_KEYS) for raw in _list(data["candidates"])
        )
    )
    edges = tuple(
        MacroSocietyLineageEdgeRecord(
            from_id=_optional_string(item["from_id"], name="from_id"),
            to_id=_optional_string(item["to_id"], name="to_id"),
            kind=_string(item["kind"], name="kind"),
            from_tick=item["from_tick"],  # type: ignore[arg-type]
            to_tick=item["to_tick"],  # type: ignore[arg-type]
            jaccard=None if item["jaccard"] is None else float(item["jaccard"]),  # type: ignore[arg-type]
        )
        for item in (
            _require_keys(raw, _EDGE_KEYS) for raw in _list(data["edges"])
        )
    )
    objective = tuple(
        MacroSocietyObjectiveRow(
            region_id=_string(item["region_id"], name="region_id"),
            tick=item["tick"],  # type: ignore[arg-type]
            population_count=item["population_count"],  # type: ignore[arg-type]
            cohort_id=_optional_string(item["cohort_id"], name="cohort_id"),
            stage_id=_optional_string(item["stage_id"], name="stage_id"),
        )
        for item in (
            _require_keys(raw, _OBJECTIVE_KEYS) for raw in _list(data["objective_rows"])
        )
    )
    coverage_data = _require_keys(data["coverage"], _COVERAGE_KEYS)
    coverage = MacroSocietyCoverage(
        observed=coverage_data["observed"],  # type: ignore[arg-type]
        expected=coverage_data["expected"],  # type: ignore[arg-type]
        ratio=(
            None
            if coverage_data["ratio"] is None
            else float(coverage_data["ratio"])  # type: ignore[arg-type]
        ),
    )
    snapshot = MacroSocietySnapshot(
        schema_version=_string(data["schema_version"], name="schema_version"),
        policy_version=_string(data["policy_version"], name="policy_version"),
        run_id=_string(data["run_id"], name="run_id"),
        input_revision=_string(data["input_revision"], name="input_revision"),
        generated_tick=data["generated_tick"],  # type: ignore[arg-type]
        publication_id=_string(data["publication_id"], name="publication_id"),
        windows=windows,
        candidates=candidates,
        edges=edges,
        objective_rows=objective,
        coverage=coverage,
        provenance_code=_string(data["provenance_code"], name="provenance_code"),
    )
    if encode_macro_society_snapshot(snapshot) != bytes(payload):
        raise MacroSocietyArtifactError("macro_society_digest_mismatch")
    return snapshot


def compute_macro_society_publication_id(
    snapshot_payload: bytes, *, run_id: str
) -> str:
    """Content-addressed publication id bound to one run."""
    if not isinstance(snapshot_payload, (bytes, bytearray)):
        raise MacroSocietyArtifactError("macro_society_invalid_value")
    run = require_stable_id("run_id", run_id)
    data = decode_macro_society_value(bytes(snapshot_payload))
    if not isinstance(data, dict):
        raise MacroSocietyArtifactError("macro_society_invalid_value")
    # The publication id is derived from content only, so the id field itself is
    # normalized away to keep derivation idempotent.
    normalized = dict(data)
    normalized["publication_id"] = ""
    encoded = encode_macro_society_value(normalized)
    digest = hashlib.sha256(run.encode("utf-8") + b"\x00" + encoded).hexdigest()[:16]
    return require_publication_id(f"msoc-edge-{digest}")
