# mypy: ignore-errors
"""V4-33 diffusion contract: qualified keys, comparisons, coverage, caps."""

from __future__ import annotations

import json

import pytest

from analysis.science_diffusion_contract import (
    DIFFUSION_WINDOW_TICKS,
    MAX_DIFFUSION_EVENTS,
    MAX_DIFFUSION_INPUT_ROWS,
    MAX_DIFFUSION_OWNERS,
    MAX_DIFFUSION_TICKS,
    MAX_DIFFUSION_WINDOWS,
    DiffusionAccumulator,
    DiffusionContextFlag,
    DiffusionError,
    DiffusionInputs,
    DiffusionLane,
    DiffusionLayer,
    DiffusionOccurrence,
    DiffusionReason,
    DiffusionResolution,
    DiffusionStage,
    EvidenceKind,
    EvidenceRef,
    HypothesisDescriptor,
    LaneCoverage,
    LaneCoverageState,
    ModelDescriptor,
    ScienceKind,
    ScienceVersion,
    ScienceVersionKey,
    StagedDiffusionBoundary,
    canonical_fingerprint,
    compare_science_versions,
    require_capture_plan,
    require_diffusion_window_index,
    require_input_row_cap,
    require_source_prior,
)

pytestmark = pytest.mark.unit

RUN = "run-sdf"
OWNER = "agent-a"
OTHER = "agent-b"


def _owner_row(tick: int = 0) -> EvidenceRef:
    return EvidenceRef(
        kind=EvidenceKind.OWNER_ROW,
        run_id=RUN,
        tick=tick,
        owner_id=OWNER,
        local_id="h1",
        revision_index=0,
    )


def _event(tick: int = 0, sequence: int = 0, event_id: str = "evt-1") -> EvidenceRef:
    return EvidenceRef(
        kind=EvidenceKind.EVENT,
        run_id=RUN,
        tick=tick,
        event_id=event_id,
        sequence=sequence,
    )


def _hypothesis(
    *,
    predicted_outcome: str | None = "STRIKE_SUCCESS",
    operands: tuple[str, ...] = ("resource:grain",),
    conditions: tuple[tuple[str, str], ...] = (("season", "summer"),),
) -> HypothesisDescriptor:
    return HypothesisDescriptor(
        operator="STRIKE",
        operand_refs=operands,
        process="process:harvest",
        predicted_outcome=predicted_outcome,
        conditions=conditions,
    )


def _version(
    *,
    revision: int = 0,
    kind: ScienceKind = ScienceKind.HYPOTHESIS,
    hypothesis: HypothesisDescriptor | None = None,
    model: ModelDescriptor | None = None,
    tick: int = 0,
    observed: int | None = None,
    wire: tuple[tuple[str, str], ...] = (("confidence", "100"),),
    owner: str = OWNER,
) -> ScienceVersion:
    observed_value = tick if observed is None else observed
    key = ScienceVersionKey(
        run_id=RUN,
        owner_id=owner,
        kind=kind,
        local_id="h1" if kind is ScienceKind.HYPOTHESIS else "m1",
        revision_index=revision,
    )
    if kind is ScienceKind.HYPOTHESIS and hypothesis is None:
        hypothesis = _hypothesis()
    return ScienceVersion(
        key=key,
        occurrence_tick=tick,
        first_observed_boundary=observed_value,
        wire=wire,
        hypothesis=hypothesis,
        model=model,
        evidence=EvidenceRef(
            kind=EvidenceKind.OWNER_ROW,
            run_id=RUN,
            tick=tick,
            owner_id=owner,
            local_id=key.local_id,
            revision_index=revision,
        ),
    )


def _occurrence(
    *,
    tick: int = 1,
    lane: DiffusionLane = DiffusionLane.SPEECH,
    source: ScienceVersionKey | None = None,
    first_observed: int | None = None,
    confirmation: int | None = None,
    stage: DiffusionStage = DiffusionStage.DELIVERED,
    resolution: DiffusionResolution = DiffusionResolution.CONFIRMED,
    reason: DiffusionReason | None = None,
    sequence: int = 0,
    detail: tuple[tuple[str, str], ...] = (),
) -> DiffusionOccurrence:
    observed = tick if first_observed is None else first_observed
    return DiffusionOccurrence(
        run_id=RUN,
        lane=lane,
        occurrence_kind="test_occurrence",
        tick=tick,
        first_observed_boundary=observed,
        evidence=_event(tick=tick, sequence=sequence),
        stage=stage,
        confirmation_boundary=confirmation,
        actor_id=OWNER,
        counterparty_id=OTHER,
        source_version=source,
        detail=detail,
        resolution=resolution,
        reason=reason,
    )


