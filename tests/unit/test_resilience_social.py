# mypy: ignore-errors
"""Owner-scoped and distributional resilience reducer coverage."""

from __future__ import annotations

from analysis.resilience_social import SocialReduceInputs, reduce_social
from analysis.resilience_windows import (
    ShockReceipt,
    WindowCoverage,
    WindowReason,
    build_shock_windows,
)
from simulation.resilience_evidence import (
    OwnerLaneState,
    ResilienceBatchEvents,
    ResilienceBodyRow,
    ResilienceBoundaryFacts,
    ResilienceFeedRow,
    ResilienceHelpRow,
    ResilienceOwnerKeys,
    ResilienceProjectContributionRow,
)

pytestmark = __import__("pytest").mark.unit


def _windows_for(shock_tick: int = 8, *, through: int = 80):
    built = build_shock_windows(
        (
            ShockReceipt(
                tick=shock_tick,
                sequence=0,
                event_id="shock",
                kind="drought",
                origin="spontaneous",
                outcome="applied",
                rule_id="r1",
            ),
        ),
        run_id="run-a",
        finalized_through=through,
        capture_through=through,
        schedule=(),
    )
    return built.episodes[0], built.episodes[0].windows


def _body(body_id: str, *, living: bool = True, held: int = 0) -> ResilienceBodyRow:
    return ResilienceBodyRow(
        body_id=body_id,
        agent_id=f"agent-{body_id}",
        living=living,
        held_item_count=held,
        region_id=None,
    )


def _owner(
    body_id: str,
    *,
    living: bool = True,
    institution: OwnerLaneState = OwnerLaneState.COMPLETE,
    knowledge: OwnerLaneState = OwnerLaneState.COMPLETE,
    concepts: tuple[str, ...] = (),
    contents: tuple[str, ...] = (),
) -> ResilienceOwnerKeys:
    return ResilienceOwnerKeys(
        agent_id=f"agent-{body_id}",
        body_id=body_id,
        living=living,
        institution_state=institution,
        knowledge_state=knowledge,
        recognized_concept_ids=concepts,
        active_content_keys=contents,
    )


def _frame(
    boundary: int,
    *,
    bodies: tuple[ResilienceBodyRow, ...] = (),
    owners: tuple[ResilienceOwnerKeys, ...] = (),
) -> ResilienceBoundaryFacts:
    return ResilienceBoundaryFacts(
        run_id="run-a",
        config_fingerprint="fp",
        boundary_tick=boundary,
        revision=boundary,
        body_projection_hash=None if boundary == 0 else "hash",
        history_length=0,
        infrastructure_channel=OwnerLaneState.OFF,
        ecology_channel=OwnerLaneState.OFF,
        bodies=bodies,
        stocks=(),
        infrastructure=(),
        owners=owners,
    )


def test_institution_continuity_fading_replacement_and_death() -> None:
    episode, windows = _windows_for()
    # Baseline at boundary 8: owner a recognizes c1.
    base_owners = (_owner("a", concepts=("c1",)),)
    # Post0 at 16: a dead; b recognizes c1 (replacement ID, not continuity).
    post_owners = (
        _owner("a", living=False, concepts=()),
        _owner("b", concepts=("c1",)),
    )
    frames = {
        8: _frame(8, bodies=(_body("a"),), owners=base_owners),
        16: _frame(
            16,
            bodies=(_body("a", living=False), _body("b")),
            owners=post_owners,
        ),
    }
    for b in range(0, 81, 8):
        frames.setdefault(b, _frame(b, bodies=(_body("a"),), owners=base_owners))
    frames[16] = _frame(
        16,
        bodies=(_body("a", living=False), _body("b")),
        owners=post_owners,
    )
    inputs = SocialReduceInputs(
        frames_by_boundary=frames,
        batches=(),
        projects_enabled=True,
    )
    inst = reduce_social(inputs, episode, windows)[0].windows[1]
    by_metric = {m.metric: m for m in inst.measures}
    assert by_metric["recognized_owner_concepts"].value == 1
    assert by_metric["baseline_recognized_owner_concepts"].value == 1
    assert by_metric["baseline_concepts_still_recognized"].value == 0
    assert by_metric["recognized_continuity_milli"].value == 0


