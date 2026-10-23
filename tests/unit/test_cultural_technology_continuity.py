"""Technology retention, archival preservation, and global loss separation."""

from __future__ import annotations

from analysis.cultural_evolution_evidence import (
    CULTURAL_DIMENSIONS,
    ArchiveKnowledgeState,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    InventoryBoundary,
    TraitPresence,
)
from analysis.cultural_technology_continuity import (
    compute_cultural_technology_continuity,
)
from analysis.models import MetricAvailability

_A = "a" * 64
_B = "b" * 64
_C = "c" * 64
_KEY = "tech:fire"


def _coverage(
    owners: tuple[str, ...] | None = None,
) -> tuple[tuple[str, str, str], ...]:
    owners = owners or ("a",)
    return tuple(
        (owner, dimension, "complete")
        for owner in owners
        for dimension in CULTURAL_DIMENSIONS
    )


def _tech(
    owner: str,
    digest: str,
    *,
    key: str = _KEY,
    local_id: str | None = None,
) -> TraitPresence:
    return TraitPresence(
        owner_id=owner,
        local_entry_id=local_id or f"entry:{owner}:{digest[:4]}",
        dimension="technology",
        content_digest=digest,
        lineage_key=key,
        status="active",
    )


def _boundary(
    tick: int,
    entries: tuple[TraitPresence, ...],
    *,
    owners: tuple[str, ...] | None = None,
    generations: dict[str, int] | None = None,
) -> InventoryBoundary:
    owners = owners or tuple(sorted({entry.owner_id for entry in entries})) or ("a",)
    return InventoryBoundary(
        boundary_tick=tick,
        living_owner_ids=owners,
        generation_by_owner=(
            {owner: 0 for owner in owners}
            if generations is None
            else {owner: generations.get(owner, 0) for owner in owners}
        ),
        owner_dimension_coverage=_coverage(owners),
        entries=entries,
    )


def _archive(
    tick: int,
    *,
    subject: str = _KEY,
    digest: str = _A,
    present: bool = True,
) -> ArchiveKnowledgeState:
    return ArchiveKnowledgeState(
        boundary_tick=tick,
        subject_id=subject,
        content_digest=digest,
        record_present=present,
        holder_owner_ids=(),
        provenance_source_ids=("record:1",),
        evidence_ids=("record-evidence-1",),
    )


def _inputs(
    boundaries,
    *,
    baseline: int = 0,
    end: int | None = 1,
    archives: tuple[ArchiveKnowledgeState, ...] = (),
) -> CulturalEvolutionInputs:
    return CulturalEvolutionInputs(
        run_id="run-technology",
        source_revision="rev-technology",
        window=CulturalAnalysisWindow(baseline_boundary=baseline, end_boundary=end),
        boundaries=boundaries,
        archive_states=archives,
    )


def _row(rows, measurement_id):
    matches = [row for row in rows if row.measurement_id == measurement_id]
    assert len(matches) == 1, (measurement_id, matches)
    return matches[0]


def test_living_holder_survives() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, (_tech("a", _A),)),
                _boundary(1, (_tech("a", _A),)),
            )
        )
    )
    assert _row(rows, "living_retention").value == 1.0
    assert _row(rows, "exact_variant_retention").value == 1.0
    assert _row(rows, "living_loss_count").value == 0.0
    assert _row(rows, "global_loss_count").value == 0.0


def test_holder_dies_but_intact_record_preserves_global_knowledge() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, (_tech("a", _A),)),
                _boundary(1, (), owners=("a",)),
            ),
            archives=(_archive(1),),
        )
    )
    assert _row(rows, "living_retention").value == 0.0
    assert _row(rows, "technology_preserved_count").value == 1.0
    assert _row(rows, "global_loss_count").value == 0.0


def test_living_and_archive_both_absent_is_global_loss() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, (_tech("a", _A),)),
                _boundary(1, (), owners=("a",)),
            ),
            archives=(_archive(1, present=False),),
        )
    )
    assert _row(rows, "living_retention").value == 0.0
    assert _row(rows, "technology_absent_count").value == 1.0
    assert _row(rows, "global_loss_count").value == 1.0
    assert _row(rows, "global_loss_share").value == 1.0


def test_unknown_archive_inventory_censors_global_loss() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, (_tech("a", _A),)),
                _boundary(1, (), owners=("a",)),
            )
        )
    )
    assert _row(rows, "living_retention").value == 0.0
    assert _row(rows, "technology_unknown_count").value == 1.0
    assert _row(rows, "global_loss_count").value is None
    assert _row(rows, "global_loss_count").availability is MetricAvailability.UNKNOWN