def test_constants_and_closed_enums_are_exact() -> None:
    assert DIFFUSION_WINDOW_TICKS == 32
    assert MAX_DIFFUSION_TICKS == 512
    assert MAX_DIFFUSION_WINDOWS == 16
    assert MAX_DIFFUSION_OWNERS == 128
    assert MAX_DIFFUSION_EVENTS == 32_768
    assert MAX_DIFFUSION_INPUT_ROWS == 16_384
    assert tuple(item.value for item in DiffusionLane) == (
        "science",
        "speech",
        "teaching",
        "records",
        "knowledge_genealogy",
        "organizations",
        "migration",
        "societies",
        "translation",
    )
    assert tuple(item.value for item in LaneCoverageState) == (
        "complete",
        "partial",
        "unavailable",
    )
    assert tuple(item.value for item in DiffusionLayer) == (
        "objective_occurrence",
        "owner_evidence",
        "analytical_association",
    )
    assert tuple(item.value for item in DiffusionStage) == (
        "delivered",
        "interpreted",
        "adopted",
        "locally_derived",
        "reported_reference",
        "carried",
    )
    assert tuple(item.value for item in DiffusionResolution) == (
        "confirmed",
        "unresolved",
        "ambiguous",
        "excluded",
    )


def test_unknown_enum_values_are_rejected() -> None:
    with pytest.raises(DiffusionError) as lane:
        DiffusionOccurrence(
            run_id=RUN,
            lane="unknown",  # type: ignore[arg-type]
            occurrence_kind="x",
            tick=1,
            first_observed_boundary=1,
            evidence=_event(tick=1),
            stage=DiffusionStage.DELIVERED,
        )
    assert lane.value.reason_code == DiffusionReason.UNSUPPORTED_SCHEMA.value

    with pytest.raises(DiffusionError) as state:
        LaneCoverage(
            lane=DiffusionLane.SPEECH,
            start_tick=0,
            end_tick_exclusive=1,
            state="done",  # type: ignore[arg-type]
        )
    assert state.value.reason_code == DiffusionReason.UNSUPPORTED_SCHEMA.value


def test_ordered_operands_are_preserved_and_comparison_is_order_sensitive() -> None:
    forward = _hypothesis(operands=("resource:grain", "resource:tool"))
    reverse = _hypothesis(operands=("resource:tool", "resource:grain"))
    assert forward.operand_refs == ("resource:grain", "resource:tool")
    left = _version(hypothesis=forward)
    right = _version(hypothesis=reverse)
    assert compare_science_versions(left, right) == ("operand_refs",)
    assert left.content_fingerprint() != right.content_fingerprint()


def test_unknown_field_is_not_a_wildcard_or_absent_operand() -> None:
    unknown = _version(hypothesis=_hypothesis(predicted_outcome=None))
    known = _version(hypothesis=_hypothesis(predicted_outcome="STRIKE_SUCCESS"))
    assert compare_science_versions(unknown, known) == ("predicted_outcome",)

    absent = _version(hypothesis=_hypothesis(operands=("resource:grain",)))
    present = _version(
        hypothesis=_hypothesis(operands=("resource:grain", "resource:tool"))
    )
    assert "operand_refs" in compare_science_versions(absent, present)


def test_operator_must_be_a_concrete_typed_reference() -> None:
    with pytest.raises(DiffusionError):
        HypothesisDescriptor(
            operator="STRIKE",
            operand_refs=("grain",),
            process="process:harvest",
        )


def test_same_tick_requires_exact_causal_ordering() -> None:
    with pytest.raises(DiffusionError) as unordered:
        require_source_prior(source_tick=4, target_tick=4)
    assert unordered.value.reason_code == DiffusionReason.SOURCE_NOT_PRIOR.value

    require_source_prior(
        source_tick=4,
        target_tick=4,
        source_sequence=2,
        target_sequence=3,
        causal_evidence=True,
    )

    with pytest.raises(DiffusionError):
        require_source_prior(
            source_tick=4,
            target_tick=4,
            source_sequence=3,
            target_sequence=2,
            causal_evidence=True,
        )


