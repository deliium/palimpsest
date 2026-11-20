"""Trusted completed-run publication bridge for competing theories."""

from __future__ import annotations

import logging
from typing import Final

from analysis.competing_theories_models import CompetingTheoryAnalysis
from simulation.competing_theories_codec import canonical_competing_theories_json
from simulation.competing_theories_models import (
    MAX_SECTION_ROWS,
    MAX_SNAPSHOT_BYTES,
    CompetingTheoriesSnapshot,
    TheorySnapshotOverflow,
    TheorySnapshotRow,
)

__all__ = [
    "TheorySnapshotOverflow",
    "compose_competing_theories_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.competing_theories_publication"
)


def _row(
    section: str,
    window_start: int,
    window_end: int,
    theory_id: str,
    row_key: str,
    fields: tuple[tuple[str, int | str], ...],
) -> TheorySnapshotRow:
    return TheorySnapshotRow(
        section=section,
        window_start=window_start,
        window_end=window_end,
        theory_id=theory_id,
        row_key=row_key,
        fields=fields,
    )


def _candidate_rows(
    analysis: CompetingTheoryAnalysis,
) -> dict[int, tuple[TheorySnapshotRow, ...]]:
    """Build every row exactly once, grouped by its owning window."""

    by_window: dict[int, list[TheorySnapshotRow]] = {}

    def _add(row: TheorySnapshotRow) -> None:
        by_window.setdefault(row.window_start, []).append(row)

    for claim_row in analysis.claim_rows:
        _add(
            _row(
                "theories",
                claim_row.window_start,
                claim_row.window_end,
                claim_row.claim_token,
                f"theories:{claim_row.claim_token}",
                (
                    ("owner_token", claim_row.owner_token),
                    ("context_token", claim_row.context_token),
                    ("account", claim_row.account),
                    ("category", claim_row.category),
                    ("created_tick", claim_row.created_tick),
                ),
            )
        )
    for support_row in analysis.support_edges:
        _add(
            _row(
                "support",
                support_row.window_start,
                support_row.window_end,
                support_row.claim_token,
                f"support:{support_row.window_start}:{support_row.owner_token}:{support_row.claim_token}",
                (("owner_token", support_row.owner_token),),
            )
        )
    for citation_row in analysis.citation_edges:
        _add(
            _row(
                "citations",
                citation_row.window_start,
                citation_row.window_end,
                citation_row.claim_token,
                f"citations:{citation_row.tick}:{citation_row.claim_token}:{citation_row.kind}:{citation_row.polarity}",
                (
                    ("owner_token", citation_row.owner_token),
                    ("kind", citation_row.kind),
                    ("polarity", citation_row.polarity),
                    ("root_token", citation_row.root_token),
                    ("independent", 1 if citation_row.independent else 0),
                    ("tick", citation_row.tick),
                ),
            )
        )
    for case_row in analysis.case_rows:
        observed = case_row.observed_category or ""
        for claim_token, predicted, probabilities, brier in case_row.rows:
            _add(
                _row(
                    "predictions",
                    case_row.window_start,
                    case_row.window_end,
                    claim_token,
                    f"predictions:{case_row.case_token}:{claim_token}",
                    (
                        ("case_token", case_row.case_token),
                        ("owner_token", case_row.owner_token),
                        ("state", case_row.state),
                        ("observed_category", observed),
                        ("predicted_category", predicted),
                        ("probabilities_milli", probabilities),
                        ("brier_numerator", brier),
                        ("issued_tick", case_row.issued_tick),
                        ("target_tick", case_row.target_tick),
                    ),
                )
            )
            if case_row.state == "scored" and predicted != observed:
                _add(
                    _row(
                        "failures",
                        case_row.window_start,
                        case_row.window_end,
                        claim_token,
                        f"failures:{case_row.case_token}:{claim_token}",
                        (
                            ("case_token", case_row.case_token),
                            ("owner_token", case_row.owner_token),
                            ("observed_category", observed),
                            ("failure_count", 1),
                        ),
                    )
                )
    for transmission_row in analysis.transmission_edges:
        _add(
            _row(
                "transmission",
                transmission_row.window_start,
                transmission_row.window_end,
                transmission_row.claim_token,
                (
                    f"transmission:{transmission_row.window_start}:"
                    f"{transmission_row.speaker_token}:"
                    f"{transmission_row.learner_token}:{transmission_row.act}"
                ),
                (
                    ("speaker_token", transmission_row.speaker_token),
                    ("learner_token", transmission_row.learner_token),
                    ("act", transmission_row.act),
                ),
            )
        )
    for coverage_row in analysis.coverage:
        _add(
            _row(
                "coverage",
                coverage_row.window_start,
                coverage_row.window_end,
                f"window:{coverage_row.window_start}",
                f"coverage:{coverage_row.window_start}",
                (
                    ("observed_owners", coverage_row.observed_owners),
                    ("expected_owners", coverage_row.expected_owners),
                    ("unavailable_owners", coverage_row.unavailable_owners),
                    ("omitted_windows", coverage_row.omitted_windows),
                ),
            )
        )
    return {
        start: tuple(
            sorted(rows, key=lambda row: (row.window_start, row.theory_id, row.row_key))
        )
        for start, rows in by_window.items()
    }


