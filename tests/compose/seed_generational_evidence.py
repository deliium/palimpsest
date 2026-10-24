"""Create controlled generational evidence and publish native lineage fixtures.

This producer is test-only. It persists a real durable generational run through
the installed manager/runner/database composition, commits one ordinary Feed
care command through the trusted intervention seam, projects the resulting
objective genealogy, and publishes explicitly constructed native mentorship
presentation fixtures for the same run/boundary. The mentorship records prove
rendering and API provenance handling, not spontaneous teaching.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx

from api.durable_runner import make_durable_runner_factory
from api.errors import ApiError
from api.simulation_manager import SimulationManager
from experiments.generational_runner_scenario import generational_runner_scenario
from infrastructure.database import create_database_resources
from infrastructure.settings import load_settings
from persistence import create_run_control_repository
from persistence.lineage_filesystem import create_lineage_publisher
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageEdge,
    LineageNode,
    LineageNodeState,
    LineageScope,
    LineageSnapshotRef,
    MentorshipLineageRecord,
)
from simulation.lineage_objective import (
    extract_agent_lifecycle_facts,
    extract_kinship_source_edges,
    project_genealogy_lineage,
)
from simulation.lineage_ports import (
    LineageBoundaryFrame,
    LineagePublication,
    LineageSourceProjection,
)
from simulation.models import RunId
from simulation.run_control import RunControlRecord
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    KinshipBootstrapEdgeSpec,
    KinshipSpec,
    MortalityMode,
    SimulationRunnerConfig,
    example_dependency_care_spec,
)
from simulation.runner_serialization import (
    encode_runner_config,
    runner_config_fingerprint,
)
from world.actions import Feed
from world.identifiers import AgentId, EntityId
from world.lifecycle import DependencyStatus
from world.models import Item, LifeStatus, non_lethal_physical_rules
from world.values import BodyCapacity, ItemKind, ItemLoad

_HORIZON = 16
_FOOD_ITEM = EntityId("item-acceptance-food")
_CAREGIVER = "agent-origin"
_SPAWN = EntityId("loc-origin")
_CONDITION_ID = "bl-generational-unassisted"


class FeedCareArbiter:
    """Trusted test arbiter: one ordinary Feed to a colocated dependent."""

    def __init__(self) -> None:
        self._runner: Any = None
        self.fired = False
        self.feed_tick: int | None = None
        self.actor_id: str | None = None
        self.target_id: str | None = None

    def bind(self, runner: Any) -> None:
        self._runner = runner

    def maybe_replace(
        self, *, tick: int, agent_id: AgentId, proposed_command: object
    ) -> object | None:
        del proposed_command
        if self.fired or self._runner is None:
            return None
        engine = self._runner.engine
        records = tuple(engine.lifecycle_records)
        bodies = {body.entity_id: body for body in engine.detached_bodies()}
        caregiver = next(
            (record for record in records if record.agent_id == agent_id.value),
            None,
        )
        if (
            caregiver is None
            or caregiver.dependency_status is not DependencyStatus.INDEPENDENT
        ):
            return None
        actor_body = bodies.get(caregiver.body_id)
        if (
            actor_body is None
            or actor_body.life_status is not LifeStatus.ALIVE
            or _FOOD_ITEM not in actor_body.inventory
        ):
            return None
        for record in records:
            if record.agent_id == agent_id.value:
                continue
            if record.dependency_status is not DependencyStatus.DEPENDENT:
                continue
            target_body = bodies.get(record.body_id)
            if target_body is None or target_body.life_status is not LifeStatus.ALIVE:
                continue
            if target_body.location_id != actor_body.location_id:
                continue
            self.fired = True
            self.feed_tick = tick
            self.actor_id = caregiver.agent_id
            self.target_id = record.agent_id
            return Feed(target_id=record.body_id, item_id=_FOOD_ITEM)
        return None

    def acknowledge_resolutions(self, resolutions: object) -> None:
        del resolutions


def _bl_config() -> SimulationRunnerConfig:
    definition = generational_runner_scenario(seed=23, max_ticks=_HORIZON)
    for condition in definition.conditions:
        if condition.condition_id == _CONDITION_ID:
            return condition.runner_config
    raise RuntimeError("acceptance_bl_condition_missing")


def _controlled_config() -> SimulationRunnerConfig:
    config = _bl_config()
    if config.population_lifecycle is None:
        raise RuntimeError("acceptance_lifecycle_missing")
    scenario = config.scenario
    bodies = []
    for body in scenario.bodies:
        inventory = (
            (_FOOD_ITEM,) if body.entity_id.value == "body-origin" else body.inventory
        )
        bodies.append(
            replace(
                body,
                location_id=_SPAWN,
                inventory=inventory,
            )
        )
    locations = tuple(
        replace(location, body_capacity=BodyCapacity(16))
        if location.entity_id == _SPAWN
        else location
        for location in scenario.locations
    )
    scenario = replace(
        scenario,
        physical_rules=non_lethal_physical_rules(base=scenario.physical_rules),
        locations=locations,
        bodies=tuple(bodies),
        items=(
            *scenario.items,
            Item(
                entity_id=_FOOD_ITEM,
                name="Acceptance grain",
                kind=ItemKind.FOOD,
                load=ItemLoad(1),
                holder_id=EntityId("body-origin"),
            ),
        ),
    )
    lifecycle = replace(
        config.population_lifecycle,
        max_population=12,
        demographic_policy_params={
            **config.population_lifecycle.demographic_policy_params,
            "spawn_location_ids": [_SPAWN.value],
        },
    )
    return replace(
        config,
        scenario=scenario,
        mortality_mode=MortalityMode.DISABLED,
        population_lifecycle=lifecycle,
        v3_capability_flags=replace(
            config.v3_capability_flags,
            generational_population=True,
            kinship_inheritance=True,
        ),
        kinship=KinshipSpec(
            bootstrap_edges=(
                KinshipBootstrapEdgeSpec(
                    parent_agent_id=AgentId("agent-origin"),
                    child_agent_id=AgentId("agent-spring"),
                ),
            ),
        ),
        dependency_care=example_dependency_care_spec(
            enabled_needs=("food",),
            caregiving_cognition_mode="disabled",
            perception_mode="none",
            allow_feed=True,
            allow_transport=True,
        ),
    )


async def _create_controlled_run() -> tuple[str, int, Any]:
    settings = load_settings()
    resources = create_database_resources(settings)
    try:
        base_factory = make_durable_runner_factory(resources.session_factory, settings)
        arbiter = FeedCareArbiter()
        holder: dict[str, Any] = {}

        async def factory(record: RunControlRecord) -> SimulationRunner:
            runner = await base_factory(record)
            arbiter.bind(runner)
            runner.set_intervention_arbiter(arbiter)
            holder["runner"] = runner
            return runner

        manager = SimulationManager(
            settings=settings,
            run_control=create_run_control_repository(resources.session_factory),
            runner_factory=factory,
            owner_id="acceptance-producer",
        )
        config = _controlled_config()
        seed_digest = hashlib.sha256(config.seed.to_bytes(8, "big")).hexdigest()
        run_id = f"acceptance-gen-{seed_digest[:12]}"
        payload = encode_runner_config(config)
        await manager.create(
            run_id=run_id,
            config_schema_version=config.schema_version,
            config_fingerprint=runner_config_fingerprint(config),
            config_payload=payload,
        )
        await manager.start(run_id=run_id)
        for _ in range(_HORIZON):
            try:
                await manager.tick(run_id=run_id)
            except ApiError as exc:
                if exc.code in {"lifecycle_conflict", "run_task_active"}:
                    break
                raise
        status = await manager.status(run_id=run_id)
        boundary = int(status.ticks_committed)
        if not arbiter.fired:
            raise RuntimeError("acceptance_feed_not_committed")
        runner = holder.get("runner")
        if runner is None:
            raise RuntimeError("acceptance_runner_missing")
        return run_id, boundary, runner
    finally:
        await resources.engine.dispose()


def _node_ref(
    run_id: RunId,
    family: LineageFamily,
    evidence: LineageEvidenceClass,
    kind: LineageNativeKind,
    native_id: str,
    owner: str | None,
) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=run_id,
        family=family,
        evidence_class=evidence,
        native_kind=kind,
        native_id=native_id,
        identity_owner=owner,
    )


def _digest(nodes: tuple[LineageNode, ...], edges: tuple[LineageEdge, ...]) -> str:
    payload = json.dumps(
        {
            "nodes": [repr(item) for item in nodes],
            "edges": [repr(item) for item in edges],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _publish_scope(
    *,
    root: Path,
    run_id: RunId,
    scope: LineageScope,
    boundary: int,
    nodes: tuple[LineageNode, ...],
    edges: tuple[LineageEdge, ...],
    policy: str,
) -> str:
    digest = _digest(nodes, edges)
    publication = LineagePublication(
        snapshot=LineageSnapshotRef(
            publication_id=f"lineage-{digest[:16]}",
            digest=digest,
            boundary_tick=boundary,
        ),
        frame=LineageBoundaryFrame(
            run_id=run_id,
            scope=scope,
            boundary_tick=boundary,
            observed_boundary=boundary,
            nodes=nodes,
            edges=edges,
            coverage=LineageCoverage(
                state=LineageCoverageState.COMPLETE,
                capture_start_tick=0,
                capture_end_tick=boundary,
                policy_version=policy,
            ),
            source_revision="acceptance-v1",
        ),
    )
    published = asyncio.run(create_lineage_publisher(root).publish(publication))
    return published.publication_id


def _roster(runner: Any, boundary: int) -> tuple[str, str, list[dict[str, object]]]:
    engine = runner.engine
    records = tuple(engine.lifecycle_records)
    bodies = {body.entity_id: body for body in engine.detached_bodies()}
    caregiver = next(
        (
            record
            for record in records
            if record.agent_id == _CAREGIVER
            and record.dependency_status is DependencyStatus.INDEPENDENT
        ),
        None,
    )
    learner = next(
        (
            record
            for record in records
            if record.dependency_status is DependencyStatus.DEPENDENT
            and record.generation_index > 0
        ),
        None,
    )
    if caregiver is None or learner is None:
        raise RuntimeError("acceptance_care_pair_missing")
    roster = [
        {
            "agent_id": record.agent_id,
            "body_id": record.body_id.value,
            "generation_index": record.generation_index,
            "stage": record.stage.value,
            "dependency_status": record.dependency_status.value,
            "life_status": (
                "alive"
                if bodies[record.body_id].life_status is LifeStatus.ALIVE
                else "dead"
            ),
            "entry_tick": record.entry_tick,
            "observed_tick": boundary,
        }
        for record in records
        if record.body_id in bodies
    ]
    return caregiver.agent_id, learner.agent_id, roster


def _genealogy(
    *,
    runner: Any,
    run_id: RunId,
    boundary: int,
) -> LineageSourceProjection:
    engine = runner.engine
    records = tuple(engine.lifecycle_records)
    bodies = {body.entity_id: body for body in engine.detached_bodies()}
    registrations = tuple(engine.ordered_registrations)
    facts = extract_agent_lifecycle_facts(
        bodies=tuple(
            (
                registration.agent_id.value,
                registration.entity_id.value,
                bodies[registration.entity_id].life_status,
            )
            for registration in registrations
            if registration.entity_id in bodies
        ),
        lifecycle_entry_ticks={
            record.agent_id: record.entry_tick for record in records
        },
        observed_tick=boundary,
    )
    projection = project_genealogy_lineage(
        run_id=run_id,
        boundary_tick=boundary,
        source_edges=extract_kinship_source_edges(engine.kinship_graph),
        lifecycle_facts=facts,
        coverage=LineageCoverage(
            state=LineageCoverageState.COMPLETE,
            capture_start_tick=0,
            capture_end_tick=boundary,
            policy_version="objective-genealogy.v1",
        ),
    )
    return projection


def _publish_lineage(
    *,
    runner: Any,
    run_id: str,
    lineage_root: Path,
    boundary: int,
) -> dict[str, object]:
    typed_run = RunId(run_id)
    founder, child, roster = _roster(runner, boundary)
    objective = LineageScope(
        run_id=typed_run,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
    )
    genealogy = _genealogy(runner=runner, run_id=typed_run, boundary=boundary)
    genealogy_id = _publish_scope(
        root=lineage_root,
        run_id=typed_run,
        scope=objective,
        boundary=boundary,
        nodes=genealogy.nodes,
        edges=genealogy.edges,
        policy="objective-genealogy.v1",
    )

    subjective = LineageScope(
        run_id=typed_run,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        owner_id=founder,
    )
    records = (
        MentorshipLineageRecord(
            owner_id=founder,
            teacher_id=founder,
            learner_id=child,
            lineage_id="acceptance-attempt",
            root_id="acceptance-root",
            parent_ids=(),
            content_kind="skill",
            content_key="acceptance-content-attempt",
            hop=1,
            acquisition_tick=max(0, boundary - 2),
            update_tick=max(0, boundary - 1),
            attempt_count=2,
            learning_evidence_count=0,
            confidence_band="low",
            mutated=False,
            evidence_refs=(),
            policy_version="mentorship-reciprocity.v1",
            observed_boundary=boundary,
            source_observed_boundary=boundary,
            native_status="attempt_only",
            source_revision="acceptance-attempt:1",
        ),
        MentorshipLineageRecord(
            owner_id=founder,
            teacher_id=founder,
            learner_id=child,
            lineage_id="acceptance-learned",
            root_id="acceptance-root",
            parent_ids=(),
            content_kind="skill",
            content_key="acceptance-content-learned",
            hop=1,
            acquisition_tick=max(0, boundary - 3),
            update_tick=max(0, boundary - 1),
            attempt_count=1,
            learning_evidence_count=2,
            confidence_band="medium",
            mutated=False,
            evidence_refs=(),
            policy_version="mentorship-reciprocity.v1",
            observed_boundary=boundary,
            source_observed_boundary=boundary,
            native_status="learned",
            source_revision="acceptance-learned:1",
        ),
    )
    mentorship_nodes = tuple(
        LineageNode(
            ref=_node_ref(
                typed_run,
                LineageFamily.MENTORSHIP,
                LineageEvidenceClass.SUBJECTIVE,
                LineageNativeKind.MENTORSHIP_ENTRY,
                record.lineage_id,
                founder,
            ),
            state=LineageNodeState.OBSERVED,
            observed_tick=record.update_tick,
            status_code=record.native_status,
            mentorship_record=record,
            source_observed_boundary=boundary,
        )
        for record in records
    )
    subjective_id = _publish_scope(
        root=lineage_root,
        run_id=typed_run,
        scope=subjective,
        boundary=boundary,
        nodes=mentorship_nodes,
        edges=(),
        policy="mentorship-subjective.v1",
    )

    analytical = LineageScope(
        run_id=typed_run,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
    )
    analytical_record = records[1]
    analytical_id = _publish_scope(
        root=lineage_root,
        run_id=typed_run,
        scope=analytical,
        boundary=boundary,
        nodes=(
            LineageNode(
                ref=_node_ref(
                    typed_run,
                    LineageFamily.MENTORSHIP,
                    LineageEvidenceClass.ANALYTICAL,
                    LineageNativeKind.MENTORSHIP_ENTRY,
                    analytical_record.lineage_id,
                    founder,
                ),
                state=LineageNodeState.OBSERVED,
                observed_tick=analytical_record.update_tick,
                status_code="learned",
                mentorship_record=analytical_record,
                source_observed_boundary=boundary,
            ),
        ),
        edges=(),
        policy="mentorship-analytical.v1",
    )

    return {
        "run_id": run_id,
        "boundary_tick": boundary,
        "roster_count": len(roster),
        "founder": founder,
        "child": child,
        "genealogy_publication": genealogy_id,
        "subjective_publication": subjective_id,
        "analytical_publication": analytical_id,
        "attempt_only_records": 1,
        "learning_evidence_records": 1,
        "genealogy_node_count": len(genealogy.nodes),
        "roster": roster,
    }


def _verify_api(
    *,
    base_url: str,
    run_id: str,
    boundary: int,
    inspection_token: str,
) -> dict[str, object]:
    headers = {"x-palimpsest-token": inspection_token} if inspection_token else {}
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=60.0) as client:
        demographics = client.get(
            f"/v1/simulations/{run_id}/observer/demographics",
            params={"tick": boundary},
            headers=headers,
        )
        demographics.raise_for_status()
        document = demographics.json()
        if document.get("availability") != "available":
            raise RuntimeError("acceptance_demographics_unavailable")
        feed_events = client.get(
            f"/v1/simulations/{run_id}/observer/events",
            params={
                "event_type": "AGENT_FED",
                "limit": 50,
                "catch_up": True,
            },
            headers=headers,
        )
        feed_events.raise_for_status()
        feed_items = list(feed_events.json().get("events", []))
        if not feed_items:
            raise RuntimeError("acceptance_feed_event_missing")
        participants = client.get(
            f"/v1/simulations/{run_id}/lineage/mentorship/participants",
            params={
                "evidence_class": "subjective",
                "agent_id": str(document["agents"][0]["agent_id"]),
                "owner_id": str(document["agents"][0]["agent_id"]),
                "boundary_tick": boundary,
                "role": "both",
                "limit": 100,
            },
            headers=headers,
        )
        if participants.status_code not in {200, 401, 403}:
            raise RuntimeError(
                f"acceptance_participants_failed status={participants.status_code}"
            )
        return {
            "demographics_available": True,
            "feed_events": len(feed_items),
            "participants_status": participants.status_code,
        }


def seed(
    *,
    base_url: str,
    lineage_root: Path,
    run_id: str | None = None,
    boundary: int | None = None,
    inspection_token: str = "",
) -> dict[str, object]:
    del boundary
    if run_id is None:
        run_id, boundary_tick, runner = asyncio.run(_create_controlled_run())
    else:
        raise RuntimeError("acceptance_controlled_run_required")
    checks = _verify_api(
        base_url=base_url,
        run_id=run_id,
        boundary=boundary_tick,
        inspection_token=inspection_token,
    )
    manifest = _publish_lineage(
        runner=runner,
        run_id=run_id,
        lineage_root=lineage_root,
        boundary=boundary_tick,
    )
    manifest.update(checks)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--lineage-root", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--boundary-tick", type=int, default=None)
    parser.add_argument("--inspection-token", default="")
    args = parser.parse_args(argv)
    try:
        manifest = seed(
            base_url=args.base_url,
            lineage_root=Path(args.lineage_root),
            run_id=args.run_id,
            boundary=args.boundary_tick,
            inspection_token=args.inspection_token,
        )
    except (RuntimeError, ApiError, httpx.HTTPError) as exc:
        print(
            json.dumps(
                {"error": type(exc).__name__, "reason": str(exc)},
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(manifest, default=str, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