def test_occurrence_cannot_be_observed_before_it_occurs() -> None:
    with pytest.raises(DiffusionError) as exc:
        _occurrence(tick=5, first_observed=4)
    assert exc.value.reason_code == DiffusionReason.SOURCE_NOT_PRIOR.value


def test_confirmation_cannot_precede_first_observation() -> None:
    with pytest.raises(DiffusionError):
        _occurrence(tick=2, first_observed=3, confirmation=2)


def test_duplicate_qualified_keys_must_match_exactly() -> None:
    first = _version()
    identical = _version()
    inputs = DiffusionInputs(
        run_id=RUN,
        versions=(first, identical),
        occurrences=(),
        coverage=(),
    )
    assert inputs.versions == (first,)

    changed = _version(hypothesis=_hypothesis(predicted_outcome="OTHER"))
    with pytest.raises(DiffusionError) as exc:
        DiffusionInputs(
            run_id=RUN,
            versions=(first, changed),
            occurrences=(),
            coverage=(),
        )
    assert exc.value.reason_code == DiffusionReason.IDENTITY_CONFLICT.value


def test_foreign_and_cross_run_references_are_rejected() -> None:
    version = _version()
    stranger = ScienceVersionKey(
        run_id="other-run",
        owner_id=OWNER,
        kind=ScienceKind.HYPOTHESIS,
        local_id="h1",
        revision_index=0,
    )
    with pytest.raises(DiffusionError) as exc:
        DiffusionInputs(
            run_id=RUN,
            versions=(version,),
            occurrences=(_occurrence(tick=3, source=stranger),),
            coverage=(),
        )
    assert exc.value.reason_code == DiffusionReason.IDENTITY_CONFLICT.value

    with pytest.raises(DiffusionError) as evidence:
        DiffusionInputs(
            run_id=RUN,
            versions=(version,),
            occurrences=(
                DiffusionOccurrence(
                    run_id=RUN,
                    lane=DiffusionLane.SPEECH,
                    occurrence_kind="test_occurrence",
                    tick=3,
                    first_observed_boundary=3,
                    evidence=EvidenceRef(
                        kind=EvidenceKind.EVENT,
                        run_id="other-run",
                        tick=2,
                        event_id="evt-9",
                        sequence=0,
                    ),
                    stage=DiffusionStage.DELIVERED,
                ),
            ),
            coverage=(),
        )
    assert evidence.value.reason_code == DiffusionReason.IDENTITY_CONFLICT.value


def test_source_version_must_precede_delivery() -> None:
    version = _version(tick=3)
    with pytest.raises(DiffusionError) as exc:
        DiffusionInputs(
            run_id=RUN,
            versions=(version,),
            occurrences=(_occurrence(tick=3, source=version.key),),
            coverage=(),
        )
    assert exc.value.reason_code == DiffusionReason.SOURCE_NOT_PRIOR.value

    prior = _version(tick=2)
    inputs = DiffusionInputs(
        run_id=RUN,
        versions=(prior,),
        occurrences=(_occurrence(tick=3, source=prior.key),),
        coverage=(),
    )
    assert len(inputs.occurrences) == 1


def test_deterministic_permutations_produce_equal_inputs() -> None:
    first = _version(tick=0)
    second = _version(revision=1, tick=1, hypothesis=_hypothesis())
    occ = _occurrence(tick=2, source=second.key)
    coverage = (
        LaneCoverage(
            lane=DiffusionLane.SPEECH,
            start_tick=0,
            end_tick_exclusive=4,
            state=LaneCoverageState.COMPLETE,
        ),
        LaneCoverage(
            lane=DiffusionLane.RECORDS,
            start_tick=0,
            end_tick_exclusive=4,
            state=LaneCoverageState.COMPLETE,
        ),
    )
    left = DiffusionInputs(
        run_id=RUN,
        versions=(first, second),
        occurrences=(occ,),
        coverage=coverage,
    )
    right = DiffusionInputs(
        run_id=RUN,
        versions=(second, first),
        occurrences=(occ,),
        coverage=tuple(reversed(coverage)),
    )
    assert left == right
    assert [item.key for item in left.versions] == sorted(
        (first.key, second.key), key=lambda item: item.as_tuple()
    )


