# mypy: ignore-errors
"""V4-33 detached lineage: edges, changes, loss, and rediscovery."""

from __future__ import annotations

import pytest

from analysis.science_diffusion_contract import (
    DIFFUSION_WINDOW_TICKS,
    DiffusionContextFlag,
    DiffusionInputs,
    DiffusionLane,
    DiffusionOccurrence,
    DiffusionReason,
    DiffusionResolution,
    DiffusionStage,
    EvidenceKind,
    EvidenceRef,
    HypothesisDescriptor,
    LaneCoverage,
    LaneCoverageState,
    ScienceKind,
    ScienceVersion,
    ScienceVersionKey,
)
from analysis.science_diffusion_lineage import (
    CarrierClosureWitness,
    DiffusionChangeKind,
    DiffusionEdgeKind,
    DiffusionLossScope,
    DiffusionRediscoveryKind,
    RediscoveryRoot,
    V3Link,
    derive_science_diffusion,
)

pytestmark = pytest.mark.unit

RUN = "run-sdf-lineage"


def _key(owner: str = "agent-a", revision: int = 0) -> ScienceVersionKey:
    return ScienceVersionKey(
        run_id=RUN,
        owner_id=owner,
        kind=ScienceKind.HYPOTHESIS,
        local_id="h1",
        revision_index=revision,
    )


def _version(
    *,
    owner: str = "agent-a",
    revision: int = 0,
    tick: int = 0,
    observed: int | None = None,
    predicted: str = "success",
    status: str = "provisional",
    reason: str = "formulated",
    wire_extra: tuple[tuple[str, str], ...] = (),
) -> ScienceVersion:
    key = _key(owner, revision)
    return ScienceVersion(
        key=key,
        occurrence_tick=tick,
        first_observed_boundary=tick if observed is None else observed,
        wire=tuple(
            sorted(
                (
                    ("confidence", str(100 + revision)),
                    ("status", status),
                    ("reason", reason),
                    *wire_extra,
                )
            )
        ),
        hypothesis=HypothesisDescriptor(
            operator="combine",
            operand_refs=("item:wood",),
            process="harvest",
            predicted_outcome=predicted,
            conditions=(),
        ),
        evidence=EvidenceRef(
            kind=EvidenceKind.OWNER_ROW,
            run_id=RUN,
            tick=tick,
            owner_id=owner,
            local_id="h1",
            revision_index=revision,
        ),
    )


def _occurrence(
    *,
    tick: int = 2,
    lane: DiffusionLane = DiffusionLane.SPEECH,
    stage: DiffusionStage = DiffusionStage.DELIVERED,
    source: ScienceVersionKey | None = None,
    target: ScienceVersionKey | None = None,
    actor: str = "agent-a",
    counterparty: str = "agent-b",
    event_id: str = "evt-1",
    detail: tuple[tuple[str, str], ...] = (),
    resolution: DiffusionResolution = DiffusionResolution.CONFIRMED,
    context_flags: tuple[DiffusionContextFlag, ...] = (),
    variant: ScienceVersionKey | None = None,
    carrier_id: str | None = None,
    content_revision: int | None = None,
) -> DiffusionOccurrence:
    return DiffusionOccurrence(
        run_id=RUN,
        lane=lane,
        occurrence_kind="test",
        tick=tick,
        first_observed_boundary=tick,
        evidence=EvidenceRef(
            kind=EvidenceKind.EVENT,
            run_id=RUN,
            tick=tick,
            event_id=event_id,
            sequence=0,
        ),
        stage=stage,
        actor_id=actor,
        counterparty_id=counterparty,
        source_version=source,
        target_version=target,
        variant_version=variant,
        carrier_id=carrier_id,
        content_revision=content_revision,
        detail=detail,
        resolution=resolution,
        context_flags=context_flags,
    )


def _coverage(
    *,
    end: int = 128,
    state: LaneCoverageState = LaneCoverageState.COMPLETE,
    lanes: tuple[DiffusionLane, ...] | None = None,
) -> tuple[LaneCoverage, ...]:
    chosen = lanes or tuple(DiffusionLane)
    return tuple(
        LaneCoverage(
            lane=lane,
            start_tick=0,
            end_tick_exclusive=end,
            state=state,
            reason=(
                None
                if state is LaneCoverageState.COMPLETE
                else DiffusionReason.COVERAGE_GAP
            ),
        )
        for lane in chosen
    )


def _inputs(
    *,
    versions=(),
    occurrences=(),
    coverage=None,
) -> DiffusionInputs:
    return DiffusionInputs(
        run_id=RUN,
        versions=tuple(versions),
        occurrences=tuple(occurrences),
        coverage=coverage if coverage is not None else _coverage(),
    )


