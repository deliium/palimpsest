"""Deterministic organization identities, analysis, and publications."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import AgentId
from analysis import (
    OrganizationCandidate,
    OrganizationCandidateStatus,
    OrganizationCoverage,
    OrganizationDetectionResult,
    OrganizationIdentityAssignment,
    OrganizationLineageEdge,
    OrganizationLineageKind,
    OrganizationTemporalScope,
    OrganizationWindowResult,
    assign_organization_identities,
    derive_organization_id,
    derive_organization_lineage,
    validate_organization_lineage,
)
from experiments import (
    build_organization_harvest_result,
    publish_organization_snapshot,
)
from experiments.catalog import base_runner_config_from_scenario
from persistence.organization_filesystem import create_organization_publisher
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _config() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace_config(
        base_runner_config_from_scenario(
            seed=11,
            stochastic_identity="cmp-v4-organization-determinism",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-v4-organization-determinism"),
                revision=WorldRevision(0),
                physical_rules=default_physical_rules(),
                locations=(make_location(),),
                bodies=(body,),
                weather=(make_weather(),),
            ),
            agents=(
                AgentRunnerSpec(
                    agent_id=agent_id,
                    entity_id=body.entity_id,
                    cognition=AgentCognitionSpec(agent_id=agent_id),
                ),
            ),
            max_ticks=2,
        )
    )


def replace_config(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    from dataclasses import replace

    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(organizations=True),
    )


def _candidate(
    key: str,
    window: int,
    members: tuple[str, ...],
    anchors: tuple[str, ...],
) -> OrganizationCandidate:
    return OrganizationCandidate(
        candidate_key=key,
        window_index=window,
        member_ids=tuple(sorted(members)),
        member_claims=(),
        role_anchor_ids=(),
        goal_anchor_ids=tuple(sorted(anchors)),
        resource_anchor_ids=(),
        procedure_anchor_ids=(),
        record_anchor_ids=(),
        commitment_ids=(),
        identity_tokens=(),
        status=OrganizationCandidateStatus.PARTIAL,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        self_identified=False,
        owner_ids=("ada",),
        first_tick=window * 10,
        last_tick=window * 10 + 9,
    )


def _assignment(
    candidates: tuple[OrganizationCandidate, ...],
    windows: tuple[int, ...] = (0,),
) -> OrganizationIdentityAssignment:
    detection = OrganizationDetectionResult(
        windows=tuple(
            OrganizationWindowResult(
                window_index=index,
                start_tick=index * 10,
                end_tick=index * 10 + 9,
                candidate_keys=tuple(
                    candidate.candidate_key
                    for candidate in candidates
                    if candidate.window_index == index
                ),
                lane_presence=(("goals", True),),
            )
            for index in windows
        ),
        candidates=tuple(candidates),
        coverage=OrganizationCoverage.of(1, 7),
    )
    return assign_organization_identities(detection)


def test_identity_is_permutation_invariant_and_run_bound() -> None:
    first = derive_organization_id(
        creation_tick=3,
        founding_member_ids=("b", "a"),
        structural_anchors=("goal:p1", "role:r1"),
    )
    second = derive_organization_id(
        creation_tick=3,
        founding_member_ids=("a", "b"),
        structural_anchors=("role:r1", "goal:p1"),
    )
    assert first == second


@pytest.mark.asyncio
async def test_publication_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    from experiments import build_completed_run_organization_harvest

    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-organization-determinism")
    ) as runner:
        result = await runner.run()
    harvest = build_completed_run_organization_harvest(
        result,
        run_id="run-organization-determinism",
        input_revision="rev-1",
        generated_tick=result.ticks_committed,
    )
    first = build_organization_harvest_result(harvest)
    second = build_organization_harvest_result(harvest)
    assert first.publication_id == second.publication_id
    assert first.snapshot_bytes == second.snapshot_bytes

    publisher = create_organization_publisher(tmp_path)
    assert publisher is not None
    publish_organization_snapshot(first, publisher)
    publish_organization_snapshot(second, publisher)
    assert first.snapshot_bytes == second.snapshot_bytes


def test_pythonhashseed_does_not_change_ids(tmp_path: Path) -> None:
    script = (
        "from analysis.organization_contract import derive_organization_id;"
        "print(derive_organization_id(creation_tick=3,"
        "founding_member_ids=('b','a','c'),"
        "structural_anchors=('goal:p1','role:r1')))"
    )
    outputs = set()
    for seed in ("0", "1"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            cwd=tmp_path,
            env=env,
        )
        outputs.add(completed.stdout.strip())
    assert len(outputs) == 1
    assert outputs.pop().startswith("org-")


@settings(max_examples=25, deadline=None)
@given(count=st.integers(min_value=1, max_value=6))
def test_generated_acyclic_lineage_validates(count: int) -> None:
    candidates = tuple(
        _candidate(f"c{index}", 0, (f"m{index}", "shared"), ("goal:p1",))
        for index in range(count)
    )
    analysis = derive_organization_lineage(_assignment(candidates))
    known = tuple(record.organization_id for record in analysis.records)
    validate_organization_lineage(analysis.edges, known_ids=known)


def test_backward_edge_is_rejected() -> None:
    first = "org-0000000000000001"
    second = "org-0000000000000002"
    edges = (
        OrganizationLineageEdge(
            kind=OrganizationLineageKind.CONTINUED,
            from_id=first,
            to_id=second,
            tick=5,
        ),
        OrganizationLineageEdge(
            kind=OrganizationLineageKind.CONTINUED,
            from_id=second,
            to_id=first,
            tick=4,
        ),
    )
    with pytest.raises(ValueError):
        validate_organization_lineage(edges, known_ids=(first, second))
