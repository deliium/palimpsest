"""Completed-run organization publication: snapshot, receipt, and truncation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from analysis import (
    OrganizationCandidate,
    OrganizationCandidateStatus,
    OrganizationCoverage,
    OrganizationMemberClaim,
    OrganizationMembershipStatus,
    OrganizationTemporalScope,
    derive_organization_lineage,
)
from experiments import (
    OrganizationHarvest,
    build_organization_harvest_result,
    organization_publication_document,
    publish_organization_snapshot,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.organization_models import MAX_SNAPSHOT_MEMBERS
from simulation.organization_ports import OrganizationPublication
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
from tests.unit.organization_artifact_helpers import example_snapshot
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _config() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=11,
            stochastic_identity="cmp-v4-organization-publication",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-v4-organization-publication"),
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
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(organizations=True),
    )


class _RecordingPort:
    def __init__(self) -> None:
        self.publications: list[OrganizationPublication] = []

    def publish(self, publication: OrganizationPublication) -> None:
        self.publications.append(publication)


class _SyntheticHarvest:
    def __init__(self, claims: int) -> None:
        from analysis import (
            OrganizationIdentityAssignment,
            OrganizationRecord,
            OrganizationWindowSnapshot,
            derive_organization_id,
        )

        claims_rows = tuple(
            OrganizationMemberClaim(
                member_id=f"body-{index:04d}",
                status=OrganizationMembershipStatus.PERCEIVED,
                basis="participation",
                temporal_scope=OrganizationTemporalScope.ONGOING,
                owner_ids=("ada",),
            )
            for index in range(claims)
        )
        member_ids = tuple(sorted(claim.member_id for claim in claims_rows))
        candidate = OrganizationCandidate(
            candidate_key="bulk",
            window_index=0,
            member_ids=member_ids,
            member_claims=claims_rows,
            role_anchor_ids=(),
            goal_anchor_ids=("project-1",),
            resource_anchor_ids=(),
            procedure_anchor_ids=(),
            record_anchor_ids=(),
            commitment_ids=(),
            identity_tokens=(),
            status=OrganizationCandidateStatus.RECOGNIZED,
            temporal_scope=OrganizationTemporalScope.ONGOING,
            self_identified=False,
            owner_ids=("ada",),
            first_tick=0,
            last_tick=9,
        )
        organization_id = derive_organization_id(
            creation_tick=0,
            founding_member_ids=member_ids[:512],
            structural_anchors=("goal:project-1",),
        )
        record = OrganizationRecord(
            organization_id=organization_id,
            creation_tick=0,
            first_tick=0,
            last_tick=9,
            status=OrganizationCandidateStatus.RECOGNIZED,
            member_ids=member_ids,
            anchor_signature=("goal:project-1",),
            window_indexes=(0,),
        )
        assignment = OrganizationIdentityAssignment(
            policy_version="organization-identity.v1",
            records=(record,),
            transitions=(),
            windows=(
                OrganizationWindowSnapshot(
                    window_index=0,
                    start_tick=0,
                    end_tick=99,
                    candidates=(candidate,),
                    overlap_person_ids=(),
                    lane_presence=(("goals", True),),
                    coverage=OrganizationCoverage.of(1, 7),
                ),
            ),
            coverage=OrganizationCoverage.of(1, 7),
            candidate_ids=(("bulk", organization_id),),
        )
        analysis = derive_organization_lineage(assignment)
        self.harvest = OrganizationHarvest(
            run_id="run-synthetic",
            input_revision="rev-1",
            generated_tick=9,
            owner_rows=(),
            assignment=assignment,
            analysis=analysis,
        )


@pytest.mark.asyncio
async def test_completed_run_builds_one_canonical_snapshot() -> None:
    from experiments import build_completed_run_organization_harvest

    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-organization-publication")
    ) as runner:
        result = await runner.run()

    harvest = build_completed_run_organization_harvest(
        result,
        run_id="run-organization-publication",
        input_revision="rev-1",
        generated_tick=result.ticks_committed,
    )
    built = build_organization_harvest_result(harvest)
    assert built.publication_id.startswith("org-edge-")
    assert built.snapshot.publication_id == built.publication_id
    assert built.snapshot.run_id == "run-organization-publication"

    again = build_organization_harvest_result(harvest)
    assert again.publication_id == built.publication_id
    assert again.snapshot_bytes == built.snapshot_bytes


@pytest.mark.asyncio
async def test_publication_injects_exactly_one_artifact() -> None:
    from experiments import build_completed_run_organization_harvest

    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-organization-publication-port")
    ) as runner:
        result = await runner.run()
    harvest = build_completed_run_organization_harvest(
        result,
        run_id="run-organization-publication-port",
        input_revision="rev-1",
        generated_tick=result.ticks_committed,
    )
    built = build_organization_harvest_result(harvest)
    port = _RecordingPort()
    publish_organization_snapshot(built, port)
    assert len(port.publications) == 1
    assert port.publications[0].payload == built.snapshot_bytes


def test_receipt_contains_no_identity_payloads() -> None:
    harvest = _SyntheticHarvest(3).harvest
    built = build_organization_harvest_result(harvest)
    receipt = organization_publication_document(built)
    assert receipt["status"] == "published"
    assert receipt["candidate_count"] == 1
    assert "run_id" not in receipt
    for value in receipt.values():
        if isinstance(value, str):
            assert "body-" not in value
            assert "orgc-" not in value
            assert "ada" not in value


def test_member_truncation_is_explicit_and_bounded() -> None:
    harvest = _SyntheticHarvest(MAX_SNAPSHOT_MEMBERS + 5).harvest
    built = build_organization_harvest_result(harvest)
    candidate = built.snapshot.candidates[0]
    assert len(candidate.members) == MAX_SNAPSHOT_MEMBERS
    assert built.provenance_code == "member_list_truncated"
    assert built.snapshot.provenance_code == "member_list_truncated"
    assert [member.member_id for member in candidate.members] == sorted(
        member.member_id for member in candidate.members
    )


def test_changing_a_member_changes_the_digest() -> None:
    harvest = _SyntheticHarvest(3).harvest
    first = build_organization_harvest_result(harvest)
    from dataclasses import replace as dataclass_replace

    snapshot = first.snapshot
    candidate = snapshot.candidates[0]
    changed_member = dataclass_replace(candidate.members[0], status="former")
    changed_candidate = dataclass_replace(
        candidate, members=(changed_member, *candidate.members[1:])
    )
    changed_snapshot = dataclass_replace(
        snapshot, candidates=(changed_candidate,), publication_id=""
    )
    from simulation.organization_codec import (
        compute_organization_publication_id,
        encode_organization_snapshot,
        organization_digest,
    )

    assert organization_digest(encode_organization_snapshot(changed_snapshot)) != (
        organization_digest(first.snapshot_bytes)
    )
    assert compute_organization_publication_id(changed_snapshot) != (
        first.publication_id
    )


def test_example_snapshot_is_a_valid_artifact() -> None:
    snapshot = example_snapshot()
    assert snapshot.schema_version == "organization-snapshot-v1"