def _snapshot(
    *,
    run_id: str,
    publication_id: str,
    analysis: CompetingTheoryAnalysis,
    admitted: tuple[int, ...],
    rows: tuple[TheorySnapshotRow, ...],
    omitted_windows: int,
) -> CompetingTheoriesSnapshot:
    sections: dict[str, tuple[TheorySnapshotRow, ...]] = {
        name: tuple(
            sorted(
                (row for row in rows if row.section == name),
                key=lambda row: (row.window_start, row.theory_id, row.row_key),
            )
        )
        for name in (
            "theories",
            "support",
            "citations",
            "predictions",
            "failures",
            "transmission",
            "coverage",
        )
    }
    return CompetingTheoriesSnapshot(
        run_id=run_id,
        publication_id=publication_id,
        theories=sections["theories"],
        support=sections["support"],
        citations=sections["citations"],
        predictions=sections["predictions"],
        failures=sections["failures"],
        transmission=sections["transmission"],
        coverage=sections["coverage"],
        omitted_windows=omitted_windows,
        first_retained_window=(min(admitted) if admitted else 0),
        summary=(
            ("claim_count", analysis.claim_count),
            ("support_edge_count", analysis.support_edge_count),
            ("community_count", analysis.community_count),
            ("citation_count", analysis.citation_count),
            ("prediction_count", analysis.prediction_count),
            ("failure_count", analysis.failure_count),
            ("teaching_count", analysis.teaching_count),
        ),
    )


def compose_competing_theories_snapshot(
    analysis: CompetingTheoryAnalysis,
    *,
    run_id: str,
    publication_id: str,
) -> CompetingTheoriesSnapshot:
    """Compose the newest whole windows that fit the canonical envelope."""

    if type(analysis) is not CompetingTheoryAnalysis:
        raise ValueError("competing_theories_analysis_invalid_type")
    by_window = _candidate_rows(analysis)
    claim_rows = {
        row.theory_id: row
        for rows in by_window.values()
        for row in rows
        if row.section == "theories"
    }
    windows = sorted(by_window, reverse=True)
    admitted: list[int] = []
    admitted_rows: list[TheorySnapshotRow] = []
    admitted_keys: set[tuple[str, str]] = set()
    for start in windows:
        candidate = by_window[start]
        referenced = {
            row.theory_id
            for row in candidate
            if row.section
            in {
                "support",
                "citations",
                "predictions",
                "failures",
                "transmission",
            }
        }
        dependency_rows = tuple(
            claim_rows[token]
            for token in sorted(referenced)
            if token in claim_rows and token not in {
                row.theory_id
                for row in candidate
                if row.section == "theories"
            }
        )
        proposed = tuple(admitted_rows + list(candidate) + list(dependency_rows))
        proposed_keys = set(admitted_keys)
        proposed_keys.update((row.section, row.row_key) for row in proposed)
        if len(proposed_keys) != len(proposed):
            # Exact duplicate rows are no-ops; keep the canonical first one.
            proposed = tuple(
                {
                    (row.section, row.row_key): row for row in proposed
                }.values()
            )
        snapshot = _snapshot(
            run_id=run_id,
            publication_id=publication_id,
            analysis=analysis,
            admitted=(*admitted, start),
            rows=proposed,
            omitted_windows=0,
        )
        if any(len(snapshot.rows_for(name)) > MAX_SECTION_ROWS for name in (
            "theories",
            "support",
            "citations",
            "predictions",
            "failures",
            "transmission",
            "coverage",
        )):
            break
        if len(canonical_competing_theories_json(snapshot)) > MAX_SNAPSHOT_BYTES:
            break
        admitted.append(start)
        admitted_rows = list(proposed)
        admitted_keys = proposed_keys
    if not admitted:
        _LOG.warning(
            "competing_theories_publication_overflow run_id=%s publication_id=%s",
            run_id,
            publication_id,
        )
        raise TheorySnapshotOverflow("quota_exceeded")
    total_omitted = (len(windows) - len(admitted)) + (
        analysis.coverage[-1].omitted_windows if analysis.coverage else 0
    )
    snapshot = _snapshot(
        run_id=run_id,
        publication_id=publication_id,
        analysis=analysis,
        admitted=tuple(admitted),
        rows=tuple(admitted_rows),
        omitted_windows=total_omitted,
    )
    if len(canonical_competing_theories_json(snapshot)) > MAX_SNAPSHOT_BYTES:
        raise TheorySnapshotOverflow("quota_exceeded")
    _LOG.debug(
        "competing_theories_snapshot_composed run_id=%s "
        "publication_id=%s windows=%s omitted=%s",
        run_id,
        publication_id,
        len(admitted),
        total_omitted,
    )
    return snapshot