def test_confidence_only_wire_change_preserves_content_fingerprint() -> None:
    quiet = _version(wire=(("confidence", "100"),))
    loud = _version(wire=(("confidence", "900"), ("confidence_trend", "up")))
    assert quiet.content_fingerprint() == loud.content_fingerprint()
    assert compare_science_versions(quiet, loud) == ()


def test_model_parameter_digest_requires_equal_descriptor_scope() -> None:
    def model(scope: str, digest: str) -> ModelDescriptor:
        return ModelDescriptor(
            target_kind="resource_amount",
            target_ref="resource:grain",
            unit="unit:quantity",
            horizon=2,
            variant="baseline",
            conditions=(("season", "summer"),),
            predicted_class="high",
            parameter_digest=digest,
            parameter_scope=scope,
        )

    left = _version(
        kind=ScienceKind.MODEL, hypothesis=None, model=model("scope-a", "digest-a")
    )
    right = _version(
        kind=ScienceKind.MODEL, hypothesis=None, model=model("scope-a", "digest-b")
    )
    assert compare_science_versions(left, right) == ("parameter_digest",)

    other_scope = _version(
        kind=ScienceKind.MODEL,
        hypothesis=None,
        model=model("scope-b", "digest-b"),
    )
    assert "parameter_scope" in compare_science_versions(left, other_scope)


def test_complete_empty_is_distinct_from_unavailable() -> None:
    empty = DiffusionInputs(
        run_id=RUN,
        versions=(),
        occurrences=(),
        coverage=(
            LaneCoverage(
                lane=DiffusionLane.SPEECH,
                start_tick=0,
                end_tick_exclusive=4,
                state=LaneCoverageState.COMPLETE,
                observed=0,
            ),
        ),
    )
    assert empty.lane_state(DiffusionLane.SPEECH) is LaneCoverageState.COMPLETE
    assert empty.lane_state(DiffusionLane.RECORDS) is LaneCoverageState.UNAVAILABLE


def test_unresolved_occurrence_does_not_change_lane_availability() -> None:
    inputs = DiffusionInputs(
        run_id=RUN,
        versions=(),
        occurrences=(
            _occurrence(
                resolution=DiffusionResolution.UNRESOLVED,
                reason=DiffusionReason.UNVERIFIED_REFERENCE,
            ),
        ),
        coverage=(
            LaneCoverage(
                lane=DiffusionLane.SPEECH,
                start_tick=0,
                end_tick_exclusive=4,
                state=LaneCoverageState.COMPLETE,
            ),
        ),
    )
    assert inputs.lane_state(DiffusionLane.SPEECH) is LaneCoverageState.COMPLETE


def test_coverage_intervals_are_half_open_and_must_not_overlap() -> None:
    row = LaneCoverage(
        lane=DiffusionLane.RECORDS,
        start_tick=0,
        end_tick_exclusive=2,
        state=LaneCoverageState.COMPLETE,
    )
    assert row.covers(1) and not row.covers(2)
    with pytest.raises(DiffusionError) as exc:
        DiffusionInputs(
            run_id=RUN,
            versions=(),
            occurrences=(),
            coverage=(
                row,
                LaneCoverage(
                    lane=DiffusionLane.RECORDS,
                    start_tick=1,
                    end_tick_exclusive=3,
                    state=LaneCoverageState.COMPLETE,
                ),
            ),
        )
    assert exc.value.reason_code == DiffusionReason.COVERAGE_GAP.value


def test_partial_and_unavailable_coverage_require_a_reason() -> None:
    with pytest.raises(DiffusionError):
        LaneCoverage(
            lane=DiffusionLane.SPEECH,
            start_tick=0,
            end_tick_exclusive=1,
            state=LaneCoverageState.PARTIAL,
        )
    with pytest.raises(DiffusionError):
        LaneCoverage(
            lane=DiffusionLane.SPEECH,
            start_tick=0,
            end_tick_exclusive=1,
            state=LaneCoverageState.COMPLETE,
            reason=DiffusionReason.COVERAGE_GAP,
        )


