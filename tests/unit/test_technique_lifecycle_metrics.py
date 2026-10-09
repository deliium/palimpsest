"""Known-answer technique lifecycle metric families."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.models import AppliedActionRow, MetricAvailability
from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from analysis.technique_lifecycle import technique_lineage_diffusion
from analysis.technique_lifecycle_metrics import assemble_technique_lifecycle_metrics
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


def test_family_count_is_71() -> None:
    assert METRIC_FAMILY_COUNT == 71
    assert MetricFamilyId.TECHNIQUE_LIFECYCLE_STATE.value == "technique_lifecycle_state"


def test_discovered_metrics_and_empty_roots_without_rediscovery() -> None:
    docs = assemble_technique_lifecycle_metrics(
        (_audit(),),
        run_id="run-1",
        input_revision="rev-1",
        spec=example_technique_lifecycle_spec(),
        as_of_tick=2,
        applied_actions=(
            AppliedActionRow(
                tick=1,
                ordinal=0,
                agent_id="agent-a",
                action_kind="move",
                location_id="loc-1",
            ),
        ),
    )
    state = docs[0]
    assert state.availability is MetricAvailability.PRESENT
    assert state.values["discovered_count"] >= 1
    assert state.values["known_by_n_histogram"] == "1:2"
    diffusion = docs[2]
    assert diffusion.values["mean_location_spread"] == 1.0
    assert diffusion.values["mean_hop"] == 0.0
    query = technique_lineage_diffusion(
        (_audit(),),
        content_key="tech:hafting",
        as_of_tick=2,
        spec=example_technique_lifecycle_spec(),
    )
    assert query.prior_lineage_root_id == ""
    assert query.new_lineage_root_id == ""


def test_location_spread_and_living_hop_mean() -> None:
    docs = assemble_technique_lifecycle_metrics(
        (
            _audit(hop_index=0),
            _audit(
                owner_id="agent-b",
                entry_id="entry-2",
                lineage_root_id="root-1",
                origin="teaching",
                hop_index=2,
                acquired_tick=2,
            ),
        ),
        run_id="run-1",
        input_revision="rev-1",
        spec=example_technique_lifecycle_spec(),
        as_of_tick=3,
        applied_actions=(
            AppliedActionRow(
                tick=1,
                ordinal=0,
                agent_id="agent-a",
                action_kind="move",
                location_id="loc-1",
            ),
            AppliedActionRow(
                tick=2,
                ordinal=0,
                agent_id="agent-b",
                action_kind="move",
                location_id="loc-2",
            ),
        ),
    )
    diffusion = docs[2]
    assert diffusion.values["mean_location_spread"] == 2.0
    assert diffusion.values["mean_hop"] == 1.0
