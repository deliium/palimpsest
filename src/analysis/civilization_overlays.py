"""Pure detached civilization overlay calculators.

Every output is a presentation read model over already-retained evidence. The
module never reads live state, never invents objective entities, and never
classifies a missing capture interval as disappearance or zero prevalence.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Final, Literal, cast

from analysis.institution_lineage import compute_institution_lineage
from analysis.institutional_decay import (
    InstitutionTemporalRow,
    compute_institutional_decay,
)
from simulation.civilization_boundaries import CivilizationBoundaryInput
from simulation.civilization_capture import (
    CivilizationEventBatch,
    CivilizationEventKind,
    CivilizationEventReceipt,
    CivilizationInventoryChannel,
    CivilizationOwnerInventory,
    CivilizationOwnerKnowledge,
)
from simulation.civilization_models import (
    CivilizationAnchor,
    CivilizationAnchorKind,
    CivilizationCoverage,
    CivilizationCoverageState,
    CivilizationEvidenceClass,
    CivilizationLayer,
    CivilizationMarker,
    CivilizationMarkerType,
    CivilizationScope,
    CivilizationSourceRef,
    CivilizationWindow,
)
from simulation.civilization_rows import (
    CivilizationCultureRow,
    CivilizationGroupRow,
    CivilizationInstitutionRow,
    CivilizationItemCount,
    CivilizationLayerContext,
    CivilizationLocationRow,
    CivilizationMigrationRow,
    CivilizationRowContext,
    CivilizationSettlementRow,
    CivilizationTechnologyRow,
    CivilizationTradeRow,
)
from world.values import ItemKind

__all__ = [
    "CIVILIZATION_FLOW_WINDOW_TICKS",
    "CIVILIZATION_OVERLAYS_POLICY_VERSION",
    "compose_culture_rows",
    "compose_group_rows",
    "compose_institution_rows",
    "compose_markers",
    "compose_migration_rows",
    "compose_settlement_rows",
    "compose_technology_rows",
    "compose_trade_rows",
    "flow_window",
]

CIVILIZATION_OVERLAYS_POLICY_VERSION: Final = "civilization-overlays.v1"
CIVILIZATION_FLOW_WINDOW_TICKS: Final = 32

_InstitutionStatus = Literal[
    "emerging",
    "stable",
    "weakening",
    "collapsed",
    "censored",
    "recognized",
    "uncertain",
    "vacant",
    "contested",
    "lost",
]

_CULTURAL_CHANNEL_BY_REPRESENTATION: Final = {
    CivilizationInventoryChannel.CULTURAL_FEATURES: "ledger_carriage",
    CivilizationInventoryChannel.TERMINOLOGY: "label_inventory",
    CivilizationInventoryChannel.NARRATIVES: "narrative_lineage",
}


def flow_window(boundary_tick: int) -> CivilizationWindow:
    if type(boundary_tick) is not int or boundary_tick < 0:
        raise ValueError("boundary_tick")
    return CivilizationWindow(
        max(0, boundary_tick - CIVILIZATION_FLOW_WINDOW_TICKS), boundary_tick
    )


def _context(
    *,
    layer: CivilizationLayer,
    evidence_class: CivilizationEvidenceClass,
    owner_id: str | None,
    row_id: str,
    source_refs: tuple[CivilizationSourceRef, ...],
    anchors: tuple[CivilizationAnchor, ...] = (),
    boundary_tick: int,
    window: CivilizationWindow,
    coverage: CivilizationCoverage,
    detail_truncated: bool = False,
) -> tuple[CivilizationRowContext, CivilizationLayerContext]:
    return (
        CivilizationRowContext(row_id, source_refs, anchors, detail_truncated),
        CivilizationLayerContext(
            CivilizationScope(layer, evidence_class, owner_id),
            boundary_tick,
            window,
            CIVILIZATION_OVERLAYS_POLICY_VERSION,
            coverage,
        ),
    )


def _event_ref(
    receipt: CivilizationEventReceipt, owner_id: str | None = None
) -> CivilizationSourceRef:
    return CivilizationSourceRef(
        "event", receipt.event_id, receipt.tick, owner_id=owner_id
    )


def _window_coverage(
    batches: tuple[CivilizationEventBatch, ...], window: CivilizationWindow
) -> CivilizationCoverage:
    covered = {
        batch.tick
        for batch in batches
        if batch.coverage.state is CivilizationCoverageState.COMPLETE
        and window.start_tick <= batch.tick < window.end_tick
    }
    expected = max(0, window.end_tick - window.start_tick)
    if len(covered) >= expected:
        return CivilizationCoverage(CivilizationCoverageState.COMPLETE)
    return CivilizationCoverage(
        CivilizationCoverageState.PARTIAL,
        "capture_gap",
        capture_start=window.start_tick,
        capture_end=window.end_tick,
        missing_intervals=tuple(
            CivilizationWindow(tick, tick + 1)
            for tick in range(window.start_tick, window.end_tick)
            if tick not in covered
        ),
    )


def _filtered_batches(
    batches: tuple[CivilizationEventBatch, ...], window: CivilizationWindow
) -> tuple[CivilizationEventBatch, ...]:
    return tuple(
        batch
        for batch in batches
        if batch.coverage.state is CivilizationCoverageState.COMPLETE
        and window.start_tick <= batch.tick < window.end_tick
    )


def _settlement_active(
    occupancy: dict[int, int | None],
    structures: dict[int, int | None],
    tick: int,
) -> bool:
    if tick < 3 or structures.get(tick, 0) in (None, 0):
        return False
    for boundary in range(tick - 3, tick + 1):
        if occupancy.get(boundary, None) in (None, 0):
            return False
    return True


def compose_settlement_rows(
    boundaries: tuple[CivilizationBoundaryInput, ...],
    *,
    boundary_tick: int,
) -> tuple[CivilizationSettlementRow, ...]:
    """Four complete occupancy boundaries plus intact infrastructure at B."""
    location_rows = {
        row.location_id: row
        for frame in boundaries
        for row in frame.map_rows
        if isinstance(row, CivilizationLocationRow)
    }
    location_ids = sorted(location_rows)
    window = flow_window(boundary_tick)
    rows: list[CivilizationSettlementRow] = []
    for location_id in location_ids:
        occupancy: dict[int, int | None] = {}
        structures: dict[int, int | None] = {}
        for frame in boundaries:
            tick = frame.cursor.tick
            occupancy[tick] = sum(
                1
                for body in frame.bodies
                if body.location_id == location_id and body.living and body.owner_id
            )
            structures[tick] = sum(
                1
                for structure in frame.structures
                if structure.location_id == location_id and structure.integrity > 0.0
            )
        recent = [
            occupancy.get(tick) for tick in range(boundary_tick - 3, boundary_tick + 1)
        ]
        if boundary_tick < 3:
            status: Literal[
                "active", "inactive", "censored", "insufficient_history"
            ] = "insufficient_history"
            coverage = CivilizationCoverage(
                CivilizationCoverageState.UNAVAILABLE, "insufficient_history"
            )
            streak = 0
        elif (
            any(value is None for value in recent)
            or structures.get(boundary_tick) is None
        ):
            status = "censored"
            coverage = CivilizationCoverage(
                CivilizationCoverageState.PARTIAL, "capture_gap"
            )
            streak = 0
        elif _settlement_active(occupancy, structures, boundary_tick):
            status = "active"
            coverage = CivilizationCoverage(CivilizationCoverageState.COMPLETE)
            streak = 0
            tick = boundary_tick
            while _settlement_active(occupancy, structures, tick):
                streak += 1
                tick -= 1
        else:
            status = "inactive"
            coverage = CivilizationCoverage(CivilizationCoverageState.COMPLETE)
            streak = 0
        active_ticks = [
            tick
            for tick in sorted(occupancy)
            if tick <= boundary_tick and _settlement_active(occupancy, structures, tick)
        ]
        first = active_ticks[0] if active_ticks else None
        last = active_ticks[-1] if active_ticks else None
        episode_start = None
        if status == "active":
            episode_start = boundary_tick - streak + 1
        elif active_ticks:
            episode_start = active_ticks[-1]
        context, history = _context(
            layer=CivilizationLayer.SETTLEMENTS,
            evidence_class=CivilizationEvidenceClass.ANALYTICAL,
            owner_id=None,
            row_id=f"settlement:{location_id}",
            source_refs=location_rows[location_id].context.source_refs,
            boundary_tick=boundary_tick,
            window=window,
            coverage=coverage,
        )
        rows.append(
            CivilizationSettlementRow(
                context,
                history,
                f"settlement:{location_id}",
                location_id,
                occupancy.get(boundary_tick) or 0,
                structures.get(boundary_tick) or 0,
                first,
                last,
                streak,
                episode_start,
                status,
            )
        )
    return tuple(sorted(rows, key=lambda row: row.context.row_id))


def compose_migration_rows(
    batches: tuple[CivilizationEventBatch, ...],
    *,
    boundary_tick: int,
) -> tuple[CivilizationMigrationRow, ...]:
    window = flow_window(boundary_tick)
    coverage = _window_coverage(batches, window)
    grouped: dict[str, list[CivilizationEventReceipt]] = defaultdict(list)
    for batch in _filtered_batches(batches, window):
        for receipt in batch.receipts:
            if receipt.kind in {
                CivilizationEventKind.JOURNEY_STARTED,
                CivilizationEventKind.JOURNEY_ARRIVED,
                CivilizationEventKind.JOURNEY_ENDED,
            }:
                assert receipt.journey_id is not None
                grouped[receipt.journey_id].append(receipt)
    rows: list[CivilizationMigrationRow] = []
    for journey_id in sorted(grouped):
        events = sorted(
            grouped[journey_id], key=lambda item: (item.tick, item.sequence)
        )
        started = next(
            (
                item
                for item in events
                if item.kind is CivilizationEventKind.JOURNEY_STARTED
            ),
            None,
        )
        arrived = next(
            (
                item
                for item in events
                if item.kind is CivilizationEventKind.JOURNEY_ARRIVED
            ),
            None,
        )
        ended = next(
            (
                item
                for item in events
                if item.kind is CivilizationEventKind.JOURNEY_ENDED
            ),
            None,
        )
        phase: Literal[
            "preparing", "capacity_wait", "travelling", "arrived", "ended"
        ] = (
            "arrived"
            if arrived
            else "ended"
            if ended
            else "travelling"
            if started
            else "preparing"
        )
        participants = tuple(
            sorted({pid for item in events for pid in item.participant_ids})
        )
        origin = next(
            item.origin_location_id for item in events if item.origin_location_id
        )
        destination = next(
            item.destination_location_id
            for item in events
            if item.destination_location_id
        )
        if origin is None or destination is None:
            continue
        context, history = _context(
            layer=CivilizationLayer.MIGRATION,
            evidence_class=CivilizationEvidenceClass.OBJECTIVE,
            owner_id=None,
            row_id=f"migration:{journey_id}",
            source_refs=tuple(_event_ref(item) for item in events),
            boundary_tick=boundary_tick,
            window=window,
            coverage=coverage,
        )
        rows.append(
            CivilizationMigrationRow(
                context,
                history,
                journey_id,
                f"route:{origin}->{destination}",
                origin,
                destination,
                len(participants),
                participants,
                phase,
                started.tick if started else None,
                arrived.tick if arrived else None,
                ended.tick if ended else None,
                sum(
                    1
                    for item in events
                    if item.kind is CivilizationEventKind.JOURNEY_STARTED
                ),
                sum(
                    1
                    for item in events
                    if item.kind is CivilizationEventKind.JOURNEY_ARRIVED
                ),
                0,
                sum(
                    1
                    for item in events
                    if item.kind is CivilizationEventKind.JOURNEY_ENDED
                ),
            )
        )
    return tuple(sorted(rows, key=lambda row: row.context.row_id))


def compose_trade_rows(
    batches: tuple[CivilizationEventBatch, ...],
    *,
    boundary_tick: int,
) -> tuple[CivilizationTradeRow, ...]:
    window = flow_window(boundary_tick)
    coverage = _window_coverage(batches, window)
    grouped: dict[
        tuple[tuple[str, ...], str | None], list[CivilizationEventReceipt]
    ] = defaultdict(list)
    for batch in _filtered_batches(batches, window):
        for receipt in batch.receipts:
            if receipt.kind is not CivilizationEventKind.EXCHANGE_COMPLETED:
                continue
            key = (receipt.participant_ids, receipt.origin_location_id)
            grouped[key].append(receipt)
    rows: list[CivilizationTradeRow] = []
    for (participants, location), receipts in sorted(
        grouped.items(), key=lambda item: (item[0][0], item[0][1] or "")
    ):
        forward: dict[str, int] = defaultdict(int)
        reverse: dict[str, int] = defaultdict(int)
        for receipt in receipts:
            for item in receipt.items:
                if item.kind is None:
                    continue
                target = forward if item.direction == "give" else reverse
                target[item.kind.value] += 1
        context, history = _context(
            layer=CivilizationLayer.TRADE,
            evidence_class=CivilizationEvidenceClass.ANALYTICAL,
            owner_id=None,
            row_id=f"trade:{'|'.join(participants)}:{location or 'nonspatial'}",
            source_refs=tuple(_event_ref(item) for item in receipts),
            boundary_tick=boundary_tick,
            window=window,
            coverage=coverage,
        )
        rows.append(
            CivilizationTradeRow(
                context,
                history,
                participants,
                len(receipts),
                tuple(
                    CivilizationItemCount(kind=ItemKind(kind), count=count)
                    for kind, count in sorted(
                        ((key, value) for key, value in forward.items()),
                        key=lambda item: item[0],
                    )
                ),
                tuple(
                    CivilizationItemCount(kind=ItemKind(kind), count=count)
                    for kind, count in sorted(
                        ((key, value) for key, value in reverse.items()),
                        key=lambda item: item[0],
                    )
                ),
                location,
            )
        )
    return tuple(sorted(rows, key=lambda row: row.context.row_id))


def _owner_living(inventory: CivilizationOwnerInventory) -> bool:
    return inventory.living


def _channel_state(
    inventory: CivilizationOwnerInventory,
    channel: CivilizationInventoryChannel,
) -> CivilizationCoverageState:
    for row in inventory.channels:
        if row.channel is channel:
            return row.coverage.state
    return CivilizationCoverageState.UNAVAILABLE


def _inventory_coverage(
    inventories: tuple[CivilizationOwnerInventory, ...],
    channel: CivilizationInventoryChannel,
) -> CivilizationCoverage:
    states = {
        _channel_state(inventory, channel)
        for inventory in inventories
        if inventory.living
    }
    if not states or states == {CivilizationCoverageState.DISABLED}:
        return CivilizationCoverage(CivilizationCoverageState.DISABLED, "capture_off")
    if states == {CivilizationCoverageState.COMPLETE}:
        return CivilizationCoverage(CivilizationCoverageState.COMPLETE)
    if CivilizationCoverageState.COMPLETE not in states and (
        CivilizationCoverageState.UNAVAILABLE in states
        or CivilizationCoverageState.PARTIAL in states
    ):
        return CivilizationCoverage(
            CivilizationCoverageState.UNAVAILABLE, "capture_gap"
        )
    return CivilizationCoverage(
        CivilizationCoverageState.PARTIAL, "partial_owner_coverage"
    )


def _inventory_ref(
    owner_id: str, source_id: str, *, tick: int
) -> CivilizationSourceRef:
    return CivilizationSourceRef("inventory", source_id, tick, owner_id=owner_id)


def compose_culture_rows(
    boundary: CivilizationBoundaryInput,
) -> tuple[CivilizationCultureRow, ...]:
    inventories = boundary.owner_inventories
    boundary_tick = boundary.cursor.tick
    window = CivilizationWindow(boundary_tick, boundary_tick)
    rows: list[CivilizationCultureRow] = []
    for channel, representation in _CULTURAL_CHANNEL_BY_REPRESENTATION.items():
        field = {
            CivilizationInventoryChannel.CULTURAL_FEATURES: "cultural_traits",
            CivilizationInventoryChannel.TERMINOLOGY: "terminology",
            CivilizationInventoryChannel.NARRATIVES: "narratives",
        }[channel]
        living = tuple(inventory for inventory in inventories if inventory.living)
        eligible = tuple(
            inventory
            for inventory in living
            if _channel_state(inventory, channel) is CivilizationCoverageState.COMPLETE
        )
        unavailable = tuple(
            inventory
            for inventory in living
            if _channel_state(inventory, channel)
            in {
                CivilizationCoverageState.UNAVAILABLE,
                CivilizationCoverageState.PARTIAL,
            }
        )
        carrier_map: dict[str, set[str]] = defaultdict(set)
        for inventory in eligible:
            for trait in getattr(inventory, field):
                carrier_map[trait.representation_id].add(inventory.owner_id)
        denominator = len(eligible)
        coverage = (
            CivilizationCoverage(CivilizationCoverageState.COMPLETE)
            if not unavailable
            else CivilizationCoverage(
                CivilizationCoverageState.PARTIAL, "partial_owner_coverage"
            )
        )
        for representation_id in sorted(carrier_map):
            carriers = tuple(sorted(carrier_map[representation_id]))
            proportion = (
                len(carriers) / denominator if denominator and not unavailable else None
            )
            context, history = _context(
                layer=CivilizationLayer.CULTURE,
                evidence_class=CivilizationEvidenceClass.ANALYTICAL,
                owner_id=None,
                row_id=f"culture:{channel.value}:{representation_id}",
                source_refs=tuple(
                    _inventory_ref(owner, representation_id, tick=boundary_tick)
                    for owner in carriers
                ),
                boundary_tick=boundary_tick,
                window=window,
                coverage=coverage,
            )
            rows.append(
                CivilizationCultureRow(
                    context,
                    history,
                    f"{channel.value}:{representation_id}",
                    representation,
                    "living_population",
                    len(carriers),
                    carriers,
                    denominator or None,
                    len(unavailable),
                    proportion,
                )
            )
            owners_by_location: dict[str, list[str]] = defaultdict(list)
            for body in boundary.bodies:
                if body.living and body.owner_id:
                    owners_by_location[body.location_id].append(body.owner_id)
            for location_id in sorted(owners_by_location):
                local_owners = tuple(sorted(set(owners_by_location[location_id])))
                local_eligible = tuple(
                    owner
                    for owner in local_owners
                    if owner in {item.owner_id for item in eligible}
                )
                local_unavailable = tuple(
                    owner
                    for owner in local_owners
                    if owner in {item.owner_id for item in unavailable}
                )
                local_carriers = tuple(
                    owner for owner in local_eligible if owner in set(carriers)
                )
                if not local_carriers and not local_unavailable:
                    continue
                local_proportion = (
                    len(local_carriers) / len(local_eligible)
                    if local_eligible and not local_unavailable
                    else None
                )
                local_coverage = (
                    CivilizationCoverage(CivilizationCoverageState.COMPLETE)
                    if not local_unavailable
                    else CivilizationCoverage(
                        CivilizationCoverageState.PARTIAL,
                        "partial_owner_coverage",
                    )
                )
                local_context, local_history = _context(
                    layer=CivilizationLayer.CULTURE,
                    evidence_class=CivilizationEvidenceClass.ANALYTICAL,
                    owner_id=None,
                    row_id=(
                        f"culture:{channel.value}:{representation_id}:loc:{location_id}"
                    ),
                    source_refs=tuple(
                        _inventory_ref(owner, representation_id, tick=boundary_tick)
                        for owner in local_carriers
                    ),
                    anchors=(
                        CivilizationAnchor(
                            CivilizationAnchorKind.LOCATION,
                            location_id,
                            None,
                            CivilizationSourceRef("scene", location_id, boundary_tick),
                            boundary_tick,
                        ),
                    ),
                    boundary_tick=boundary_tick,
                    window=window,
                    coverage=local_coverage,
                )
                rows.append(
                    CivilizationCultureRow(
                        local_context,
                        local_history,
                        f"{channel.value}:{representation_id}",
                        representation,
                        "location_presence",
                        len(local_carriers),
                        local_carriers,
                        len(local_eligible) or None,
                        len(local_unavailable),
                        local_proportion,
                    )
                )
    return tuple(sorted(rows, key=lambda row: row.context.row_id))


def _technology_attribution(
    entry: CivilizationOwnerKnowledge,
) -> tuple[
    Literal["attributable", "unknown", "ambiguous", "rediscovery"],
    Literal["practice", "teaching", "record", "observation", "unknown"],
    str | None,
    str | None,
]:
    if entry.origin == "independent_discovery":
        return ("rediscovery", "practice", None, None)
    if entry.origin == "written_record":
        modality: Literal[
            "practice", "teaching", "record", "observation", "unknown"
        ] = "record"
    elif entry.origin == "teaching":
        modality = "teaching"
    elif entry.origin in {"imitation", "reconstruction"}:
        modality = "observation"
    else:
        modality = "practice"
    source_owner = entry.teacher_agent_id or entry.source_agent_id
    source_knowledge = (
        entry.parent_entry_ids[0] if len(entry.parent_entry_ids) == 1 else None
    )
    if source_owner is not None and source_knowledge is not None:
        return ("attributable", modality, source_owner, source_knowledge)
    if entry.parent_entry_ids and len(entry.parent_entry_ids) > 1:
        return ("ambiguous", modality, None, None)
    return ("unknown", modality, None, None)


def compose_technology_rows(
    boundary: CivilizationBoundaryInput,
) -> tuple[CivilizationTechnologyRow, ...]:
    inventories = boundary.owner_inventories
    boundary_tick = boundary.cursor.tick
    window = CivilizationWindow(boundary_tick, boundary_tick)
    channel = CivilizationInventoryChannel.PRACTICAL_KNOWLEDGE
    living = tuple(inventory for inventory in inventories if inventory.living)
    eligible = tuple(
        inventory
        for inventory in living
        if _channel_state(inventory, channel) is CivilizationCoverageState.COMPLETE
    )
    coverage = _inventory_coverage(inventories, channel)
    living_holders: dict[str, int] = defaultdict(int)
    for inventory in eligible:
        for entry in inventory.knowledge:
            if entry.active:
                living_holders[entry.content_key] += 1
    rows: list[CivilizationTechnologyRow] = []
    for inventory in inventories:
        if _channel_state(inventory, channel) is not CivilizationCoverageState.COMPLETE:
            continue
        for entry in inventory.knowledge:
            if entry.acquired_tick >= boundary_tick:
                continue
            attribution, modality, source_owner, source_knowledge = (
                _technology_attribution(entry)
            )
            acquisition = min(boundary_tick, entry.acquired_tick + 1)
            context, history = _context(
                layer=CivilizationLayer.TECHNOLOGY,
                evidence_class=CivilizationEvidenceClass.ANALYTICAL,
                owner_id=None,
                row_id=f"technology:{inventory.owner_id}:{entry.entry_id}",
                source_refs=(
                    CivilizationSourceRef(
                        "knowledge",
                        entry.entry_id,
                        entry.acquired_tick,
                        owner_id=inventory.owner_id,
                    ),
                ),
                boundary_tick=boundary_tick,
                window=window,
                coverage=coverage,
            )
            rows.append(
                CivilizationTechnologyRow(
                    context,
                    history,
                    entry.content_key,
                    inventory.owner_id,
                    "held" if entry.active else "lost",
                    acquisition,
                    attribution,
                    modality,
                    source_owner,
                    source_knowledge,
                    living_holders.get(entry.content_key),
                    len(eligible) or None,
                )
            )
    return tuple(sorted(rows, key=lambda row: row.context.row_id))


def compose_group_rows(
    boundary: CivilizationBoundaryInput,
) -> tuple[CivilizationGroupRow, ...]:
    inventories = boundary.owner_inventories
    boundary_tick = boundary.cursor.tick
    window = CivilizationWindow(boundary_tick, boundary_tick)
    subjective: list[CivilizationGroupRow] = []
    for inventory in inventories:
        if (
            _channel_state(inventory, CivilizationInventoryChannel.GROUPS)
            is not CivilizationCoverageState.COMPLETE
        ):
            continue
        for group in inventory.groups:
            context, history = _context(
                layer=CivilizationLayer.SOCIAL_GROUPS,
                evidence_class=CivilizationEvidenceClass.SUBJECTIVE,
                owner_id=inventory.owner_id,
                row_id=f"group:{inventory.owner_id}:{group.belief_id}",
                source_refs=(
                    CivilizationSourceRef(
                        "group",
                        group.belief_id,
                        boundary_tick,
                        owner_id=inventory.owner_id,
                    ),
                ),
                boundary_tick=boundary_tick,
                window=window,
                coverage=CivilizationCoverage(CivilizationCoverageState.COMPLETE),
            )
            subjective.append(
                CivilizationGroupRow(
                    context,
                    history,
                    group.concept_id or group.belief_id,
                    "owner_belief",
                    len(group.member_ids),
                    group.member_ids,
                    (),
                )
            )
    analytical: list[CivilizationGroupRow] = []
    by_location: dict[str, set[str]] = defaultdict(set)
    for body in boundary.bodies:
        if body.living and body.owner_id:
            by_location[body.location_id].add(body.owner_id)
    for location, members in sorted(by_location.items()):
        if len(members) < 2:
            continue
        ordered = tuple(sorted(members))
        ref = CivilizationSourceRef("scene", location, boundary_tick)
        context, history = _context(
            layer=CivilizationLayer.SOCIAL_GROUPS,
            evidence_class=CivilizationEvidenceClass.ANALYTICAL,
            owner_id=None,
            row_id=f"group:residence:{location}",
            source_refs=(ref,),
            boundary_tick=boundary_tick,
            window=flow_window(boundary_tick),
            coverage=CivilizationCoverage(CivilizationCoverageState.COMPLETE),
        )
        analytical.append(
            CivilizationGroupRow(
                context,
                history,
                f"residence:{location}",
                "interaction_residence",
                len(ordered),
                ordered,
                ("interaction", "trust"),
            )
        )
    return tuple(sorted(subjective + analytical, key=lambda row: row.context.row_id))


def _decay_rows(
    inventories: tuple[CivilizationOwnerInventory, ...],
) -> tuple[InstitutionTemporalRow, ...]:
    rows: dict[tuple[str, str, int], InstitutionTemporalRow] = {}
    for inventory in inventories:
        for sample in inventory.decay_samples:
            key = (inventory.owner_id, sample.local_pattern_id, sample.observation_tick)
            row = InstitutionTemporalRow(
                inventory.owner_id,
                sample.local_pattern_id,
                sample.observation_tick,
                sample.source_first_tick,
                sample.source_last_tick,
                sample.role_recognition,
                sample.procedure_recurrence,
                sample.social_expectation,
                sample.legitimacy_belief,
                sample.succession_observed,
                sample.generational_continuity,
                sample.recognized,
                observed_cohort=sample.observed_cohort,
                supporters=sample.supporters,
                participant_actions=sample.participant_actions,
                performed_procedure_keys=sample.performed_procedure_keys,
                succession_transitions=sample.succession_transitions,
                completed_transitions=sample.completed_transitions,
                structural_components=sample.structural_components,
                context_key=sample.context_key,
                office_id=sample.office_id,
                covered=sample.covered,
                pruned=sample.pruned,
            )
            previous = rows.get(key)
            if previous is not None and previous != row:
                raise ValueError("source_conflict")
            rows[key] = row
    return tuple(rows[key] for key in sorted(rows))


def compose_institution_rows(
    boundary: CivilizationBoundaryInput,
) -> tuple[CivilizationInstitutionRow, ...]:
    inventories = boundary.owner_inventories
    boundary_tick = boundary.cursor.tick
    window = CivilizationWindow(boundary_tick, boundary_tick)
    witnesses = {
        (witness.owner_id, witness.concept_id, witness.evidence_id): witness
        for witness in boundary.grounding_witnesses
    }
    rows: list[CivilizationInstitutionRow] = []
    for inventory in inventories:
        for concept in inventory.concepts:
            anchors = []
            for evidence in concept.evidence:
                witness = witnesses.get(
                    (inventory.owner_id, concept.concept_id, evidence.evidence_id)
                )
                if witness is None:
                    continue
                anchors.append(
                    CivilizationAnchor(
                        (
                            CivilizationAnchorKind.PROJECT
                            if witness.source_kind == "project"
                            else CivilizationAnchorKind.REPOSITORY
                        ),
                        witness.location_id,
                        witness.source_id,
                        CivilizationSourceRef(
                            witness.source_kind,
                            witness.source_id,
                            witness.evidence_tick,
                            owner_id=inventory.owner_id,
                        ),
                        witness.evidence_tick,
                    )
                )
            context, history = _context(
                layer=CivilizationLayer.INSTITUTIONS,
                evidence_class=CivilizationEvidenceClass.SUBJECTIVE,
                owner_id=inventory.owner_id,
                row_id=f"institution:concept:{inventory.owner_id}:{concept.concept_id}",
                source_refs=(
                    CivilizationSourceRef(
                        "concept",
                        concept.concept_id,
                        concept.last_tick,
                        owner_id=inventory.owner_id,
                    ),
                ),
                anchors=tuple(anchors),
                boundary_tick=boundary_tick,
                window=window,
                coverage=CivilizationCoverage(CivilizationCoverageState.COMPLETE),
            )
            rows.append(
                CivilizationInstitutionRow(
                    context,
                    history,
                    concept.concept_id,
                    inventory.owner_id,
                    concept.concept_id,
                    "concept",
                    cast(
                        _InstitutionStatus,
                        {
                            "candidate": "emerging",
                            "recognized": "recognized",
                            "fading": "weakening",
                            "retired": "collapsed",
                        }.get(concept.status, "censored"),
                    ),
                    concept.first_tick,
                    concept.last_tick,
                    concept.first_tick,
                    concept.last_tick,
                )
            )
        for office in inventory.offices:
            context, history = _context(
                layer=CivilizationLayer.INSTITUTIONS,
                evidence_class=CivilizationEvidenceClass.SUBJECTIVE,
                owner_id=inventory.owner_id,
                row_id=f"institution:office:{inventory.owner_id}:{office.office_id}",
                source_refs=(
                    CivilizationSourceRef(
                        "office",
                        office.office_id,
                        office.last_tick,
                        owner_id=inventory.owner_id,
                    ),
                ),
                boundary_tick=boundary_tick,
                window=window,
                coverage=CivilizationCoverage(CivilizationCoverageState.COMPLETE),
            )
            rows.append(
                CivilizationInstitutionRow(
                    context,
                    history,
                    office.office_id,
                    inventory.owner_id,
                    office.office_id,
                    "office",
                    cast(
                        _InstitutionStatus,
                        {
                            "proposed": "emerging",
                            "recognized": "recognized",
                            "disputed": "contested",
                            "vacant": "vacant",
                            "fading": "weakening",
                            "abandoned": "lost",
                        }.get(office.status, "censored"),
                    ),
                    office.first_tick,
                    office.last_tick,
                    office.first_tick,
                    office.last_tick,
                )
            )
    if boundary_tick > 0:
        decay_rows = _decay_rows(inventories)
        if decay_rows:
            lifecycle = compute_institutional_decay(
                decay_rows, as_of_tick=boundary_tick - 1
            )
            lineage = compute_institution_lineage(
                decay_rows,
                as_of_tick=boundary_tick - 1,
                lifecycle=lifecycle,
            )
            for episode in lineage.episodes:
                context, history = _context(
                    layer=CivilizationLayer.INSTITUTIONS,
                    evidence_class=CivilizationEvidenceClass.ANALYTICAL,
                    owner_id=None,
                    row_id=f"institution:episode:{episode.episode_id}",
                    source_refs=(
                        CivilizationSourceRef(
                            "institution_episode",
                            episode.episode_id,
                            episode.last_tick,
                        ),
                    ),
                    boundary_tick=boundary_tick,
                    window=CivilizationWindow(0, boundary_tick),
                    coverage=CivilizationCoverage(CivilizationCoverageState.COMPLETE),
                )
                rows.append(
                    CivilizationInstitutionRow(
                        context,
                        history,
                        episode.episode_id,
                        episode.owner_id,
                        episode.episode_id,
                        "episode",
                        cast(_InstitutionStatus, episode.state),
                        episode.first_tick,
                        episode.last_tick,
                        episode.first_tick,
                        episode.last_tick,
                    )
                )
    return tuple(sorted(rows, key=lambda row: row.context.row_id))


def compose_markers(
    boundaries: tuple[CivilizationBoundaryInput, ...],
    batches: tuple[CivilizationEventBatch, ...],
    *,
    boundary_tick: int,
) -> tuple[CivilizationMarker, ...]:
    markers: list[CivilizationMarker] = []
    ordered = tuple(sorted(boundaries, key=lambda frame: frame.cursor.tick))
    for tick in sorted(frame.cursor.tick for frame in ordered):
        if tick != boundary_tick or tick < 4:
            continue
        prefix = tuple(frame for frame in ordered if frame.cursor.tick <= tick)
        prior_prefix = tuple(
            frame for frame in ordered if frame.cursor.tick <= tick - 1
        )
        if not prior_prefix or prior_prefix[-1].cursor.tick != tick - 1:
            continue
        current_rows = {
            row.candidate_id: row
            for row in compose_settlement_rows(prefix, boundary_tick=tick)
        }
        prior_rows = {
            row.candidate_id: row
            for row in compose_settlement_rows(prior_prefix, boundary_tick=tick - 1)
        }
        for candidate_id in sorted(current_rows):
            row = current_rows[candidate_id]
            prior = prior_rows.get(candidate_id)
            if prior is None or row.status not in {"active", "inactive"}:
                continue
            if prior.status not in {"active", "inactive"} or prior.status == row.status:
                continue
            kind = (
                CivilizationMarkerType.SETTLEMENT_ACTIVATED
                if row.status == "active"
                else CivilizationMarkerType.SETTLEMENT_DEACTIVATED
            )
            source = CivilizationSourceRef("scene", row.location_id, tick - 1)
            markers.append(
                CivilizationMarker(
                    f"marker:settlement:{row.location_id}:{tick}:{row.status}",
                    kind,
                    tick,
                    CivilizationEvidenceClass.ANALYTICAL,
                    None,
                    CivilizationLayer.SETTLEMENTS,
                    row.context.row_id,
                    (source,),
                    CivilizationCoverage(CivilizationCoverageState.COMPLETE),
                )
            )
    window = flow_window(boundary_tick)
    for batch in _filtered_batches(batches, window):
        for receipt in batch.receipts:
            if receipt.kind is CivilizationEventKind.JOURNEY_STARTED:
                kind = CivilizationMarkerType.JOURNEY_STARTED
            elif receipt.kind is CivilizationEventKind.JOURNEY_ARRIVED:
                kind = CivilizationMarkerType.JOURNEY_ARRIVED
            elif receipt.kind is CivilizationEventKind.JOURNEY_ENDED:
                kind = CivilizationMarkerType.JOURNEY_ENDED
            else:
                continue
            if receipt.tick + 1 != boundary_tick:
                continue
            markers.append(
                CivilizationMarker(
                    f"marker:migration:{receipt.event_id}",
                    kind,
                    receipt.tick + 1,
                    CivilizationEvidenceClass.OBJECTIVE,
                    None,
                    CivilizationLayer.MIGRATION,
                    f"migration:{receipt.journey_id}",
                    (_event_ref(receipt),),
                    CivilizationCoverage(CivilizationCoverageState.COMPLETE),
                )
            )
    frame = next(
        (item for item in boundaries if item.cursor.tick == boundary_tick), None
    )
    if frame is not None:
        for inventory in frame.owner_inventories:
            for entry in inventory.knowledge:
                acquisition = entry.acquired_tick + 1
                if acquisition != boundary_tick or entry.acquired_tick >= boundary_tick:
                    continue
                markers.append(
                    CivilizationMarker(
                        f"marker:technology:{inventory.owner_id}:{entry.entry_id}",
                        CivilizationMarkerType.TECHNOLOGY_ACQUIRED,
                        boundary_tick,
                        CivilizationEvidenceClass.SUBJECTIVE,
                        inventory.owner_id,
                        CivilizationLayer.TECHNOLOGY,
                        f"technology:{inventory.owner_id}:{entry.entry_id}",
                        (
                            CivilizationSourceRef(
                                "knowledge",
                                entry.entry_id,
                                entry.acquired_tick,
                                owner_id=inventory.owner_id,
                            ),
                        ),
                        CivilizationCoverage(CivilizationCoverageState.COMPLETE),
                    )
                )
        previous = next(
            (item for item in boundaries if item.cursor.tick == boundary_tick - 1),
            None,
        )
        if previous is not None:
            prior_concepts = {
                (inventory.owner_id, concept.concept_id): concept
                for inventory in previous.owner_inventories
                for concept in inventory.concepts
            }
            for inventory in frame.owner_inventories:
                for concept in inventory.concepts:
                    prior_concept = prior_concepts.get(
                        (inventory.owner_id, concept.concept_id)
                    )
                    if prior_concept is None or prior_concept.status == concept.status:
                        continue
                    markers.append(
                        CivilizationMarker(
                            f"marker:institution:{inventory.owner_id}:"
                            f"{concept.concept_id}:{concept.status}",
                            CivilizationMarkerType.INSTITUTION_TRANSITION,
                            boundary_tick,
                            CivilizationEvidenceClass.SUBJECTIVE,
                            inventory.owner_id,
                            CivilizationLayer.INSTITUTIONS,
                            f"institution:concept:{inventory.owner_id}:"
                            f"{concept.concept_id}",
                            (
                                CivilizationSourceRef(
                                    "concept",
                                    concept.concept_id,
                                    concept.last_tick,
                                    owner_id=inventory.owner_id,
                                ),
                            ),
                            CivilizationCoverage(CivilizationCoverageState.COMPLETE),
                        )
                    )
    return tuple(sorted(markers, key=lambda row: (row.seek_boundary, row.marker_id)))