def test_documented_caps_fail_closed() -> None:
    require_capture_plan(
        committed_ticks=MAX_DIFFUSION_TICKS,
        owner_count=MAX_DIFFUSION_OWNERS,
        cumulative_events=MAX_DIFFUSION_EVENTS,
    )
    for kwargs in (
        {"committed_ticks": MAX_DIFFUSION_TICKS + 1},
        {"owner_count": MAX_DIFFUSION_OWNERS + 1},
        {"cumulative_events": MAX_DIFFUSION_EVENTS + 1},
    ):
        payload = {
            "committed_ticks": 1,
            "owner_count": 1,
            "cumulative_events": 1,
            **kwargs,
        }
        with pytest.raises(DiffusionError) as exc:
            require_capture_plan(**payload)
        assert exc.value.reason_code == DiffusionReason.LIMIT_REACHED.value
    with pytest.raises(DiffusionError):
        require_input_row_cap(MAX_DIFFUSION_INPUT_ROWS + 1)
    with pytest.raises(DiffusionError):
        require_diffusion_window_index(MAX_DIFFUSION_WINDOWS)


def test_accumulator_discards_whole_overflowing_boundary_and_seals_tail() -> None:
    accumulator = DiffusionAccumulator(RUN, max_rows=12)
    first = StagedDiffusionBoundary(boundary_tick=1, occurrences=(_occurrence(tick=1),))
    assert accumulator.stage(first)
    assert accumulator.row_count == 1

    overflow = StagedDiffusionBoundary(
        boundary_tick=2,
        occurrences=tuple(
            _occurrence(tick=2, sequence=index) for index in range(4)
        ),
    )
    assert not accumulator.stage(overflow)
    assert accumulator.sealed is DiffusionReason.LIMIT_REACHED
    assert not accumulator.stage(
        StagedDiffusionBoundary(boundary_tick=3, occurrences=(_occurrence(tick=3),))
    )
    versions, occurrences, coverage = accumulator.results()
    assert versions == ()
    assert len(occurrences) == 1
    assert {row.lane for row in coverage} == set(DiffusionLane)
    assert all(row.state is LaneCoverageState.PARTIAL for row in coverage)


def test_tokens_and_fingerprints_are_deterministic_and_domain_separated() -> None:
    key = ScienceVersionKey(
        run_id=RUN,
        owner_id=OWNER,
        kind=ScienceKind.HYPOTHESIS,
        local_id="h1",
        revision_index=0,
    )
    assert key.token() == key.token()
    assert key.token().startswith("sdf:")
    assert key.token() != ScienceVersionKey(
        run_id="run-other",
        owner_id=OWNER,
        kind=ScienceKind.HYPOTHESIS,
        local_id="h1",
        revision_index=0,
    ).token()
    payload = {"b": [1, 2], "a": "x"}
    assert canonical_fingerprint("one", payload) == canonical_fingerprint(
        "one", payload
    )
    assert canonical_fingerprint("one", payload) != canonical_fingerprint(
        "two", payload
    )
    assert json.loads(json.dumps(payload)) == payload


def test_context_flags_are_sorted_and_unique() -> None:
    occurrence = DiffusionOccurrence(
        run_id=RUN,
        lane=DiffusionLane.ORGANIZATIONS,
        occurrence_kind="test_occurrence",
        tick=1,
        first_observed_boundary=1,
        evidence=_event(tick=1),
        stage=DiffusionStage.DELIVERED,
        context_flags=(
            DiffusionContextFlag.ORGANIZATION_MEDIATED,
            DiffusionContextFlag.SHARED_ORG_CONTEXT,
        ),
    )
    assert occurrence.context_flags == (
        DiffusionContextFlag.ORGANIZATION_MEDIATED,
        DiffusionContextFlag.SHARED_ORG_CONTEXT,
    )
    with pytest.raises(DiffusionError):
        DiffusionOccurrence(
            run_id=RUN,
            lane=DiffusionLane.ORGANIZATIONS,
            occurrence_kind="test_occurrence",
            tick=1,
            first_observed_boundary=1,
            evidence=_event(tick=1),
            stage=DiffusionStage.DELIVERED,
            context_flags=(
                DiffusionContextFlag.ORGANIZATION_MEDIATED,
                DiffusionContextFlag.ORGANIZATION_MEDIATED,
            ),
        )