def test_knowledge_retention_vs_cross_owner_technology() -> None:
    episode, windows = _windows_for()
    base = (_owner("a", contents=("tech-1", "tech-2")),)
    # a loses tech-1; b gains tech-1 → knowledge pair lost, technique key survives.
    post = (
        _owner("a", contents=("tech-2",)),
        _owner("b", contents=("tech-1",)),
    )
    frames = {
        8: _frame(8, bodies=(_body("a"),), owners=base),
        16: _frame(16, bodies=(_body("a"), _body("b")), owners=post),
    }
    for b in range(0, 81, 8):
        frames.setdefault(b, _frame(b, bodies=(_body("a"),), owners=base))
    frames[16] = _frame(16, bodies=(_body("a"), _body("b")), owners=post)
    inputs = SocialReduceInputs(
        frames_by_boundary=frames, batches=(), projects_enabled=False
    )
    knowledge, technology = reduce_social(inputs, episode, windows)[1:3]
    k = {m.metric: m for m in knowledge.windows[1].measures}
    assert k["active_owner_contents"].value == 2
    assert k["baseline_owner_contents_retained"].value == 1
    assert k["owner_content_retention_milli"].value == 500
    t = {m.metric: m for m in technology.windows[1].measures}
    assert t["living_technique_keys"].value == 2
    assert t["baseline_technique_keys_missing"].value == 0


def test_unsupported_living_source_marks_partial_with_coverage() -> None:
    episode, windows = _windows_for()
    base = (_owner("a", contents=("tech-1",), concepts=("c1",)),)
    post = (
        _owner(
            "a",
            institution=OwnerLaneState.UNSUPPORTED,
            knowledge=OwnerLaneState.UNSUPPORTED,
            concepts=(),
            contents=(),
        ),
    )
    frames = {
        8: _frame(8, bodies=(_body("a"),), owners=base),
        16: _frame(16, bodies=(_body("a"),), owners=post),
    }
    for b in range(0, 81, 8):
        frames.setdefault(b, _frame(b, bodies=(_body("a"),), owners=base))
    frames[16] = _frame(16, bodies=(_body("a"),), owners=post)
    inputs = SocialReduceInputs(
        frames_by_boundary=frames, batches=(), projects_enabled=False
    )
    inst = reduce_social(inputs, episode, windows)[0].windows[1]
    assert inst.status is WindowCoverage.PARTIAL
    assert inst.reason is WindowReason.PROJECTION_GAP
    assert inst.owner_coverage is not None
    assert inst.owner_coverage.eligible_owners == 1
    assert inst.owner_coverage.observed_owners == 0
    assert inst.measures == ()


def test_technology_two_point_absence_and_gap_break() -> None:
    episode, windows = _windows_for()
    with_tech = (_owner("a", contents=("tech-1",)),)
    without = (_owner("a", contents=()),)
    frames: dict[int, ResilienceBoundaryFacts] = {}
    for b in range(0, 81, 8):
        frames[b] = _frame(b, bodies=(_body("a"),), owners=with_tech)
    frames[8] = _frame(8, bodies=(_body("a"),), owners=with_tech)
    frames[16] = _frame(16, bodies=(_body("a"),), owners=without)
    frames[24] = _frame(24, bodies=(_body("a"),), owners=without)
    # Drop boundary 32 → gap breaks adjacency for later absences.
    del frames[32]
    frames[40] = _frame(40, bodies=(_body("a"),), owners=without)
    frames[48] = _frame(48, bodies=(_body("a"),), owners=without)
    inputs = SocialReduceInputs(
        frames_by_boundary=frames, batches=(), projects_enabled=False
    )
    tech = reduce_social(inputs, episode, windows)[2]
    post0 = {m.metric: m for m in tech.windows[1].measures}
    post1 = {m.metric: m for m in tech.windows[2].measures}
    assert post0["baseline_technique_keys_missing"].value == 1
    assert post0["baseline_technique_keys_missing_two_points"].value is None
    assert post1["baseline_technique_keys_missing_two_points"].value == 1
    assert tech.windows[3].status is WindowCoverage.PARTIAL
    # First complete post after the gap cannot claim two-point continuity.
    post3 = {m.metric: m for m in tech.windows[4].measures}
    assert post3["baseline_technique_keys_missing_two_points"].value is None
    # A second consecutive complete absence after the gap can.
    post4 = {m.metric: m for m in tech.windows[5].measures}
    assert post4["baseline_technique_keys_missing_two_points"].value == 1


