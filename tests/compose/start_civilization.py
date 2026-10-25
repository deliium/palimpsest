"""Run a durable, representative civilization producer.

This is test composition only. It builds a real simulation through the ordinary
manager/runner/database seam, installs the Task 6 capture, runs a finite
long-horizon schedule, and publishes through the task-owned composer/publisher.
It never writes world state directly and never fabricates owner evidence.

The real 256-tick/browser execution is a Compose gate (Task 17). Missing
database prerequisites must fail closed, not be silently skipped.
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
from experiments.civilization_capture import CivilizationEvidenceRecorder
from experiments.civilization_publication import (
    CivilizationCapturedHistory,
    compose_civilization_history,
)
from experiments.generational_runner_scenario import generational_runner_scenario
from experiments.regional_migration_scenario import (
    regional_migration_arbiter,
    regional_migration_scenario,
)
from infrastructure.database import create_database_resources
from infrastructure.settings import load_settings
from persistence import create_run_control_repository
from persistence.civilization_filesystem import (
    create_civilization_publisher,
    create_civilization_reader,
)
from research_runner.civilization_composition import (
    CivilizationProducerOptions,
    install_civilization_capture,
)
from simulation.civilization_capture import (
    CivilizationCaptureOptions,
    CivilizationEventKind,
)
from simulation.civilization_ports import CivilizationReadBudget
from simulation.run_control import RunControlRecord
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    example_collective_projects_spec,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
    example_knowledge_repositories_spec,
    example_public_goods_spec,
    example_resource_exchange_profile_spec,
    example_subjective_valuation_spec,
)
from simulation.runner_serialization import (
    encode_runner_config,
    runner_config_fingerprint,
)

HORIZON = 256
_REQUIRED_EVENTS = (
    CivilizationEventKind.JOURNEY_STARTED,
    CivilizationEventKind.JOURNEY_ARRIVED,
    CivilizationEventKind.EXCHANGE_COMPLETED,
    CivilizationEventKind.PROJECT_CONTRIBUTED,
    CivilizationEventKind.PUBLIC_GOOD_BENEFIT,
    CivilizationEventKind.REPOSITORY_MEMBER_DEPOSITED,
    CivilizationEventKind.REPOSITORY_MEMBER_RETRIEVED,
)


def civilization_config(*, seed: int = 23, max_ticks: int = HORIZON):
    """Representative AY/BL base plus retained-record and civic channels."""
    source = regional_migration_scenario(seed=seed, max_ticks=max_ticks)
    by_id = {item.condition_id: item for item in source.conditions}
    base = by_id["ay-accurate-evidence"].runner_config
    generational = {
        item.condition_id: item for item in generational_runner_scenario(
            seed=seed, max_ticks=max_ticks, base=base
        ).conditions
    }["bl-generational-unassisted"].runner_config
    flags = replace(
        generational.v3_capability_flags, cultural_historical_memory=True
    )
    return replace(
        generational,
        v3_capability_flags=flags,
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        knowledge_repositories=example_knowledge_repositories_spec(),
        collective_projects=example_collective_projects_spec(),
        public_goods=example_public_goods_spec(),
        subjective_valuation=example_subjective_valuation_spec(),
        resource_exchange_profile=example_resource_exchange_profile_spec(),
    )


def _run_id(config: Any) -> str:
    digest = hashlib.sha256(encode_runner_config(config)).hexdigest()[:12]
    return f"civ-real-{digest}"


def _event_counts(recorder: CivilizationEvidenceRecorder) -> dict[str, int]:
    counts: dict[str, int] = {}
    for batch in recorder.event_batches:
        for receipt in batch.receipts:
            counts[receipt.kind.value] = counts.get(receipt.kind.value, 0) + 1
    return counts


def _missing_categories(counts: dict[str, int], *, deaths: int) -> list[str]:
    missing = [
        kind.value for kind in _REQUIRED_EVENTS if int(counts.get(kind.value, 0)) < 1
    ]
    if deaths < 1:
        missing.append("death")
    return missing


async def _publish(
    history: CivilizationCapturedHistory, root: Path
) -> dict[str, object]:
    publisher = create_civilization_publisher(root)
    publication_id = f"civilization-{history.run_id}"
    publications = 0
    for publication in compose_civilization_history(history):
        await publisher.publish_boundary(publication_id, publication)
        publications += 1
    sealed = await publisher.seal_catalogue(history.run_id, publication_id)
    reader = create_civilization_reader(root)
    await reader.catalogue(
        history.run_id,
        after_boundary=None,
        publication=sealed,
        budget=CivilizationReadBudget(),
    )
    return {
        "publication_id": sealed.publication_id,
        "digest": sealed.digest,
        "published_boundaries": publications,
    }


async def _create_controlled_run(
    *, root: Path, max_ticks: int
) -> tuple[str, int, CivilizationEvidenceRecorder, Any]:
    settings = load_settings()
    resources = create_database_resources(settings)
    config = civilization_config(max_ticks=max_ticks)
    arbiter = regional_migration_arbiter("ay-visit-return", config)
    try:
        base_factory = make_durable_runner_factory(
            resources.session_factory, settings
        )
        holder: dict[str, Any] = {}
        recorder: CivilizationEvidenceRecorder | None = None

        async def factory(record: RunControlRecord) -> SimulationRunner:
            nonlocal recorder
            runner = await base_factory(record)
            recorder = install_civilization_capture(
                runner,
                CivilizationProducerOptions(
                    root=root,
                    capture=CivilizationCaptureOptions(enabled=True, cadence=1),
                ),
            )
            if arbiter is not None:
                runner.set_intervention_arbiter(arbiter)
            holder["runner"] = runner
            return runner

        manager = SimulationManager(
            settings=settings,
            run_control=create_run_control_repository(resources.session_factory),
            runner_factory=factory,
            owner_id="civilization-producer",
        )
        run_id = _run_id(config)
        await manager.create(
            run_id=run_id,
            config_schema_version=config.schema_version,
            config_fingerprint=runner_config_fingerprint(config),
            config_payload=encode_runner_config(config),
        )
        await manager.start(run_id=run_id)
        for _ in range(max_ticks):
            try:
                await manager.tick(run_id=run_id)
            except ApiError as exc:
                if exc.code in {"lifecycle_conflict", "run_task_active"}:
                    break
                raise
        status = await manager.status(run_id=run_id)
        boundary = int(status.ticks_committed)
        runner = holder.get("runner")
        if recorder is None or runner is None:
            raise RuntimeError("civilization_capture_unavailable")
        if boundary < max_ticks:
            raise RuntimeError("civilization_256_tick_high_water_missing")
        return run_id, boundary, recorder, runner
    finally:
        await resources.engine.dispose()


def _deaths(runner: Any) -> int:
    from world.models import LifeStatus

    return sum(
        1
        for body in runner.engine.detached_bodies()
        if body.life_status is not LifeStatus.ALIVE
    )


def _verify_api(
    *, base_url: str, run_id: str, boundary: int, inspection_token: str, debug_token: str
) -> dict[str, object]:
    root = base_url.rstrip("/")
    inspection = {"x-palimpsest-token": inspection_token} if inspection_token else {}
    debug = {"x-palimpsest-token": debug_token} if debug_token else {}
    with httpx.Client(base_url=root, timeout=120.0) as client:
        map_response = client.get(
            f"/v1/simulations/{run_id}/observer/civilization/map",
            params={"section": "locations", "tick": boundary, "limit": 100},
            headers=inspection,
        )
        map_response.raise_for_status()
        catalogue = client.get(
            f"/v1/simulations/{run_id}/observer/civilization/catalogue",
            params={"evidence_class": "ANALYTICAL", "limit": 100},
            headers=debug,
        )
        catalogue.raise_for_status()
        document = catalogue.json()
        return {
            "map_rows": len(map_response.json().get("rows", [])),
            "catalogue_boundaries": len(document.get("boundaries", [])),
            "catalogue_status": str(document.get("availability", "")),
        }


def start_civilization(
    *,
    civilization_root: Path,
    base_url: str = "",
    inspection_token: str = "",
    debug_token: str = "",
    max_ticks: int = HORIZON,
    require_positive: bool = True,
) -> dict[str, object]:
    run_id, boundary, recorder, runner = asyncio.run(
        _create_controlled_run(root=civilization_root, max_ticks=max_ticks)
    )
    history = CivilizationCapturedHistory(
        run_id,
        recorder.boundaries[0].cursor.world_id,
        recorder.boundaries,
        recorder.event_batches,
    )
    publication = asyncio.run(_publish(history, civilization_root))
    counts = _event_counts(recorder)
    missing = _missing_categories(counts, deaths=_deaths(runner))
    manifest: dict[str, object] = {
        "run_id": run_id,
        "provenance": "real durable producer",
        "boundary_tick": boundary,
        "boundary_count": len(recorder.boundaries),
        "event_count": sum(counts.values()),
        "event_counts": counts,
        "missing_categories": missing,
        "publication": publication,
    }
    if base_url:
        manifest["api"] = _verify_api(
            base_url=base_url,
            run_id=run_id,
            boundary=boundary,
            inspection_token=inspection_token,
            debug_token=debug_token,
        )
    if require_positive and missing:
        raise RuntimeError(
            "civilization_positive_evidence_missing:" + ",".join(sorted(missing))
        )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--civilization-root", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--inspection-token", default="")
    parser.add_argument("--debug-token", default="")
    parser.add_argument("--max-ticks", type=int, default=HORIZON)
    parser.add_argument("--allow-missing-positive", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = start_civilization(
            civilization_root=Path(args.civilization_root),
            base_url=args.base_url,
            inspection_token=args.inspection_token,
            debug_token=args.debug_token,
            max_ticks=args.max_ticks,
            require_positive=not args.allow_missing_positive,
        )
    except Exception as exc:  # bounded diagnostics only
        print(
            json.dumps(
                {"error": type(exc).__name__, "reason": str(exc)[:200]},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(manifest, default=str, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