def test_configured_windows_are_absolute_and_replay_stable() -> None:
    first = _version(tick=0)
    second = _version(revision=1, tick=10, predicted="failure")
    occurrence = _occurrence(tick=12, source=second.key)
    left = derive_science_diffusion(
        _inputs(
            versions=(first, second),
            occurrences=(occurrence,),
            coverage=_coverage(end=64),
        )
    )
    right = derive_science_diffusion(
        _inputs(
            versions=(second, first),
            occurrences=(occurrence,),
            coverage=_coverage(end=64),
        )
    )
    assert left == right
    assert [row.start_tick for row in left.windows] == [0, 32]
    assert left.windows[0].complete is True


def test_confidence_only_revision_is_not_mutation() -> None:
    first = _version(revision=0)
    second = _version(revision=1, tick=4)
    assessment = derive_science_diffusion(
        _inputs(versions=(first, second), coverage=_coverage())
    )
    assert assessment.changes == ()


def test_revision_mutation_reports_changed_field_categories() -> None:
    first = _version(revision=0)
    second = _version(revision=1, tick=4, predicted="failure")
    assessment = derive_science_diffusion(
        _inputs(versions=(first, second), coverage=_coverage())
    )
    mutations = [
        row for row in assessment.changes if row.kind is DiffusionChangeKind.MUTATION
    ]
    assert len(mutations) == 1
    assert mutations[0].changed_fields == ("predicted_outcome",)


def test_divergent_reading_is_misunderstanding() -> None:
    source = _version(tick=0)
    reading = _occurrence(
        tick=5,
        lane=DiffusionLane.RECORDS,
        stage=DiffusionStage.INTERPRETED,
        source=source.key,
        carrier_id="artifact-1",
        content_revision=0,
        detail=(("divergent_read", "1"),),
    )
    assessment = derive_science_diffusion(
        _inputs(versions=(source,), occurrences=(reading,))
    )
    signals = [
        row
        for row in assessment.changes
        if row.kind is DiffusionChangeKind.MISUNDERSTANDING
    ]
    assert len(signals) == 1


def test_changed_adoption_is_misunderstanding() -> None:
    source = _version(owner="agent-a", tick=0)
    adopted = _version(
        owner="agent-b",
        tick=2,
        predicted="failure",
        reason="source_adopted",
    )
    occurrence = _occurrence(
        tick=2,
        stage=DiffusionStage.ADOPTED,
        source=source.key,
        target=adopted.key,
    )
    assessment = derive_science_diffusion(
        _inputs(versions=(source, adopted), occurrences=(occurrence,))
    )
    assert any(
        row.kind is DiffusionChangeKind.MISUNDERSTANDING for row in assessment.changes
    )


def test_explicit_retirement_and_observed_loss_confirmation() -> None:
    retired = _version(tick=5, status="retired")
    closure = CarrierClosureWitness(
        witness_boundary=5,
        holders_closed=True,
        carriers_closed=True,
        version_key=retired.key,
    )
    assessment = derive_science_diffusion(
        _inputs(versions=(retired,)),
        closure_witnesses=(closure,),
    )
    scopes = {row.scope for row in assessment.losses}
    assert DiffusionLossScope.OWNER_VERSION in scopes
    assert DiffusionLossScope.OBSERVED_LINEAGE in scopes
    observed = [
        row
        for row in assessment.losses
        if row.scope is DiffusionLossScope.OBSERVED_LINEAGE
    ]
    assert observed[0].confirmation_boundary == 3 * DIFFUSION_WINDOW_TICKS


def test_observed_loss_requires_complete_coverage() -> None:
    retired = _version(tick=5, status="retired")
    closure = CarrierClosureWitness(
        witness_boundary=5,
        holders_closed=True,
        carriers_closed=True,
        version_key=retired.key,
    )
    assessment = derive_science_diffusion(
        _inputs(
            versions=(retired,),
            coverage=_coverage(
                state=LaneCoverageState.PARTIAL,
                lanes=(
                    DiffusionLane.SCIENCE,
                    DiffusionLane.SPEECH,
                    DiffusionLane.RECORDS,
                ),
            ),
        ),
        closure_witnesses=(closure,),
    )
    assert not [
        row
        for row in assessment.losses
        if row.scope is DiffusionLossScope.OBSERVED_LINEAGE
    ]


def test_reacquisition_requires_a_linked_later_uptake() -> None:
    lost = _version(tick=0, status="retired")
    regained = _version(owner="agent-b", tick=100, observed=100)
    uptake = _occurrence(
        tick=100,
        stage=DiffusionStage.ADOPTED,
        source=lost.key,
        target=regained.key,
        actor="agent-c",
        counterparty="agent-b",
        event_id="evt-reacquire",
    )
    assessment = derive_science_diffusion(
        _inputs(versions=(lost, regained), occurrences=(uptake,))
    )
    assert any(
        row.kind is DiffusionRediscoveryKind.REACQUIRED
        for row in assessment.rediscoveries
    )


