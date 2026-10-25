"""Publish an explicitly constructed civilization presentation pack.

This is test-only, constructed presentation evidence. It never runs a world and
never writes into the real producer namespace. It exercises the same detached
composer and read-only filesystem publisher as the real producer so API/client
tests can cover positive settlement/trade/culture/knowledge/group/institution
rows that a short real run may not reliably provide.
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

from experiments.civilization_publication import (
    CivilizationCapturedHistory,
    compose_civilization_history,
)
from persistence.civilization_filesystem import (
    create_civilization_publisher,
    create_civilization_reader,
)
from simulation.civilization_boundaries import project_civilization_boundary
from simulation.civilization_capture import (
    CivilizationOwnerGroup,
    CivilizationOwnerKnowledge,
    CivilizationOwnerTrait,
    project_civilization_events,
)
from simulation.civilization_ports import CivilizationReadBudget
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V22,
    ExchangeCompleted,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.production import Structure, StructureKind


def _identity(seed: str) -> tuple[str, str]:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"civ-constructed-{digest}", f"world-constructed-{digest}"


def _trait(
    trait_id: str, fingerprint: str, first: int, last: int
) -> CivilizationOwnerTrait:
    return CivilizationOwnerTrait(trait_id, fingerprint, first, last)


def _inventory(
    owner_id: str,
    *,
    cultural: tuple[CivilizationOwnerTrait, ...] = (),
    knowledge: tuple[CivilizationOwnerKnowledge, ...] = (),
    groups: tuple[CivilizationOwnerGroup, ...] = (),
) -> Any:
    from simulation.civilization_capture import (
        CivilizationInventoryChannel,
        CivilizationInventoryCoverage,
        CivilizationOwnerInventory,
    )
    from simulation.civilization_models import (
        CivilizationCoverage,
        CivilizationCoverageState,
    )

    present = {
        CivilizationInventoryChannel.CULTURAL_FEATURES: bool(cultural),
        CivilizationInventoryChannel.PRACTICAL_KNOWLEDGE: bool(knowledge),
        CivilizationInventoryChannel.GROUPS: bool(groups),
    }
    channels = tuple(
        CivilizationInventoryCoverage(
            channel,
            (
                CivilizationCoverage(CivilizationCoverageState.COMPLETE)
                if present.get(channel, False)
                else CivilizationCoverage(
                    CivilizationCoverageState.DISABLED, "capture_off"
                )
            ),
        )
        for channel in CivilizationInventoryChannel
    )
    return CivilizationOwnerInventory(
        owner_id,
        0,
        True,
        channels,
        cultural,
        (),
        (),
        knowledge,
        groups,
        (),
        (),
        (),
    )


def _boundary(
    *,
    run_id: str,
    world_id: str,
    tick: int,
    inventories: tuple[Any, ...],
    structures: tuple[Structure, ...],
) -> Any:
    from tests.unit.test_observer_civilization import _physical_scene

    scene = replace(
        _physical_scene(),
        run_id=run_id,
        world_id=world_id,
        tick=tick,
        revision=tick,
        structures=structures,
    )
    return project_civilization_boundary(
        scene,
        owner_inventories=inventories,
    )


def _exchange_batch(run_id: str, world_id: str, tick: int) -> Any:
    detail = ExchangeCompleted(
        EntityId("body-a"),
        EntityId("body-b"),
        "accept",
        (EntityId("tool-constructed"),),
        (EntityId("food-constructed"),),
        ("tool",),
        ("food",),
    )
    event = make_physical_replayable_event(
        event_id=EventId("event-constructed-exchange"),
        run_id=run_id,
        world_id=WorldId(world_id),
        tick=tick,
        sequence=0,
        cause=ActionCause(
            RequestId("request-constructed-exchange"), EntityId("body-a")
        ),
        resulting_revision=WorldRevision(tick + 1),
        details=detail,
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V22,
    )
    return project_civilization_events(
        run_id,
        tick,
        (event,),
        expected_count=1,
        source="committed_result",
    )


def constructed_history(
    *, seed: str = "v3-41-constructed"
) -> CivilizationCapturedHistory:
    run_id, world_id = _identity(seed)
    knowledge = (
        CivilizationOwnerKnowledge(
            "knowledge-taught",
            "crafting_process",
            "tech:constructed",
            "teaching",
            ("knowledge-source",),
            "knowledge-taught",
            0,
            False,
            (),
            2,
            True,
            "crafting",
            "agent-b",
            "agent-b",
        ),
        CivilizationOwnerKnowledge(
            "knowledge-ambiguous",
            "crafting_process",
            "tech:constructed",
            "independent_discovery",
            (),
            "knowledge-ambiguous",
            0,
            False,
            (),
            3,
            True,
            "crafting",
            None,
            None,
        ),
    )
    group = CivilizationOwnerGroup(
        "group-constructed",
        "member",
        ("agent-a", "agent-b"),
        0.7,
        True,
        "inferred",
        None,
    )
    owner_a = _inventory(
        "agent-a",
        cultural=(_trait("trait-constructed", "fingerprint-constructed", 0, 4),),
        knowledge=knowledge,
        groups=(group,),
    )
    owner_b = _inventory(
        "agent-b",
        cultural=(_trait("trait-constructed", "fingerprint-constructed", 1, 4),),
    )
    structure = Structure(
        EntityId("structure-constructed"),
        EntityId("loc-1"),
        StructureKind.SHELTER,
        1.0,
        0,
    )
    boundaries = tuple(
        _boundary(
            run_id=run_id,
            world_id=world_id,
            tick=tick,
            inventories=(owner_a, owner_b),
            structures=(structure,),
        )
        for tick in range(5)
    )
    batches = (_exchange_batch(run_id, world_id, 3),)
    return CivilizationCapturedHistory(run_id, world_id, boundaries, batches)


async def _publish(history: CivilizationCapturedHistory, root: Path) -> dict[str, Any]:
    publisher = create_civilization_publisher(root)
    publication_id = f"civilization-{history.run_id}"
    publications = 0
    for publication in compose_civilization_history(history):
        await publisher.publish_boundary(publication_id, publication)
        publications += 1
    sealed = await publisher.seal_catalogue(history.run_id, publication_id)
    reader = create_civilization_reader(root)
    catalogue = await reader.catalogue(
        history.run_id,
        after_boundary=None,
        publication=sealed,
        budget=CivilizationReadBudget(),
    )
    if not catalogue.boundaries:
        raise RuntimeError("constructed_catalogue_empty")
    return {
        "run_id": history.run_id,
        "world_id": history.world_id,
        "provenance": "constructed presentation evidence",
        "boundary_ticks": list(history.boundary_ticks),
        "published_boundaries": publications,
        "publication": {
            "publication_id": sealed.publication_id,
            "digest": sealed.digest,
        },
        "catalogue_boundaries": len(catalogue.boundaries),
    }


def seed(*, root: Path, seed_value: str = "v3-41-constructed") -> dict[str, Any]:
    return asyncio.run(_publish(constructed_history(seed=seed_value), root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--civilization-root", required=True)
    parser.add_argument("--seed", default="v3-41-constructed")
    args = parser.parse_args(argv)
    try:
        manifest = seed(root=Path(args.civilization_root), seed_value=args.seed)
    except Exception as exc:  # bounded diagnostic; never dump payloads
        print(
            json.dumps(
                {"error": type(exc).__name__, "reason": "constructed_pack_failed"},
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