def test_cooperation_rates_and_projects_off() -> None:
    episode, windows = _windows_for()
    bodies = (_body("a"), _body("b"))
    frames = {
        b: _frame(b, bodies=bodies, owners=()) for b in range(0, 17)
    }
    for b in range(0, 81, 8):
        frames.setdefault(b, _frame(b, bodies=bodies, owners=()))
    batches = (
        ResilienceBatchEvents(
            tick=9,
            resulting_revision=10,
            deaths=(),
            journey_arrivals=(),
            helps=(
                ResilienceHelpRow(
                    event_id="h1",
                    tick=9,
                    sequence=0,
                    actor_body_id="a",
                    target_body_id="b",
                ),
            ),
            feeds=(
                ResilienceFeedRow(
                    event_id="f1",
                    tick=9,
                    sequence=1,
                    actor_body_id="a",
                    target_body_id="b",
                ),
            ),
            contributions=(
                ResilienceProjectContributionRow(
                    event_id="p1",
                    tick=9,
                    sequence=2,
                    actor_body_id="a",
                    project_id="proj-1",
                ),
            ),
            exchanges=(),
            shock_receipts=(),
            event_count=3,
        ),
    )
    off = SocialReduceInputs(
        frames_by_boundary=frames, batches=batches, projects_enabled=False
    )
    coop = reduce_social(off, episode, windows)[3].windows[1]
    by_metric = {m.metric: m for m in coop.measures}
    assert by_metric["helps"].value == 1
    assert by_metric["feeds"].value == 1
    assert by_metric["person_ticks"].value == 16  # 8 ticks * 2 living
    assert by_metric["helps_per_person_tick_milli"].value == 1000 // 16
    assert by_metric["contributions"].value is None
    assert by_metric["contributions"].reason == "channel_off"


def test_inequality_gini_samples() -> None:
    episode, windows = _windows_for()
    frames = {
        8: _frame(8, bodies=(_body("a", held=0), _body("b", held=2))),
        16: _frame(16, bodies=(_body("a", held=0), _body("b", held=0))),
    }
    for b in range(0, 81, 8):
        frames.setdefault(
            b, _frame(b, bodies=(_body("a", held=0), _body("b", held=2)))
        )
    frames[16] = _frame(16, bodies=(_body("a", held=0), _body("b", held=0)))
    inputs = SocialReduceInputs(
        frames_by_boundary=frames, batches=(), projects_enabled=False
    )
    ineq = reduce_social(inputs, episode, windows)[4]
    base = {m.metric: m for m in ineq.windows[0].measures}
    post = {m.metric: m for m in ineq.windows[1].measures}
    assert base["held_item_gini_milli"].value == 500
    assert post["held_item_gini_milli"].value == 0
    single = {
        b: _frame(b, bodies=(_body("a", held=3),)) for b in range(0, 81, 8)
    }
    single_inputs = SocialReduceInputs(
        frames_by_boundary=single, batches=(), projects_enabled=False
    )
    single_cell = reduce_social(single_inputs, episode, windows)[4].windows[1]
    assert {m.metric: m for m in single_cell.measures}[
        "held_item_gini_milli"
    ].value is None
