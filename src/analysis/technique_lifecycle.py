"""Analysis-only technique lifecycle over detached practical-knowledge audits.

States are research labels. They are not world rules and they are not
agent-visible facts.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.knowledge_genealogy import (
    build_knowledge_genealogy_graph,
    query_who_currently_knows,
)
from analysis.models import AppliedActionRow
from simulation.runner_models import TechniqueLifecycleSpec
from world.identifiers import require_exact_nonneg_int, require_stable_id
from world.production import (
    HeldItemKindInput,
    HeldItemNameInput,
    ResourceNameInput,
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.technique_lifecycle")
_UNKNOWN_PLACE: Final[str] = "location:unknown"
_INTACT: Final[frozenset[str]] = frozenset(
    {"intact", "damaged", "partially_lost"}
)
_TEACHING_ORIGINS: Final[frozenset[str]] = frozenset({"teaching", "imitation"})


class TechniqueLifecycleState(StrEnum):
    """Closed lifecycle state for one technique in one scope."""

    DISCOVERED = "discovered"
    KNOWN = "known"
    DIFFUSING = "diffusing"
    RARE = "rare"
    LOCALLY_EXTINCT = "locally_extinct"
    GLOBALLY_LOST = "globally_lost"
    REDISCOVERED = "rediscovered"


class TechniqueLossCause(StrEnum):
    """Disappearance cause. A set, not a state."""

    HOLDERS_DIED = "holders_died"
    RECORDS_DESTROYED = "records_destroyed"
    MATERIALS_ABSENT = "materials_absent"
    TEACHING_CHAIN_FAILED = "teaching_chain_failed"


@dataclass(frozen=True, slots=True)
class TechniqueLifecycleSnapshot:
    """One technique in one scope at one tick. Counts and ids only."""

    content_key: str
    scope: str
    state: TechniqueLifecycleState
    known_by_n: int
    performable: bool | None
    causes: frozenset[TechniqueLossCause]
    lineage_root_ids: tuple[str, ...]
    prior_lineage_root_id: str | None = None
    new_lineage_root_id: str | None = None
    location_count: int = 0
    living_hop_sum: int = 0
    living_hop_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "content_key", require_stable_id("content_key", self.content_key)
        )
        object.__setattr__(self, "scope", require_stable_id("scope", self.scope))
        if type(self.state) is not TechniqueLifecycleState:
            raise ValueError(
                "unknown technique lifecycle state "
                "(code=technique_lifecycle_state_invalid)"
            )
        object.__setattr__(
            self,
            "known_by_n",
            require_exact_nonneg_int("known_by_n", self.known_by_n),
        )
        if self.performable is not None and type(self.performable) is not bool:
            raise TypeError("performable must be bool or None")
        if type(self.causes) is not frozenset or any(
            type(cause) is not TechniqueLossCause for cause in self.causes
        ):
            raise TypeError("causes must be a frozenset of TechniqueLossCause")
        object.__setattr__(
            self,
            "location_count",
            require_exact_nonneg_int("location_count", self.location_count),
        )
        object.__setattr__(
            self,
            "living_hop_sum",
            require_exact_nonneg_int("living_hop_sum", self.living_hop_sum),
        )
        object.__setattr__(
            self,
            "living_hop_count",
            require_exact_nonneg_int("living_hop_count", self.living_hop_count),
        )
        _LOG.debug(
            "technique_lifecycle_snapshot state=%s known_by_n=%s",
            self.state.value,
            self.known_by_n,
        )


@dataclass(frozen=True, slots=True)
class TechniqueGrounding:
    """Detached holder, record, and teaching facts for one key and scope."""

    content_key: str
    scope: str
    living_holder_ids: tuple[str, ...]
    location_ids: tuple[str, ...]
    intact_record_count: int
    teaching_chain_intact: bool


@dataclass(frozen=True, slots=True)
class TechniqueDiffusionRow:
    """Researcher query row. Empty root ids unless the state is rediscovered."""

    content_key: str
    as_of_tick: int
    state: TechniqueLifecycleState
    known_by_n: int
    location_count: int
    causes: frozenset[TechniqueLossCause]
    performable: bool | None
    prior_lineage_root_id: str
    new_lineage_root_id: str


def _token(value: object) -> str | None:
    if type(value) is str and value.strip() == value and value:
        return value
    nested = getattr(value, "value", None)
    if type(nested) is str and nested:
        return nested
    return None


def _entries(audits: Sequence[object]) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for raw in audits:
        owner = _token(getattr(raw, "owner_id", None))
        content_key = _token(getattr(raw, "content_key", None))
        origin = _token(getattr(raw, "origin", None))
        root = _token(getattr(raw, "lineage_root_id", None))
        if None in (owner, content_key, origin, root):
            continue
        acquired = getattr(raw, "acquired_tick", 0)
        hop = getattr(raw, "hop_index", 0)
        if isinstance(acquired, bool) or type(acquired) is not int:
            continue
        if isinstance(hop, bool) or type(hop) is not int:
            continue
        refs = getattr(raw, "evidence_refs", ()) or ()
        if isinstance(refs, (str, bytes)):
            refs = ()
        rows.append(
            {
                "owner_id": owner,
                "content_key": content_key,
                "origin": origin,
                "lineage_root_id": root,
                "hop_index": hop,
                "acquired_tick": acquired,
                "active": bool(getattr(raw, "active", True)),
                "evidence_refs": tuple(str(item) for item in refs),
                "capability_anchor": _token(getattr(raw, "capability_anchor", None)),
            }
        )
    return tuple(rows)


def _alive(owner: str, tick: int, deaths: Mapping[str, int]) -> bool:
    death = deaths.get(owner)
    return death is None or death > tick


def _place(
    owner: str, tick: int, actions: Sequence[AppliedActionRow]
) -> str:
    best: AppliedActionRow | None = None
    for row in actions:
        if row.agent_id != owner or row.tick > tick or row.location_id is None:
            continue
        if best is None or (row.tick, row.ordinal) >= (best.tick, best.ordinal):
            best = row
    if best is None or best.location_id is None:
        return _UNKNOWN_PLACE
    return best.location_id


def _living_hop_stats(
    entries: Sequence[Mapping[str, object]],
    holders: Sequence[str],
    as_of: int,
) -> tuple[int, int]:
    """Sum of the latest living hop and the number of those holders."""
    total = 0
    count = 0
    for owner in holders:
        chosen: tuple[int, int] | None = None
        for entry in entries:
            if str(entry["owner_id"]) != owner or not entry["active"]:
                continue
            acquired = entry["acquired_tick"]
            hop = entry["hop_index"]
            if type(acquired) is not int or type(hop) is not int or acquired > as_of:
                continue
            if chosen is None or acquired >= chosen[0]:
                chosen = (acquired, hop)
        if chosen is not None:
            total += chosen[1]
            count += 1
    return total, count


def _artifacts(rows: Sequence[object]) -> tuple[dict[str, object], ...]:
    parsed: list[dict[str, object]] = []
    for raw in rows:
        if isinstance(raw, Mapping):
            artifact_id = _token(raw.get("artifact_id"))
            integrity = _token(raw.get("integrity")) or "intact"
            location_id = _token(raw.get("location_id"))
            destroyed = raw.get("destroyed_tick")
        else:
            artifact_id = _token(getattr(raw, "artifact_id", None))
            integrity = _token(getattr(raw, "integrity", None)) or "intact"
            location_id = _token(getattr(raw, "location_id", None))
            destroyed = getattr(raw, "destroyed_tick", None)
        if artifact_id is None:
            continue
        destroyed_tick = (
            destroyed
            if type(destroyed) is int and not isinstance(destroyed, bool)
            else None
        )
        parsed.append(
            {
                "artifact_id": artifact_id,
                "integrity": integrity.lower(),
                "location_id": location_id,
                "destroyed_tick": destroyed_tick,
            }
        )
    return tuple(parsed)


def _record_intact(row: Mapping[str, object], tick: int) -> bool:
    destroyed = row["destroyed_tick"]
    integrity = str(row["integrity"])
    if type(destroyed) is int:
        return tick < destroyed and integrity in _INTACT | frozenset({"destroyed"})
    return integrity in _INTACT


def _cited_ids(entries: Sequence[Mapping[str, object]]) -> set[str]:
    found: set[str] = set()
    for entry in entries:
        refs = entry["evidence_refs"]
        if not isinstance(refs, tuple):
            continue
        for ref in refs:
            if ref.startswith("artifact:"):
                found.add(ref.removeprefix("artifact:"))
    return found


def _stats_at(
    entries: Sequence[Mapping[str, object]],
    artifacts: Sequence[Mapping[str, object]],
    actions: Sequence[AppliedActionRow],
    deaths: Mapping[str, int],
    tick: int,
    *,
    scope: str,
) -> tuple[int, frozenset[str], int, tuple[str, ...]]:
    holders: list[str] = []
    places: set[str] = set()
    for entry in entries:
        owner = str(entry["owner_id"])
        acquired = entry["acquired_tick"]
        if type(acquired) is not int or acquired > tick or not entry["active"]:
            continue
        if not _alive(owner, tick, deaths):
            continue
        place = _place(owner, tick, actions)
        if scope != "global" and place != scope.removeprefix("location:"):
            continue
        if owner not in holders:
            holders.append(owner)
        places.add(place)
    cited = _cited_ids(entries)
    intact = 0
    for row in artifacts:
        if str(row["artifact_id"]) not in cited or not _record_intact(row, tick):
            continue
        location_id = row["location_id"]
        if scope != "global" and location_id != scope.removeprefix("location:"):
            continue
        intact += 1
    return len(holders), frozenset(places), intact, tuple(sorted(holders))


def ground_technique_lifecycle(
    audits: Sequence[object],
    *,
    as_of_tick: int,
    death_ticks: Mapping[str, int] | None = None,
    artifact_rows: Sequence[object] = (),
    applied_actions: Sequence[AppliedActionRow] = (),
    mentorship_audits: Sequence[object] = (),
) -> tuple[TechniqueGrounding, ...]:
    """Living holders, places, intact cited records, and teaching-chain flags."""
    tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    deaths = dict(death_ticks or {})
    entries = _entries(audits)
    graph = build_knowledge_genealogy_graph(
        audits, as_of_tick=tick, death_ticks=deaths
    )
    artifacts = _artifacts(artifact_rows)
    keys = tuple(dict.fromkeys(str(row["content_key"]) for row in entries))
    grounded: list[TechniqueGrounding] = []
    for key in keys:
        key_entries = tuple(row for row in entries if row["content_key"] == key)
        living = query_who_currently_knows(graph, content_key=key)
        living_ids = tuple(agent for _depth, agent in living.items)
        _count, places, intact, _holders = _stats_at(
            key_entries, artifacts, applied_actions, deaths, tick, scope="global"
        )
        teaching = _teaching_intact(key_entries, mentorship_audits, living_ids, key)
        row = TechniqueGrounding(
            content_key=key,
            scope="global",
            living_holder_ids=living_ids,
            location_ids=tuple(sorted(places)),
            intact_record_count=intact,
            teaching_chain_intact=teaching,
        )
        _LOG.debug(
            "technique_grounding holder_count=%s intact_record_count=%s "
            "teaching_chain_intact=%s",
            len(row.living_holder_ids),
            row.intact_record_count,
            row.teaching_chain_intact,
        )
        grounded.append(row)
    return tuple(grounded)


def _teaching_intact(
    entries: Sequence[Mapping[str, object]],
    mentorship: Sequence[object],
    living_ids: Sequence[str],
    content_key: str,
) -> bool:
    living = set(living_ids)
    for entry in entries:
        if entry["origin"] in _TEACHING_ORIGINS and str(entry["owner_id"]) in living:
            return True
    for bond in mentorship:
        key = _token(getattr(bond, "content_key", None))
        if key not in (None, content_key):
            continue
        mentor = _token(getattr(bond, "mentor_id", None))
        if mentor is not None and mentor in living:
            return True
    return False


def _had_teaching_chain(
    entries: Sequence[Mapping[str, object]],
    mentorship: Sequence[object],
    content_key: str,
) -> bool:
    if any(entry["origin"] in _TEACHING_ORIGINS for entry in entries):
        return True
    for bond in mentorship:
        key = _token(getattr(bond, "content_key", None))
        if key in (None, content_key):
            return True
    return False


def _row_value(row: object, name: str) -> object:
    if isinstance(row, Mapping):
        return row.get(name)
    return getattr(row, name, None)


def _in_scope(location_id: object, scope: str) -> bool:
    if scope == "global":
        return True
    return _token(location_id) == scope.removeprefix("location:")


def evaluate_technique_performable(
    anchors: Sequence[object],
    catalog: object | None,
    node_rows: Sequence[object],
    item_rows: Sequence[object],
    *,
    content_key: str,
    scope: str = "global",
) -> bool | None:
    """True when every anchored recipe can be practiced in scope.

    No anchor for the key omits performable (``None``). Does not mutate world
    state and does not add recipe prerequisites.
    """
    matched = [
        anchor
        for anchor in anchors
        if _token(getattr(anchor, "content_key", None)) == content_key
    ]
    if not matched:
        _LOG.debug(
            "technique_performable content_key_hash=%s performable=%s cause=%s",
            hashlib.sha256(content_key.encode()).hexdigest()[:8],
            "omitted",
            "not_applicable",
        )
        return None
    recipes = ()
    if catalog is not None:
        recipes = tuple(getattr(catalog, "recipes", ()) or ())
    performable = True
    for anchor in matched:
        recipe_id = _token(getattr(anchor, "recipe_id", None))
        recipe = next(
            (
                item
                for item in recipes
                if _token(getattr(getattr(item, "recipe_id", None), "value", None))
                == recipe_id
            ),
            None,
        )
        if recipe is None or not _recipe_available(recipe, node_rows, item_rows, scope):
            performable = False
            break
    _LOG.debug(
        "technique_performable content_key_hash=%s performable=%s cause=%s",
        hashlib.sha256(content_key.encode()).hexdigest()[:8],
        performable,
        "materials_absent" if not performable else "present",
    )
    return performable


def _recipe_available(
    recipe: object,
    node_rows: Sequence[object],
    item_rows: Sequence[object],
    scope: str,
) -> bool:
    for item in tuple(getattr(recipe, "inputs", ()) or ()):
        if not _input_present(item, node_rows, item_rows, scope):
            return False
    tool = getattr(recipe, "tool_role", None)
    if tool is None:
        return True
    role = _token(getattr(tool, "value", tool))
    return any(
        _in_scope(_row_value(row, "location_id"), scope)
        and _token(_row_value(row, "tool_role")) == role
        for row in item_rows
    )


def _input_present(
    item: object,
    node_rows: Sequence[object],
    item_rows: Sequence[object],
    scope: str,
) -> bool:
    if type(item) is ResourceNameInput:
        matched = [
            row
            for row in node_rows
            if _token(_row_value(row, "name")) == item.name
            and _in_scope(_row_value(row, "location_id"), scope)
        ]
        if not matched:
            return False
        return any(float(_row_value(row, "quantity") or 0) > 0 for row in matched)
    if type(item) is HeldItemNameInput:
        return any(
            _token(_row_value(row, "name")) == item.name
            and _in_scope(_row_value(row, "location_id"), scope)
            for row in item_rows
        )
    if type(item) is HeldItemKindInput:
        kind = item.item_kind.value
        return any(
            _token(_row_value(row, "item_kind")) == kind
            and _in_scope(_row_value(row, "location_id"), scope)
            for row in item_rows
        )
    return False


def classify_technique_lifecycle(
    audits: Sequence[object],
    *,
    as_of_tick: int,
    spec: TechniqueLifecycleSpec,
    death_ticks: Mapping[str, int] | None = None,
    artifact_rows: Sequence[object] = (),
    applied_actions: Sequence[AppliedActionRow] = (),
    mentorship_audits: Sequence[object] = (),
    catalog: object | None = None,
    node_rows: Sequence[object] = (),
    item_rows: Sequence[object] = (),
) -> tuple[TechniqueLifecycleSnapshot, ...]:
    """Priority state machine. Pure function of detached rows plus thresholds."""
    tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    window = require_exact_nonneg_int(
        "diffusion_window_ticks", spec.diffusion_window_ticks
    )
    rare_max = require_exact_nonneg_int("rare_max", spec.rare_max)
    latch = require_exact_nonneg_int(
        "rediscovery_latch_ticks", spec.rediscovery_latch_ticks
    )
    anchors = tuple(spec.material_anchors)
    deaths = dict(death_ticks or {})
    entries = _entries(audits)
    artifacts = _artifacts(artifact_rows)
    keys = tuple(dict.fromkeys(str(row["content_key"]) for row in entries))
    snapshots: list[TechniqueLifecycleSnapshot] = []
    for key in keys:
        key_entries = tuple(row for row in entries if row["content_key"] == key)
        performable = evaluate_technique_performable(
            anchors,
            catalog,
            node_rows,
            item_rows,
            content_key=key,
            scope="global",
        )
        scopes = ["global"]
        seen_places: set[str] = set()
        owners = {str(entry["owner_id"]) for entry in key_entries}
        for action in applied_actions:
            if action.agent_id in owners and action.location_id:
                seen_places.add(action.location_id)
        for row in artifacts:
            cited = str(row["artifact_id"]) in _cited_ids(key_entries)
            if cited and row["location_id"]:
                seen_places.add(str(row["location_id"]))
        scopes.extend(f"location:{place}" for place in sorted(seen_places))
        for scope in scopes:
            snapshots.append(
                _classify_scope(
                    key_entries,
                    artifacts=artifacts,
                    actions=applied_actions,
                    deaths=deaths,
                    mentorship=mentorship_audits,
                    as_of=tick,
                    scope=scope,
                    window=window,
                    rare_max=rare_max,
                    latch=latch,
                    performable=performable,
                    content_key=key,
                )
            )
    return tuple(snapshots)


def _classify_scope(
    entries: Sequence[Mapping[str, object]],
    *,
    artifacts: Sequence[Mapping[str, object]],
    actions: Sequence[AppliedActionRow],
    deaths: Mapping[str, int],
    mentorship: Sequence[object],
    as_of: int,
    scope: str,
    window: int,
    rare_max: int,
    latch: int,
    performable: bool | None,
    content_key: str,
) -> TechniqueLifecycleSnapshot:
    ticks = {0, as_of}
    for entry in entries:
        acquired = entry["acquired_tick"]
        if type(acquired) is int and acquired <= as_of:
            ticks.add(acquired)
    for death in deaths.values():
        if death <= as_of:
            ticks.add(death)
    for row in artifacts:
        destroyed = row["destroyed_tick"]
        if type(destroyed) is int and destroyed <= as_of:
            ticks.add(destroyed)
    ordered = tuple(sorted(ticks))
    series = [
        _stats_at(entries, artifacts, actions, deaths, tick, scope=scope)
        for tick in ordered
    ]
    current_n, places, intact, _holders = series[-1]
    extant_flags = [n > 0 or count > 0 for n, _places, count, _ids in series]
    peak = max(item[0] for item in series)
    ever_holder = any(item[0] > 0 for item in series)
    prior_loss = False
    seen_extant = False
    for flag in extant_flags[:-1]:
        if flag:
            seen_extant = True
        elif seen_extant:
            prior_loss = True
    global_series = [
        _stats_at(entries, artifacts, actions, deaths, tick, scope="global")
        for tick in ordered
    ]
    global_extant = [n > 0 or count > 0 for n, _p, count, _i in global_series]
    global_lost_now = not global_extant[-1]
    roots = _rediscovery_roots(
        entries, ordered, global_series, scope, actions, deaths, artifacts
    )
    state = _pick_state(
        current_n=current_n,
        intact=intact,
        extant=current_n > 0 or intact > 0,
        peak=peak,
        places=places,
        prior_loss=prior_loss,
        ever_holder=ever_holder,
        scope=scope,
        global_lost_now=global_lost_now,
        series=series,
        ordered=ordered,
        as_of=as_of,
        window=window,
        rare_max=rare_max,
        latch=latch,
        entries=entries,
        roots=roots,
    )
    causes = _causes(
        state=state,
        entries=entries,
        deaths=deaths,
        artifacts=artifacts,
        as_of=as_of,
        performable=performable,
        mentorship=mentorship,
        content_key=content_key,
        current_n=current_n,
        peak=peak,
        scope=scope,
    )
    prior_root, new_root = _root_pair(entries, roots, state)
    hop_sum, hop_count = _living_hop_stats(entries, _holders, as_of)
    scope_kind = "global" if scope == "global" else "local"
    _LOG.info(
        "technique_state state=%s scope_kind=%s known_by_n=%s",
        state.value,
        scope_kind,
        current_n,
    )
    _LOG.debug(
        "technique_lifecycle_causes causes=%s",
        ",".join(sorted(cause.value for cause in causes)) or "none",
    )
    return TechniqueLifecycleSnapshot(
        content_key=content_key,
        scope=scope,
        state=state,
        known_by_n=current_n,
        performable=performable,
        causes=causes,
        lineage_root_ids=tuple(
            dict.fromkeys(str(entry["lineage_root_id"]) for entry in entries)
        ),
        prior_lineage_root_id=prior_root,
        new_lineage_root_id=new_root,
        location_count=sum(place != _UNKNOWN_PLACE for place in places),
        living_hop_sum=hop_sum,
        living_hop_count=hop_count,
    )


def _rediscovery_roots(
    entries: Sequence[Mapping[str, object]],
    ordered: Sequence[int],
    global_series: Sequence[tuple[int, frozenset[str], int, tuple[str, ...]]],
    scope: str,
    actions: Sequence[AppliedActionRow],
    deaths: Mapping[str, int],
    artifacts: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    lost_before: set[int] = set()
    seen = False
    paired = zip(ordered, global_series, strict=True)
    for tick, (count, _places, intact, _ids) in paired:
        if count > 0 or intact > 0:
            seen = True
        elif seen:
            lost_before.add(tick)
    found: list[Mapping[str, object]] = []
    for entry in entries:
        origin = str(entry["origin"])
        hop = entry["hop_index"]
        acquired = entry["acquired_tick"]
        if type(acquired) is not int or type(hop) is not int:
            continue
        independent = origin == "independent_discovery" and hop == 0
        reconstruction = origin == "reconstruction"
        if not independent and not reconstruction:
            continue
        if origin == "written_record":
            continue
        earlier_loss = any(tick < acquired for tick in lost_before) or any(
            tick < acquired and _was_locally_extinct(
                entries, artifacts, actions, deaths, tick, scope
            )
            for tick in ordered
            if scope != "global"
        )
        if earlier_loss:
            found.append(entry)
    return tuple(found)


def _was_locally_extinct(
    entries: Sequence[Mapping[str, object]],
    artifacts: Sequence[Mapping[str, object]],
    actions: Sequence[AppliedActionRow],
    deaths: Mapping[str, int],
    tick: int,
    scope: str,
) -> bool:
    if scope == "global":
        return False
    count, _places, intact, _ids = _stats_at(
        entries, artifacts, actions, deaths, tick, scope=scope
    )
    return count == 0 and intact == 0


def _pick_state(
    *,
    current_n: int,
    intact: int,
    extant: bool,
    peak: int,
    places: frozenset[str],
    prior_loss: bool,
    ever_holder: bool,
    scope: str,
    global_lost_now: bool,
    series: Sequence[tuple[int, frozenset[str], int, tuple[str, ...]]],
    ordered: Sequence[int],
    as_of: int,
    window: int,
    rare_max: int,
    latch: int,
    entries: Sequence[Mapping[str, object]],
    roots: Sequence[Mapping[str, object]],
) -> TechniqueLifecycleState:
    fresh_root = None
    for entry in roots:
        acquired = entry["acquired_tick"]
        if type(acquired) is int and as_of <= acquired + latch:
            fresh_root = entry
    if extant and fresh_root is not None:
        return TechniqueLifecycleState.REDISCOVERED
    if scope == "global" and not extant:
        return TechniqueLifecycleState.GLOBALLY_LOST
    if scope != "global" and not extant and prior_loss and not global_lost_now:
        if _UNKNOWN_PLACE in places or scope.endswith(_UNKNOWN_PLACE):
            return TechniqueLifecycleState.KNOWN
        return TechniqueLifecycleState.LOCALLY_EXTINCT
    if extant and _diffusing(series, ordered, as_of, window, entries):
        return TechniqueLifecycleState.DIFFUSING
    record_only = current_n == 0 and intact > 0
    if extant and (
        (current_n <= rare_max and peak > rare_max)
        or (record_only and ever_holder)
    ):
        return TechniqueLifecycleState.RARE
    location_peak = max((len(item[1]) for item in series), default=0)
    if (
        extant
        and not prior_loss
        and (
            (peak <= 1 and location_peak <= 1)
            or (record_only and not ever_holder)
        )
    ):
        return TechniqueLifecycleState.DISCOVERED
    if extant and current_n >= 1:
        return TechniqueLifecycleState.KNOWN
    if scope != "global":
        return TechniqueLifecycleState.LOCALLY_EXTINCT
    return TechniqueLifecycleState.GLOBALLY_LOST


def _diffusing(
    series: Sequence[tuple[int, frozenset[str], int, tuple[str, ...]]],
    ordered: Sequence[int],
    as_of: int,
    window: int,
    entries: Sequence[Mapping[str, object]],
) -> bool:
    start = max(0, as_of - window)
    start_index = 0
    for index, tick in enumerate(ordered):
        if tick <= start:
            start_index = index
    start_n = series[start_index][0]
    now_n = series[-1][0]
    start_locations = len(series[start_index][1])
    now_locations = len(series[-1][1])
    first_appearance = start_n == 0 and now_n == 1 and start_locations == 0
    if (now_n > start_n and not first_appearance) or (
        now_locations > start_locations and start_locations > 0
    ):
        return True
    return any(
        entry["origin"] in _TEACHING_ORIGINS
        and type(entry["acquired_tick"]) is int
        and start < int(entry["acquired_tick"]) <= as_of
        for entry in entries
    )


def _causes(
    *,
    state: TechniqueLifecycleState,
    entries: Sequence[Mapping[str, object]],
    deaths: Mapping[str, int],
    artifacts: Sequence[Mapping[str, object]],
    as_of: int,
    performable: bool | None,
    mentorship: Sequence[object],
    content_key: str,
    current_n: int,
    peak: int,
    scope: str,
) -> frozenset[TechniqueLossCause]:
    causes: set[TechniqueLossCause] = set()
    loss_state = state in {
        TechniqueLifecycleState.RARE,
        TechniqueLifecycleState.LOCALLY_EXTINCT,
        TechniqueLifecycleState.GLOBALLY_LOST,
    }
    holders_died = any(
        deaths.get(str(entry["owner_id"]), as_of + 1) <= as_of for entry in entries
    ) and current_n < peak
    cited = _cited_ids(entries)
    records_destroyed = any(
        str(row["artifact_id"]) in cited and not _record_intact(row, as_of)
        for row in artifacts
    )
    if loss_state and holders_died:
        causes.add(TechniqueLossCause.HOLDERS_DIED)
    if loss_state and records_destroyed:
        causes.add(TechniqueLossCause.RECORDS_DESTROYED)
    if performable is False:
        causes.add(TechniqueLossCause.MATERIALS_ABSENT)
    chain = _had_teaching_chain(entries, mentorship, content_key)
    living_continues = _teaching_intact(
        entries,
        mentorship,
        tuple(
            str(entry["owner_id"])
            for entry in entries
            if entry["active"]
            and type(entry["acquired_tick"]) is int
            and int(entry["acquired_tick"]) <= as_of
            and _alive(str(entry["owner_id"]), as_of, deaths)
        ),
        content_key,
    )
    lone_independent = (
        entries
        and all(entry["origin"] == "independent_discovery" for entry in entries)
        and not any(entry["origin"] in _TEACHING_ORIGINS for entry in entries)
        and not mentorship
    )
    if loss_state and chain and not living_continues and not lone_independent:
        causes.add(TechniqueLossCause.TEACHING_CHAIN_FAILED)
    _ = scope
    return frozenset(causes)


def _root_pair(
    entries: Sequence[Mapping[str, object]],
    roots: Sequence[Mapping[str, object]],
    state: TechniqueLifecycleState,
) -> tuple[str | None, str | None]:
    if state is not TechniqueLifecycleState.REDISCOVERED or not roots:
        return None, None
    new_root = str(roots[-1]["lineage_root_id"])
    prior = next(
        (
            str(entry["lineage_root_id"])
            for entry in entries
            if str(entry["lineage_root_id"]) != new_root
        ),
        None,
    )
    return prior, new_root


def technique_lineage_diffusion(
    audits: Sequence[object],
    *,
    content_key: str,
    as_of_tick: int,
    spec: TechniqueLifecycleSpec,
    death_ticks: Mapping[str, int] | None = None,
    artifact_rows: Sequence[object] = (),
    applied_actions: Sequence[AppliedActionRow] = (),
    mentorship_audits: Sequence[object] = (),
    catalog: object | None = None,
    node_rows: Sequence[object] = (),
    item_rows: Sequence[object] = (),
) -> TechniqueDiffusionRow:
    """Analysis-only diffusion row. Root ids are set only after rediscovery."""
    key = require_stable_id("content_key", content_key)
    snapshots = classify_technique_lifecycle(
        audits,
        as_of_tick=as_of_tick,
        spec=spec,
        death_ticks=death_ticks,
        artifact_rows=artifact_rows,
        applied_actions=applied_actions,
        mentorship_audits=mentorship_audits,
        catalog=catalog,
        node_rows=node_rows,
        item_rows=item_rows,
    )
    chosen = next(
        (row for row in snapshots if row.content_key == key and row.scope == "global"),
        None,
    )
    if chosen is None:
        raise ValueError("technique_lineage_diffusion_missing")
    prior = ""
    new = ""
    if chosen.state is TechniqueLifecycleState.REDISCOVERED:
        prior = chosen.prior_lineage_root_id or ""
        new = chosen.new_lineage_root_id or ""
    locations = next(
        (
            row.location_ids
            for row in ground_technique_lifecycle(
                audits,
                as_of_tick=as_of_tick,
                death_ticks=death_ticks,
                artifact_rows=artifact_rows,
                applied_actions=applied_actions,
                mentorship_audits=mentorship_audits,
            )
            if row.content_key == key
        ),
        (),
    )
    return TechniqueDiffusionRow(
        content_key=key,
        as_of_tick=as_of_tick,
        state=chosen.state,
        known_by_n=chosen.known_by_n,
        location_count=sum(place != _UNKNOWN_PLACE for place in locations),
        causes=chosen.causes,
        performable=chosen.performable,
        prior_lineage_root_id=prior,
        new_lineage_root_id=new,
    )