def test_unrelated_record_does_not_rescue_technique() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, (_tech("a", _A),)),
                _boundary(1, (), owners=("a",)),
            ),
            archives=(_archive(1, subject="tech:boat"),),
        )
    )
    assert _row(rows, "technology_preserved_count").value == 0.0
    assert _row(rows, "technology_unknown_count").value == 1.0
    assert _row(rows, "global_loss_count").value is None


def test_damaged_record_is_not_preservation() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, (_tech("a", _A),)),
                _boundary(1, (), owners=("a",)),
            ),
            archives=(_archive(1, present=False),),
        )
    )
    assert _row(rows, "technology_preserved_count").value == 0.0
    assert _row(rows, "technology_absent_count").value == 1.0


def test_mutation_keeps_content_key_but_not_exact_variant() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, (_tech("a", _A),)),
                _boundary(1, (_tech("a", _B),)),
            )
        )
    )
    assert _row(rows, "living_retention").value == 1.0
    assert _row(rows, "exact_variant_retention").value == 0.0


def test_later_generation_nonkin_holder_retains_knowledge() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, (_tech("a", _A),), owners=("a",), generations={"a": 0}),
                _boundary(1, (_tech("b", _A),), owners=("b",), generations={"b": 5}),
            )
        )
    )
    assert _row(rows, "living_retention").value == 1.0
    assert _row(rows, "baseline_content_key_count").value == 1.0


def test_empty_baseline_has_null_retention() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, ()),
                _boundary(1, (_tech("a", _A),)),
            )
        )
    )
    assert _row(rows, "baseline_content_key_count").value == 0.0
    assert _row(rows, "living_retention").value is None
    assert _row(rows, "living_retention").reason_code == "empty_baseline"


def test_missing_baseline_is_unknown() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (_boundary(0, (_tech("a", _A),)),),
            baseline=5,
            end=6,
        )
    )
    assert _row(rows, "living_retention").value is None
    assert _row(rows, "living_retention").reason_code == "missing_baseline"


def test_early_stop_before_requested_endpoint_is_unknown() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, (_tech("a", _A),)),
                _boundary(1, (_tech("a", _A),)),
            ),
            end=5,
        )
    )
    assert _row(rows, "living_retention").value is None
    assert _row(rows, "living_retention").reason_code == "missing_endpoint"


def test_performability_without_evidence_is_unknown_not_loss() -> None:
    rows = compute_cultural_technology_continuity(
        _inputs(
            (
                _boundary(0, (_tech("a", _A),)),
                _boundary(1, (_tech("a", _A),)),
            )
        )
    )
    assert _row(rows, "living_retention").value == 1.0
    assert _row(rows, "not_performable_count").value is None
    assert (
        _row(rows, "not_performable_count").reason_code == "no_performability_evidence"
    )


def _coverage_code(
    owners: tuple[str, ...], code: str
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (owner, dimension, code if dimension == "technology" else "complete")
        for owner in owners
        for dimension in CULTURAL_DIMENSIONS
    )


def test_missing_endpoint_coverage_is_unknown_not_loss() -> None:
    boundaries = (
        _boundary(0, (_tech("a", _A),)),
        InventoryBoundary(
            boundary_tick=2,
            living_owner_ids=("a",),
            generation_by_owner={"a": 0},
            owner_dimension_coverage=_coverage_code(("a",), "missing"),
            entries=(),
        ),
    )
    rows = compute_cultural_technology_continuity(_inputs(boundaries, end=2))
    row = _row(rows, "living_retention")
    assert row.value is None
    assert row.availability is MetricAvailability.UNKNOWN
    assert row.reason_code == "partial_endpoint"
    assert _row(rows, "living_loss_count").value is None


def test_disabled_baseline_channel_is_unknown_not_empty() -> None:
    boundaries = (
        InventoryBoundary(
            boundary_tick=0,
            living_owner_ids=("a",),
            generation_by_owner={"a": 0},
            owner_dimension_coverage=_coverage_code(("a",), "disabled"),
            entries=(),
        ),
        _boundary(2, (), owners=("a",)),
    )
    rows = compute_cultural_technology_continuity(_inputs(boundaries, end=2))
    row = _row(rows, "baseline_content_key_count")
    assert row.value is None
    assert row.reason_code == "channel_disabled"


def test_empty_population_is_not_inferred_loss() -> None:
    boundaries = (
        _boundary(0, (_tech("a", _A),)),
        InventoryBoundary(
            boundary_tick=2,
            living_owner_ids=(),
            generation_by_owner={},
            owner_dimension_coverage=(),
            entries=(),
        ),
    )
    rows = compute_cultural_technology_continuity(_inputs(boundaries, end=2))
    row = _row(rows, "living_retention")
    assert row.value is None
    assert row.reason_code == "population_empty"
    assert _row(rows, "global_loss_count").availability is MetricAvailability.UNKNOWN
