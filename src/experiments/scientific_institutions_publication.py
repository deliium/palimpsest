"""Trusted completed-run composition of scientific-institution snapshots."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Final

from analysis.scientific_institutions_contract import (
    PracticeStatus,
    derive_practice_token,
)
from analysis.scientific_institutions_metrics import (
    ScientificInstitutionsMetricInputs,
)
from simulation.scientific_institutions_codec import (
    canonical_scientific_institutions_json,
)
from simulation.scientific_institutions_models import (
    MAX_SECTION_ROWS,
    MAX_SNAPSHOT_BYTES,
    ScientificInstitutionsRow,
    ScientificInstitutionsSnapshot,
    ScientificInstitutionsSnapshotOverflow,
)

__all__ = [
    "ScientificInstitutionsSnapshotOverflow",
    "compose_scientific_institutions_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_institutions_publication"
)


def _org_token(run_id: str, organization_id: str) -> str:
    return derive_practice_token("organization", run_id, organization_id)


def _join(values: Iterable[object]) -> str:
    return ",".join(str(item) for item in values)


def _join_pairs(values: Iterable[tuple[str, str]]) -> str:
    return ",".join(f"{kind}|{token}" for kind, token in values)


def _window_rows(
    inputs: ScientificInstitutionsMetricInputs,
) -> tuple[ScientificInstitutionsRow, ...]:
    rows: list[ScientificInstitutionsRow] = []
    for window in inputs.assessment.windows:
        rows.append(
            ScientificInstitutionsRow(
                section="windows",
                window_index=window.window_index,
                row_key=f"windows:{window.window_index}",
                fields=(
                    ("start_tick", window.start_tick),
                    ("end_tick_exclusive", window.end_tick_exclusive),
                    ("complete", 1 if window.complete else 0),
                    ("state", window.state.value),
                    (
                        "execution_coverage",
                        window.execution_coverage.value,
                    ),
                    ("carrier_coverage", window.carrier_coverage.value),
                    (
                        "organization_coverage",
                        window.organization_coverage.value,
                    ),
                    ("row_count", window.row_count),
                    ("unassigned", window.unassigned),
                    ("ambiguous", window.ambiguous),
                ),
            )
        )
    return tuple(rows)


def _practice_rows(
    inputs: ScientificInstitutionsMetricInputs, run_id: str
) -> tuple[ScientificInstitutionsRow, ...]:
    rows: list[ScientificInstitutionsRow] = []
    for row in inputs.assessment.rows:
        token = _org_token(run_id, row.organization_id)
        rows.append(
            ScientificInstitutionsRow(
                section="practice",
                window_index=row.window_index,
                row_key=(
                    f"practice:{row.window_index}:{token}:"
                    f"{row.operator}:{row.process_token}"
                ),
                fields=(
                    ("organization_token", token),
                    ("operator", row.operator),
                    ("process_token", row.process_token),
                    ("status", row.status.value),
                    ("execution_tokens", _join(row.execution_tokens)),
                    ("service_tokens", _join(row.service_tokens)),
                    (
                        "contribution_tokens",
                        _join(row.contribution_tokens),
                    ),
                    ("actor_tokens", _join(row.actor_tokens)),
                    ("carrier_tokens", _join_pairs(row.carrier_tokens)),
                    (
                        "surviving_carrier_tokens",
                        _join_pairs(row.surviving_carrier_tokens),
                    ),
                    ("coverage", row.coverage.value),
                ),
            )
        )
    return tuple(rows)


def _signal_rows(
    inputs: ScientificInstitutionsMetricInputs, run_id: str
) -> tuple[ScientificInstitutionsRow, ...]:
    rows: list[ScientificInstitutionsRow] = []
    for window in inputs.context.windows:
        for index, supplement in enumerate(window.supplements):
            organization = (
                ""
                if supplement.organization_id is None
                else _org_token(run_id, supplement.organization_id)
            )
            rows.append(
                ScientificInstitutionsRow(
                    section="signals",
                    window_index=supplement.window_index,
                    row_key=(
                        f"signals:{supplement.window_index}:"
                        f"{supplement.signal.value}:{organization}:{index}"
                    ),
                    fields=(
                        ("organization_token", organization),
                        ("signal", supplement.signal.value),
                        ("actor_tokens", _join(supplement.actor_tokens)),
                        (
                            "carrier_tokens",
                            _join_pairs(supplement.carrier_tokens),
                        ),
                        ("tick", supplement.tick),
                        ("count", supplement.count),
                        ("contextual", 1 if supplement.contextual else 0),
                    ),
                )
            )
    return tuple(rows)


def _lineage_rows(
    inputs: ScientificInstitutionsMetricInputs, run_id: str
) -> tuple[ScientificInstitutionsRow, ...]:
    rows: list[ScientificInstitutionsRow] = []
    for episode in inputs.lineage.episodes:
        organization = _org_token(run_id, episode.organization_id)
        rows.append(
            ScientificInstitutionsRow(
                section="lineage",
                window_index=episode.first_stable_window,
                row_key=f"lineage:episode:{episode.episode_id}",
                fields=(
                    ("record_kind", "episode"),
                    ("episode_id", episode.episode_id),
                    ("organization_token", organization),
                    ("operator", episode.operator),
                    ("process_token", episode.process_token),
                    ("first_stable_window", episode.first_stable_window),
                    ("last_stable_window", episode.last_stable_window),
                    ("windows", _join(episode.windows)),
                    ("carrier_tokens", _join_pairs(episode.carrier_tokens)),
                ),
            )
        )
    for transition in inputs.lineage.transitions:
        from_token = (
            ""
            if transition.from_organization_id is None
            else _org_token(run_id, transition.from_organization_id)
        )
        to_token = (
            ""
            if transition.to_organization_id is None
            else _org_token(run_id, transition.to_organization_id)
        )
        window = (
            transition.to_window
            if transition.to_window is not None
            else transition.known_at_window
        )
        rows.append(
            ScientificInstitutionsRow(
                section="lineage",
                window_index=window,
                row_key=(
                    f"lineage:transition:{transition.kind.value}:"
                    f"{transition.from_episode_id or ''}:"
                    f"{transition.to_episode_id or ''}:"
                    f"{transition.known_at_window}"
                ),
                fields=(
                    ("record_kind", "transition"),
                    ("transition_kind", transition.kind.value),
                    ("from_episode_id", transition.from_episode_id or ""),
                    ("to_episode_id", transition.to_episode_id or ""),
                    (
                        "from_window",
                        -1
                        if transition.from_window is None
                        else transition.from_window,
                    ),
                    (
                        "to_window",
                        -1
                        if transition.to_window is None
                        else transition.to_window,
                    ),
                    ("known_at_window", transition.known_at_window),
                    ("from_organization_token", from_token),
                    ("to_organization_token", to_token),
                    (
                        "carrier_tokens",
                        _join_pairs(transition.carrier_tokens),
                    ),
                    (
                        "organization_transition_refs",
                        ",".join(
                            f"{from_id}|{to_id}|{index}"
                            for from_id, to_id, index
                            in transition.organization_transition_refs
                        ),
                    ),
                ),
            )
        )
    return tuple(rows)


def _validate_references(
    snapshot: ScientificInstitutionsSnapshot,
) -> None:
    window_indexes = {
        row.window_index
        for row in snapshot.windows
        if row.row_key.startswith("windows:")
    }
    for section in ("practice", "signals", "lineage"):
        for row in snapshot.rows_for(section):
            if section != "lineage" or (
                dict(row.fields).get("record_kind") == "episode"
            ):
                if row.window_index not in window_indexes:
                    raise ValueError("window_reference: invalid")
    episode_ids = {
        str(dict(row.fields).get("episode_id", ""))
        for row in snapshot.lineage
        if dict(row.fields).get("record_kind") == "episode"
    }
    for row in snapshot.lineage:
        fields = dict(row.fields)
        if fields.get("record_kind") != "transition":
            continue
        for name in ("from_episode_id", "to_episode_id"):
            value = str(fields.get(name, ""))
            if value and value not in episode_ids:
                raise ValueError("episode_reference: invalid")


def compose_scientific_institutions_snapshot(
    inputs: ScientificInstitutionsMetricInputs,
    *,
    run_id: str,
    publication_id: str,
    input_revision: str,
    boundary_tick: int,
) -> ScientificInstitutionsSnapshot:
    """Compose one canonical immutable snapshot from detached evidence."""

    if type(inputs) is not ScientificInstitutionsMetricInputs:
        raise ScientificInstitutionsSnapshotOverflow("invalid_inputs")
    assessment = inputs.assessment
    windows = _window_rows(inputs)
    practice = _practice_rows(inputs, run_id)
    signals = _signal_rows(inputs, run_id)
    lineage = _lineage_rows(inputs, run_id)
    total = len(windows) + len(practice) + len(signals) + len(lineage)
    if (
        total > MAX_SECTION_ROWS
        or len(windows) > MAX_SECTION_ROWS
        or len(practice) > MAX_SECTION_ROWS
        or len(signals) > MAX_SECTION_ROWS
        or len(lineage) > MAX_SECTION_ROWS
    ):
        raise ScientificInstitutionsSnapshotOverflow("row_cap")
    summary = (
        ("window_count", len(windows)),
        ("practice_row_count", len(practice)),
        ("stable_row_count", sum(
            1 for row in assessment.rows if row.status is PracticeStatus.STABLE
        )),
        ("signal_row_count", len(signals)),
        ("episode_count", len(inputs.lineage.episodes)),
        ("transition_count", len(inputs.lineage.transitions)),
        ("unassigned_count", assessment.unassigned),
        ("ambiguous_count", assessment.ambiguous),
    )
    snapshot = ScientificInstitutionsSnapshot(
        run_id=run_id,
        publication_id=publication_id,
        policy_version=assessment.policy_version,
        input_revision=input_revision,
        boundary_tick=boundary_tick,
        windows=tuple(
            sorted(windows, key=lambda row: row.window_index)
        ),
        practice=tuple(
            sorted(
                practice,
                key=lambda row: (row.window_index, row.row_key),
            )
        ),
        signals=tuple(
            sorted(
                signals,
                key=lambda row: (row.window_index, row.row_key),
            )
        ),
        lineage=tuple(
            sorted(
                lineage,
                key=lambda row: (row.window_index, row.row_key),
            )
        ),
        summary=summary,
    )
    _validate_references(snapshot)
    size = len(canonical_scientific_institutions_json(snapshot))
    if size > MAX_SNAPSHOT_BYTES:
        raise ScientificInstitutionsSnapshotOverflow("byte_cap")
    _LOG.info(
        "scientific_institutions_snapshot_composed run_id=%s rows=%s bytes=%s",
        run_id,
        total,
        size,
    )
    return snapshot