def test_independent_rediscovery_requires_root_and_complete_coverage() -> None:
    lost = _version(tick=0, status="retired")
    rediscovered = _version(owner="agent-b", tick=100, observed=100)
    root = RediscoveryRoot(
        version_key=rediscovered.key,
        root_kind="experiment",
        root_ref="evt-77",
        affirmative=True,
        committed=True,
    )
    complete = derive_science_diffusion(
        _inputs(versions=(lost, rediscovered)),
        rediscovery_roots=(root,),
    )
    assert any(
        row.kind is DiffusionRediscoveryKind.INDEPENDENT
        for row in complete.rediscoveries
    )

    partial = derive_science_diffusion(
        _inputs(
            versions=(lost, rediscovered),
            coverage=_coverage(
                state=LaneCoverageState.PARTIAL,
                lanes=(DiffusionLane.TEACHING,),
            ),
        ),
        rediscovery_roots=(root,),
    )
    assert not any(
        row.kind is DiffusionRediscoveryKind.INDEPENDENT
        for row in partial.rediscoveries
    )
    assert partial.origin_unresolved >= 1


def test_shared_root_is_origin_unresolved_not_rediscovery() -> None:
    lost = _version(tick=0, status="retired")
    rediscovered = _version(owner="agent-b", tick=100, observed=100)
    shared = RediscoveryRoot(
        version_key=rediscovered.key,
        root_kind="communicated",
        root_ref="evt-shared",
        affirmative=False,
        committed=True,
    )
    assessment = derive_science_diffusion(
        _inputs(versions=(lost, rediscovered)),
        rediscovery_roots=(shared,),
    )
    assert assessment.rediscoveries == ()
    assert assessment.origin_unresolved == 1


def test_repeated_exposure_is_counted_without_duplicate_edges() -> None:
    source = _version(tick=0)
    first = _occurrence(tick=2, source=source.key, event_id="evt-1")
    second = _occurrence(tick=3, source=source.key, event_id="evt-2")
    assessment = derive_science_diffusion(
        _inputs(versions=(source,), occurrences=(first, second))
    )
    deliveries = [
        row for row in assessment.edges if row.kind is DiffusionEdgeKind.DELIVERED
    ]
    assert len(deliveries) == 1
    assert deliveries[0].occurrence_count == 2
    assert len(assessment.transmissions) == 2


def test_translation_use_is_a_separate_change_category() -> None:
    source = _version(tick=0)
    occurrence = _occurrence(
        tick=2,
        source=source.key,
        context_flags=(DiffusionContextFlag.TRANSLATION_APPLIED,),
    )
    assessment = derive_science_diffusion(
        _inputs(versions=(source,), occurrences=(occurrence,))
    )
    assert any(
        row.kind is DiffusionChangeKind.TRANSLATION for row in assessment.changes
    )
    assert not any(
        row.kind is DiffusionChangeKind.MUTATION for row in assessment.changes
    )


def test_removing_coverage_never_increases_confirmed_losses() -> None:
    lost = _version(tick=0, status="retired")
    rediscovered = _version(owner="agent-b", tick=100, observed=100)
    root = RediscoveryRoot(
        version_key=rediscovered.key,
        root_kind="experiment",
        root_ref="evt-77",
        affirmative=True,
        committed=True,
    )
    closure = CarrierClosureWitness(
        witness_boundary=0,
        holders_closed=True,
        carriers_closed=True,
        version_key=lost.key,
    )
    complete = derive_science_diffusion(
        _inputs(versions=(lost, rediscovered)),
        closure_witnesses=(closure,),
        rediscovery_roots=(root,),
    )
    partial = derive_science_diffusion(
        _inputs(
            versions=(lost, rediscovered),
            coverage=_coverage(
                state=LaneCoverageState.PARTIAL,
                lanes=(DiffusionLane.SCIENCE, DiffusionLane.SPEECH),
            ),
        ),
        closure_witnesses=(closure,),
        rediscovery_roots=(root,),
    )
    assert len(partial.confirmed_losses) <= len(complete.confirmed_losses)
    assert len(partial.rediscoveries) <= len(complete.rediscoveries)


def test_v3_links_are_preserved_without_rewriting() -> None:
    link = V3Link(
        transmission_key="evt-1",
        v3_node_key="knowledge:agent-b:entry-1",
        origin="teaching",
        relation="teaching_uptake",
    )
    assessment = derive_science_diffusion(_inputs(), v3_links=(link,))
    assert assessment.v3_links == (link,)
