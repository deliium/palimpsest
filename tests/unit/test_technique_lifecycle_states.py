"""Priority technique lifecycle state machine."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.models import AppliedActionRow
from analysis.technique_lifecycle import (
    TechniqueLifecycleState,
    TechniqueLossCause,
    classify_technique_lifecycle,
    technique_lineage_diffusion,
)
from simulation.runner_models import example_technique_lifecycle_spec


def _audit(**overrides: object) -> SimpleNamespace:
    payload: dict[str, object] = {
        "owner_id": "agent-a",
        "entry_id": "entry-1",
        "kind": "practical",
        "content_key": "tech:hafting",
        "origin": "independent_discovery",
        "lineage_root_id": "root-1",
        "hop_index": 0,
        "acquired_tick": 1,
        "tick": 1,
        "active": True,
        "parent_entry_ids": (),
        "mutated": False,
        "evidence_refs": (),
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _move(agent: str, tick: int, location: str) -> AppliedActionRow:
    return AppliedActionRow(
        tick=tick,
        ordinal=0,
        agent_id=agent,
        action_kind="move",
        location_id=location,
    )


def _global(audits, **kwargs):
    rows = classify_technique_lifecycle(
        audits,
        as_of_tick=kwargs.pop("as_of_tick", 4),
        spec=kwargs.pop("spec", example_technique_lifecycle_spec()),
        **kwargs,
    )
    return next(row for row in rows if row.scope == "global")


def test_discovered_single_holder() -> None:
    row = _global((_audit(),), applied_actions=(_move("agent-a", 1, "loc-1"),))
    assert row.state is TechniqueLifecycleState.DISCOVERED
    assert row.known_by_n == 1


def test_known_after_window() -> None:
    spec = example_technique_lifecycle_spec(diffusion_window_ticks=2)
    audits = (
        _audit(),
        _audit(
            owner_id="agent-b",
            entry_id="entry-2",
            origin="teaching",
            hop_index=1,
            acquired_tick=2,
            lineage_root_id="root-1",
        ),
    )
    row = _global(
        audits,
        as_of_tick=8,
        spec=spec,
        applied_actions=(
            _move("agent-a", 1, "loc-1"),
            _move("agent-b", 2, "loc-1"),
        ),
    )
    assert row.state is TechniqueLifecycleState.KNOWN
    assert row.known_by_n == 2


def test_diffusing_inside_window() -> None:
    audits = (
        _audit(),
        _audit(
            owner_id="agent-b",
            entry_id="entry-2",
            origin="teaching",
            hop_index=1,
            acquired_tick=3,
        ),
    )
    row = _global(
        audits,
        as_of_tick=4,
        applied_actions=(
            _move("agent-a", 1, "loc-1"),
            _move("agent-b", 3, "loc-2"),
        ),
    )
    assert row.state is TechniqueLifecycleState.DIFFUSING
    assert row.known_by_n == 2


def test_rare_after_peak() -> None:
    audits = (
        _audit(),
        _audit(owner_id="agent-b", entry_id="entry-2", acquired_tick=2),
    )
    row = _global(
        audits,
        as_of_tick=6,
        spec=example_technique_lifecycle_spec(
            diffusion_window_ticks=1, rare_max=1
        ),
        death_ticks={"agent-b": 4},
        applied_actions=(
            _move("agent-a", 1, "loc-1"),
            _move("agent-b", 2, "loc-1"),
        ),
    )
    assert row.state is TechniqueLifecycleState.RARE
    assert TechniqueLossCause.HOLDERS_DIED in row.causes


def test_record_only_rare_and_discovered() -> None:
    rare = _global(
        (
            _audit(evidence_refs=("artifact:mark-1",)),
        ),
        as_of_tick=6,
        death_ticks={"agent-a": 3},
        artifact_rows=(
            {
                "artifact_id": "mark-1",
                "integrity": "intact",
                "location_id": "loc-1",
            },
        ),
        applied_actions=(_move("agent-a", 1, "loc-1"),),
    )
    assert rare.state is TechniqueLifecycleState.RARE
    assert rare.known_by_n == 0
    discovered = _global(
        (
            _audit(
                owner_id="nobody",
                active=False,
                evidence_refs=("artifact:mark-2",),
                acquired_tick=1,
            ),
        ),
        as_of_tick=2,
        artifact_rows=(
            {
                "artifact_id": "mark-2",
                "integrity": "intact",
                "location_id": "loc-1",
            },
        ),
    )
    assert discovered.state is TechniqueLifecycleState.DISCOVERED
    assert discovered.known_by_n == 0


def test_locally_extinct_and_globally_lost() -> None:
    audits = (
        _audit(),
        _audit(
            owner_id="agent-b",
            entry_id="entry-2",
            acquired_tick=2,
            origin="teaching",
            hop_index=1,
        ),
    )
    actions = (
        _move("agent-a", 1, "loc-1"),
        _move("agent-b", 2, "loc-2"),
    )
    rows = classify_technique_lifecycle(
        audits,
        as_of_tick=6,
        spec=example_technique_lifecycle_spec(diffusion_window_ticks=1),
        death_ticks={"agent-a": 4},
        applied_actions=actions,
    )
    local = next(row for row in rows if row.scope == "location:loc-1")
    assert local.state is TechniqueLifecycleState.LOCALLY_EXTINCT
    lost = _global(
        (_audit(),),
        as_of_tick=5,
        death_ticks={"agent-a": 3},
        applied_actions=(_move("agent-a", 1, "loc-1"),),
    )
    assert lost.state is TechniqueLifecycleState.GLOBALLY_LOST
    assert TechniqueLossCause.HOLDERS_DIED in lost.causes
    assert TechniqueLossCause.MATERIALS_ABSENT not in lost.causes


def test_materials_absent_does_not_erase_living_holder() -> None:
    row = _global(
        (_audit(),),
        applied_actions=(_move("agent-a", 1, "loc-1"),),
        spec=example_technique_lifecycle_spec(
            material_anchors=(),
        ),
    )
    assert row.state is not TechniqueLifecycleState.GLOBALLY_LOST
    assert row.performable is None


def test_teaching_chain_failed_and_lone_root() -> None:
    failed = _global(
        (
            _audit(origin="teaching", hop_index=1, acquired_tick=1),
        ),
        as_of_tick=5,
        death_ticks={"agent-a": 3},
        applied_actions=(_move("agent-a", 1, "loc-1"),),
    )
    assert TechniqueLossCause.TEACHING_CHAIN_FAILED in failed.causes
    lone = _global(
        (_audit(),),
        as_of_tick=5,
        death_ticks={"agent-a": 3},
        applied_actions=(_move("agent-a", 1, "loc-1"),),
    )
    assert TechniqueLossCause.TEACHING_CHAIN_FAILED not in lone.causes


def test_rediscovery_after_loss_keeps_new_root() -> None:
    audits = (
        _audit(acquired_tick=1),
        _audit(
            owner_id="agent-c",
            entry_id="entry-3",
            origin="independent_discovery",
            lineage_root_id="root-2",
            hop_index=0,
            acquired_tick=6,
        ),
    )
    row = _global(
        audits,
        as_of_tick=7,
        spec=example_technique_lifecycle_spec(rediscovery_latch_ticks=4),
        death_ticks={"agent-a": 3},
        applied_actions=(
            _move("agent-a", 1, "loc-1"),
            _move("agent-c", 6, "loc-1"),
        ),
    )
    assert row.state is TechniqueLifecycleState.REDISCOVERED
    assert row.new_lineage_root_id == "root-2"
    assert row.prior_lineage_root_id == "root-1"
    query = technique_lineage_diffusion(
        audits,
        content_key="tech:hafting",
        as_of_tick=7,
        spec=example_technique_lifecycle_spec(rediscovery_latch_ticks=4),
        death_ticks={"agent-a": 3},
        applied_actions=(
            _move("agent-a", 1, "loc-1"),
            _move("agent-c", 6, "loc-1"),
        ),
    )
    assert query.new_lineage_root_id == "root-2"


def test_dual_emergence_is_not_rediscovered() -> None:
    audits = (
        _audit(),
        _audit(
            owner_id="agent-b",
            entry_id="entry-2",
            lineage_root_id="root-2",
            acquired_tick=2,
        ),
    )
    row = _global(
        audits,
        as_of_tick=3,
        applied_actions=(
            _move("agent-a", 1, "loc-1"),
            _move("agent-b", 2, "loc-1"),
        ),
    )
    assert row.state is not TechniqueLifecycleState.REDISCOVERED


def test_latch_expiry_blocks_discovered() -> None:
    audits = (
        _audit(acquired_tick=1),
        _audit(
            owner_id="agent-c",
            entry_id="entry-3",
            lineage_root_id="root-2",
            acquired_tick=6,
        ),
    )
    row = _global(
        audits,
        as_of_tick=20,
        spec=example_technique_lifecycle_spec(
            rediscovery_latch_ticks=2, diffusion_window_ticks=1
        ),
        death_ticks={"agent-a": 3},
        applied_actions=(
            _move("agent-a", 1, "loc-1"),
            _move("agent-c", 6, "loc-1"),
        ),
    )
    assert row.state is not TechniqueLifecycleState.DISCOVERED
    assert row.state is not TechniqueLifecycleState.REDISCOVERED
