class_name ObserverCivilization

## Strict read-only parsers for independent civilization sidecars. Every row is
## validated against its declared layer/evidence scope; nothing is inferred.

const Evidence := preload("res://scripts/presentation/evidence_class.gd")

const MAP_SCHEMA := "observer-civilization-map-v1"
const CATALOGUE_SCHEMA := "observer-civilization-catalogue-v1"
const OVERLAY_SCHEMA := "observer-civilization-overlay-v1"
const MARKERS_SCHEMA := "observer-civilization-markers-v1"

const SECTIONS := ["regions", "routes", "locations", "projects", "repositories", "records"]
const LAYERS := ["settlements", "migration", "trade", "culture", "technology", "social_groups", "institutions"]
const EVIDENCE_VALUES := ["OBJECTIVE", "SUBJECTIVE", "ANALYTICAL"]
const ANCHOR_KINDS := ["location", "structure", "repository", "project", "agent_at_evidence", "none"]
const SOURCE_KINDS := [
	"scene", "event", "inventory", "knowledge", "group", "concept", "office",
	"institution_episode", "project", "repository", "record", "journey", "lineage",
]
const OWNER_SOURCE_KINDS := ["inventory", "knowledge", "group", "concept", "office"]
const COVERAGE_STATES := ["complete", "partial", "unavailable", "disabled"]
const COVERAGE_REASONS := [
	"capture_off", "channel_absent", "boundary_not_captured",
	"finalized_boundary_required", "publication_pending", "capture_gap",
	"capture_failed", "capture_limit", "unresolved_anchor", "missing_denominator",
	"partial_owner_coverage", "insufficient_history", "event_gap",
	"grounding_unavailable", "source_conflict",
]
const AVAILABILITY_REASONS := [
	"capture_off", "channel_absent", "boundary_not_captured",
	"publication_pending", "capture_gap", "capture_limit",
	"partial_owner_coverage", "missing_denominator", "grounding_unavailable",
]
const MARKER_TYPES := {
	"settlement_activated": "settlements",
	"settlement_deactivated": "settlements",
	"journey_started": "migration",
	"journey_arrived": "migration",
	"journey_ended": "migration",
	"technology_acquired": "technology",
	"institution_transition": "institutions",
}
const ITEM_KINDS := ["food", "water", "material", "medical", "generic", "tool"]
const STRUCTURE_KINDS := ["shelter", "store", "bridge", "record_site", "well", "warning_post"]
const PROJECT_KINDS := ["shared_shelter", "bridge", "storage", "winter_reserve", "record_site", "well", "warning_post"]
const PROJECT_STATUSES := ["open", "completed", "abandoned"]
const REPOSITORY_STATUSES := ["intact", "neglected", "inaccessible", "destroyed"]
const ACCESS_MODES := ["open", "colocated_only", "founder_list"]
const ARTIFACT_KINDS := ["mark", "sign", "note", "map", "record", "memorial"]
const RECORD_GENRES := ["warning", "instruction", "map", "story", "agreement", "inventory_record", "genealogy", "chronicle"]
const RECORD_INTEGRITY := ["intact", "damaged", "partially_lost", "destroyed"]
const SETTLEMENT_STATUSES := ["active", "inactive", "censored", "insufficient_history"]
const MIGRATION_PHASES := ["preparing", "capacity_wait", "travelling", "arrived", "ended"]
const CULTURE_BASES := ["living_population", "location_presence", "region_presence"]
const TECHNOLOGY_STATUSES := ["held", "lost", "acquired"]
const ATTRIBUTIONS := ["attributable", "unknown", "ambiguous", "rediscovery"]
const MODALITIES := ["practice", "teaching", "record", "observation", "unknown"]
const GROUP_BASES := ["owner_belief", "interaction_residence"]
const INSTITUTION_KINDS := ["concept", "office", "episode"]
const INSTITUTION_STATUSES := [
	"emerging", "stable", "weakening", "collapsed", "censored",
	"recognized", "uncertain", "vacant", "contested", "lost",
]


class WindowModel:
	extends RefCounted
	var start_tick: int = 0
	var end_tick: int = 0


class CoverageModel:
	extends RefCounted
	var state: String = ""
	var reason: Variant = null
	var capture_start: Variant = null
	var capture_end: Variant = null
	var missing_intervals: Array = []
	var observed_count: Variant = null
	var expected_count: Variant = null


class SourceRefModel:
	extends RefCounted
	var source_kind: String = ""
	var source_id: String = ""
	var tick: int = 0
	var owner_id: Variant = null


class AnchorModel:
	extends RefCounted
	var kind: String = ""
	var location_id: Variant = null
	var entity_id: Variant = null
	var evidence_ref: Variant = null
	var evidence_tick: Variant = null


class RowContextModel:
	extends RefCounted
	var row_id: String = ""
	var source_refs: Array = []
	var anchors: Array = []
	var detail_truncated: bool = false


class ScopeModel:
	extends RefCounted
	var layer: Variant = null
	var evidence_class: String = ""
	var owner_id: Variant = null


class LayerContextModel:
	extends RefCounted
	var scope: ScopeModel = null
	var boundary_tick: int = 0
	var window: WindowModel = null
	var policy_version: String = ""
	var coverage: CoverageModel = null


class PublicationModel:
	extends RefCounted
	var publication_id: String = ""
	var digest: String = ""
	var policy_version: String = ""


class CursorModel:
	extends RefCounted
	var run_id: String = ""
	var world_id: String = ""
	var tick: int = 0
	var through_sequence: Variant = null
	var boundary_tick: Variant = null
	var revision: int = 0


class RequestedCursorModel:
	extends RefCounted
	var tick: Variant = null
	var through_sequence: Variant = null


class ContributionModel:
	extends RefCounted
	var actor_id: String = ""
	var tick: int = 0
	var labor_units: int = 0
	var material_count: int = 0
	var item_id: Variant = null


class PublicActsModel:
	extends RefCounted
	var benefit_count: int = 0
	var draw_count: int = 0
	var maintenance_count: int = 0
	var opposition_count: int = 0


class ItemCountModel:
	extends RefCounted
	var kind: String = ""
	var count: int = 0


class RowModel:
	extends RefCounted
	var kind: String = ""
	var context: RowContextModel = null
	var history: Variant = null
	var region_id: Variant = null
	var location_count: int = 0
	var location_ids: Array = []
	var region_label: Variant = null
	var route_id: Variant = null
	var endpoint_a: Variant = null
	var endpoint_b: Variant = null
	var region_a: Variant = null
	var region_b: Variant = null
	var duration_ticks: int = 0
	var fatigue_cost: float = 0.0
	var location_id: Variant = null
	var living_body_count: int = 0
	var dead_body_count: int = 0
	var registered_agent_count: int = 0
	var lifecycle_living_count: Variant = null
	var lifecycle_dead_count: Variant = null
	var structure_count: int = 0
	var repository_count: int = 0
	var project_count: int = 0
	var active_journey_count: int = 0
	var active_journey_ids: Array = []
	var project_id: Variant = null
	var status: Variant = null
	var labor_progress: int = 0
	var labor_required: int = 0
	var material_progress: int = 0
	var material_required: int = 0
	var material_kind: Variant = null
	var accepted_contribution_count: int = 0
	var accepted_contributions: Array = []
	var linked_structure_id: Variant = null
	var linked_structure_kind: Variant = null
	var shortage_count: int = 0
	var public_acts: Variant = null
	var repository_id: Variant = null
	var access_mode: Variant = null
	var member_count: int = 0
	var member_ids: Array = []
	var established_tick: int = 0
	var last_maintained_tick: int = 0
	var neglect_streak: int = 0
	var record_id: Variant = null
	var genre: Variant = null
	var integrity: Variant = null
	var holder_id: Variant = null
	var custodian_repository_id: Variant = null
	var parent_record_id: Variant = null
	var source_record_id: Variant = null
	var created_tick: int = 0
	var copy_generation: int = 0
	var annotation_revisions: int = 0
	var lost_mark_count: int = 0
	var candidate_id: Variant = null
	var eligible_occupancy: int = 0
	var infrastructure_count: int = 0
	var first_supported_boundary: Variant = null
	var last_supported_boundary: Variant = null
	var observed_streak: int = 0
	var episode_start_boundary: Variant = null
	var journey_id: Variant = null
	var origin_location_id: Variant = null
	var destination_location_id: Variant = null
	var participant_count: int = 0
	var participant_ids: Array = []
	var phase: Variant = null
	var started_tick: Variant = null
	var arrived_tick: Variant = null
	var ended_tick: Variant = null
	var start_count: int = 0
	var arrival_count: int = 0
	var capacity_wait_count: int = 0
	var ended_count: int = 0
	var completed_exchange_count: int = 0
	var forward_items: Array = []
	var reverse_items: Array = []
	var occurrence_location_id: Variant = null
	var trait_id: Variant = null
	var representation_id: Variant = null
	var basis: Variant = null
	var carrier_count: int = 0
	var carrier_ids: Array = []
	var eligible_owner_count: Variant = null
	var unavailable_owner_count: int = 0
	var proportion: Variant = null
	var knowledge_id: Variant = null
	var acquisition_boundary: Variant = null
	var attribution: Variant = null
	var modality: Variant = null
	var source_owner_id: Variant = null
	var source_knowledge_id: Variant = null
	var living_holder_count: Variant = null
	var group_id: Variant = null
	var missing_lanes: Array = []
	var institution_id: Variant = null
	var native_owner_id: Variant = null
	var native_id: Variant = null
	var evidence_start_tick: Variant = null
	var evidence_end_tick: Variant = null


class MarkerModel:
	extends RefCounted
	var marker_id: String = ""
	var marker_type: String = ""
	var seek_boundary: int = 0
	var evidence_class: String = ""
	var owner_id: Variant = null
	var layer: String = ""
	var row_id: String = ""
	var source_refs: Array = []
	var coverage: CoverageModel = null


class MapModel:
	extends RefCounted
	var schema_version: String = ""
	var run_id: String = ""
	var world_id: String = ""
	var requested_cursor: RequestedCursorModel = null
	var resolved_cursor: CursorModel = null
	var section: String = ""
	var scope: ScopeModel = null
	var coverage: CoverageModel = null
	var rows: Array = []
	var next_cursor: Variant = null
	var truncated: bool = false
	var source_revision: int = 0


class CatalogueBoundaryModel:
	extends RefCounted
	var boundary_tick: int = 0
	var revision: int = 0
	var coverage: CoverageModel = null
	var layers: Array = []


class CatalogueModel:
	extends RefCounted
	var schema_version: String = ""
	var run_id: String = ""
	var world_id: String = ""
	var scope: Variant = null
	var publication: Variant = null
	var availability: String = ""
	var reason: Variant = null
	var coverage: CoverageModel = null
	var boundaries: Array = []
	var next_cursor: Variant = null
	var truncated: bool = false


class OverlayModel:
	extends RefCounted
	var schema_version: String = ""
	var run_id: String = ""
	var world_id: String = ""
	var scope: ScopeModel = null
	var requested_tick: int = 0
	var requested_publication_id: Variant = null
	var publication: Variant = null
	var availability: String = ""
	var reason: Variant = null
	var resolved_cursor: Variant = null
	var window: Variant = null
	var coverage: CoverageModel = null
	var rows: Array = []
	var next_cursor: Variant = null
	var truncated: bool = false
	var source_revision: Variant = null


class MarkersModel:
	extends RefCounted
	var schema_version: String = ""
	var run_id: String = ""
	var world_id: String = ""
	var scope: Variant = null
	var requested_window: WindowModel = null
	var publication: Variant = null
	var availability: String = ""
	var reason: Variant = null
	var markers: Array = []
	var missing_intervals: Array = []
	var coverage: CoverageModel = null
	var next_cursor: Variant = null
	var truncated: bool = false


static func parse_map(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY or payload.get("schema_version") != MAP_SCHEMA:
		return _failure(payload, MAP_SCHEMA)
	if not _is_string(payload.get("run_id")) or not _is_string(payload.get("world_id")):
		return _failure({}, MAP_SCHEMA)
	var requested: Variant = _requested_cursor(payload.get("requested_cursor"))
	var resolved: Variant = _cursor(payload.get("resolved_cursor"))
	var section := str(payload.get("section", ""))
	if requested == null or resolved == null or section not in SECTIONS:
		return _failure({}, MAP_SCHEMA)
	var scope: Variant = _scope(payload.get("scope"))
	if scope == null or scope.layer != section or scope.evidence_class != Evidence.OBJECTIVE or scope.owner_id != null:
		return _failure({}, MAP_SCHEMA)
	var coverage: Variant = _coverage(payload.get("coverage"))
	if coverage == null or not _page_fields(payload) or resolved.run_id != payload["run_id"] or resolved.world_id != payload["world_id"]:
		return _failure({}, MAP_SCHEMA)
	if not _nonneg_int(payload.get("source_revision")) or int(payload["source_revision"]) != resolved.revision:
		return _failure({}, MAP_SCHEMA)
	var limit_tick: int = int(resolved.boundary_tick) if resolved.boundary_tick != null else resolved.tick
	var rows: Array = []
	for raw in _array(payload.get("rows")):
		var row: Variant = _row(raw, section, scope, limit_tick, null)
		if row == null:
			return _failure({}, MAP_SCHEMA)
		if row.history != null:
			return _failure({}, MAP_SCHEMA)
		rows.append(row)
	if not _sorted_unique(rows, "row_id"):
		return _failure({}, MAP_SCHEMA)
	if rows.size() > 200:
		return _failure({}, MAP_SCHEMA)
	var model := MapModel.new()
	model.schema_version = MAP_SCHEMA
	model.run_id = payload["run_id"]
	model.world_id = payload["world_id"]
	model.requested_cursor = requested
	model.resolved_cursor = resolved
	model.section = section
	model.scope = scope
	model.coverage = coverage
	model.rows = rows
	model.next_cursor = payload.get("next_cursor")
	model.truncated = bool(payload.get("truncated", false))
	model.source_revision = int(payload["source_revision"])
	return {"ok": true, "value": model}


static func parse_catalogue(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY or payload.get("schema_version") != CATALOGUE_SCHEMA:
		return _failure(payload, CATALOGUE_SCHEMA)
	if not _is_string(payload.get("run_id")) or not _is_string(payload.get("world_id")):
		return _failure({}, CATALOGUE_SCHEMA)
	var scope: Variant = _catalogue_scope(payload.get("scope"))
	var publication: Variant = _optional_publication(payload.get("publication"))
	var coverage: Variant = _coverage(payload.get("coverage"))
	if scope == null or coverage == null or not _availability_fields(payload, publication):
		return _failure({}, CATALOGUE_SCHEMA)
	var boundaries: Array = []
	var previous := -1
	for raw in _array(payload.get("boundaries")):
		var boundary: Variant = _catalogue_boundary(raw)
		if boundary == null or boundary.boundary_tick <= previous:
			return _failure({}, CATALOGUE_SCHEMA)
		previous = boundary.boundary_tick
		boundaries.append(boundary)
	if boundaries.size() > 200:
		return _failure({}, CATALOGUE_SCHEMA)
	if str(payload.get("availability", "")) == "available":
		if publication == null or payload.get("reason", null) != null or boundaries.is_empty() and bool(payload.get("truncated", false)):
			return _failure({}, CATALOGUE_SCHEMA)
	var model := CatalogueModel.new()
	model.schema_version = CATALOGUE_SCHEMA
	model.run_id = payload["run_id"]
	model.world_id = payload["world_id"]
	model.scope = scope
	model.publication = publication
	model.availability = str(payload["availability"])
	model.reason = payload.get("reason")
	model.coverage = coverage
	model.boundaries = boundaries
	model.next_cursor = payload.get("next_cursor")
	model.truncated = bool(payload.get("truncated", false))
	return {"ok": true, "value": model}


static func parse_overlay(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY or payload.get("schema_version") != OVERLAY_SCHEMA:
		return _failure(payload, OVERLAY_SCHEMA)
	if not _is_string(payload.get("run_id")) or not _is_string(payload.get("world_id")):
		return _failure({}, OVERLAY_SCHEMA)
	var scope: Variant = _scope(payload.get("scope"))
	var publication: Variant = _optional_publication(payload.get("publication"))
	var coverage: Variant = _coverage(payload.get("coverage"))
	if scope == null or coverage == null or scope.layer == null or scope.layer not in LAYERS:
		return _failure({}, OVERLAY_SCHEMA)
	if not _nonneg_int(payload.get("requested_tick")):
		return _failure({}, OVERLAY_SCHEMA)
	if not _optional_string(payload.get("requested_publication_id")):
		return _failure({}, OVERLAY_SCHEMA)
	if not _availability_fields(payload, publication):
		return _failure({}, OVERLAY_SCHEMA)
	var resolved: Variant = null
	var window: Variant = null
	var source_revision: Variant = payload.get("source_revision")
	if str(payload.get("availability", "")) == "available":
		resolved = _cursor(payload.get("resolved_cursor"))
		window = _window(payload.get("window"))
		if resolved == null or window == null or not _optional_nonneg_int(source_revision):
			return _failure({}, OVERLAY_SCHEMA)
		if int(source_revision) != resolved.revision:
			return _failure({}, OVERLAY_SCHEMA)
		if resolved.boundary_tick == null or int(resolved.boundary_tick) != int(payload["requested_tick"]):
			return _failure({}, OVERLAY_SCHEMA)
		if resolved.run_id != payload["run_id"] or resolved.world_id != payload["world_id"]:
			return _failure({}, OVERLAY_SCHEMA)
		if window.end_tick > int(resolved.boundary_tick):
			return _failure({}, OVERLAY_SCHEMA)
	var rows: Array = []
	if str(payload.get("availability", "")) == "available":
		for raw in _array(payload.get("rows")):
			var row: Variant = _row(raw, scope.layer, scope, int(resolved.boundary_tick), window)
			if row == null or row.history == null or row.history.boundary_tick != int(resolved.boundary_tick):
				return _failure({}, OVERLAY_SCHEMA)
			if row.history.window.start_tick != window.start_tick or row.history.window.end_tick != window.end_tick:
				return _failure({}, OVERLAY_SCHEMA)
			rows.append(row)
		if not _sorted_unique(rows, "row_id") or rows.size() > 200:
			return _failure({}, OVERLAY_SCHEMA)
	elif not _array(payload.get("rows")).is_empty():
		return _failure({}, OVERLAY_SCHEMA)
	var model := OverlayModel.new()
	model.schema_version = OVERLAY_SCHEMA
	model.run_id = payload["run_id"]
	model.world_id = payload["world_id"]
	model.scope = scope
	model.requested_tick = int(payload["requested_tick"])
	model.requested_publication_id = payload.get("requested_publication_id")
	model.publication = publication
	model.availability = str(payload["availability"])
	model.reason = payload.get("reason")
	model.resolved_cursor = resolved
	model.window = window
	model.coverage = coverage
	model.rows = rows
	model.next_cursor = payload.get("next_cursor")
	model.truncated = bool(payload.get("truncated", false))
	model.source_revision = source_revision
	return {"ok": true, "value": model}


static func parse_markers(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY or payload.get("schema_version") != MARKERS_SCHEMA:
		return _failure(payload, MARKERS_SCHEMA)
	if not _is_string(payload.get("run_id")) or not _is_string(payload.get("world_id")):
		return _failure({}, MARKERS_SCHEMA)
	var scope: Variant = _catalogue_scope(payload.get("scope"))
	var publication: Variant = _optional_publication(payload.get("publication"))
	var window: Variant = _window(payload.get("requested_window"))
	var coverage: Variant = _coverage(payload.get("coverage"))
	if scope == null or window == null or coverage == null or not _availability_fields(payload, publication):
		return _failure({}, MARKERS_SCHEMA)
	var missing: Array = []
	var previous_end := -1
	for raw in _array(payload.get("missing_intervals")):
		var band: Variant = _window(raw)
		if band == null or band.start_tick < previous_end:
			return _failure({}, MARKERS_SCHEMA)
		if band.start_tick < window.start_tick or band.end_tick > window.end_tick:
			return _failure({}, MARKERS_SCHEMA)
		previous_end = band.end_tick
		missing.append(band)
	if missing.size() > 200:
		return _failure({}, MARKERS_SCHEMA)
	var markers: Array = []
	var previous_key := ""
	for raw in _array(payload.get("markers")):
		var marker: Variant = _marker(raw, scope, window)
		if marker == null:
			return _failure({}, MARKERS_SCHEMA)
		var key := "%012d|%s" % [marker.seek_boundary, marker.marker_id]
		if key <= previous_key:
			return _failure({}, MARKERS_SCHEMA)
		previous_key = key
		markers.append(marker)
	if markers.size() > 200:
		return _failure({}, MARKERS_SCHEMA)
	if str(payload.get("availability", "")) == "available":
		if publication == null or payload.get("reason", null) != null:
			return _failure({}, MARKERS_SCHEMA)
	elif not markers.is_empty():
		return _failure({}, MARKERS_SCHEMA)
	var model := MarkersModel.new()
	model.schema_version = MARKERS_SCHEMA
	model.run_id = payload["run_id"]
	model.world_id = payload["world_id"]
	model.scope = scope
	model.requested_window = window
	model.publication = publication
	model.availability = str(payload["availability"])
	model.reason = payload.get("reason")
	model.markers = markers
	model.missing_intervals = missing
	model.coverage = coverage
	model.next_cursor = payload.get("next_cursor")
	model.truncated = bool(payload.get("truncated", false))
	return {"ok": true, "value": model}


static func _row(raw: Variant, kind: String, scope: ScopeModel, boundary_tick: int, window: Variant) -> Variant:
	if typeof(raw) != TYPE_DICTIONARY:
		return null
	var context: Variant = _row_context(raw.get("context"))
	if context == null:
		return null
	var history: Variant = null
	if window != null:
		history = _layer_context(raw.get("history"), scope, boundary_tick)
		if history == null:
			return null
	for ref in context.source_refs:
		if ref.tick > boundary_tick or (ref.source_kind == "event" and ref.tick >= boundary_tick):
			return null
		if scope.owner_id != null and ref.owner_id != null and ref.owner_id != scope.owner_id:
			return null
	for anchor in context.anchors:
		if anchor.evidence_tick != null and int(anchor.evidence_tick) > boundary_tick:
			return null
	var model := RowModel.new()
	model.kind = kind
	model.context = context
	model.history = history
	match kind:
		"regions":
			if not _set_region(model, raw):
				return null
		"routes":
			if not _set_route(model, raw):
				return null
		"locations":
			if not _set_location(model, raw):
				return null
		"projects":
			if not _set_project(model, raw):
				return null
		"repositories":
			if not _set_repository(model, raw):
				return null
		"records":
			if not _set_record(model, raw):
				return null
		"settlements":
			if not _set_settlement(model, raw):
				return null
		"migration":
			if not _set_migration(model, raw):
				return null
		"trade":
			if not _set_trade(model, raw):
				return null
		"culture":
			if not _set_culture(model, raw):
				return null
		"technology":
			if not _set_technology(model, raw, scope):
				return null
		"social_groups":
			if not _set_group(model, raw, scope):
				return null
		"institutions":
			if not _set_institution(model, raw, scope):
				return null
		_:
			return null
	return model


static func _set_region(row: RowModel, raw: Dictionary) -> bool:
	if not _is_string(raw.get("region_id")) or not _nonneg_int(raw.get("location_count")):
		return false
	var ids: Variant = _string_array(raw.get("location_ids"))
	if ids == null or ids.size() > int(raw["location_count"]):
		return false
	if ids.size() < int(raw["location_count"]) and not row.context.detail_truncated:
		return false
	if not _optional_string(raw.get("region_label")):
		return false
	row.region_id = raw["region_id"]
	row.location_count = int(raw["location_count"])
	row.location_ids = ids
	row.region_label = raw.get("region_label")
	return true


static func _set_route(row: RowModel, raw: Dictionary) -> bool:
	if not _is_string(raw.get("route_id")) or not _is_string(raw.get("endpoint_a")) or not _is_string(raw.get("endpoint_b")):
		return false
	if str(raw["endpoint_a"]) >= str(raw["endpoint_b"]):
		return false
	if not _optional_string(raw.get("region_a")) or not _optional_string(raw.get("region_b")):
		return false
	if not _nonneg_int(raw.get("duration_ticks")) or int(raw["duration_ticks"]) < 1:
		return false
	if not _finite(raw.get("fatigue_cost")) or float(raw["fatigue_cost"]) < 0.0:
		return false
	row.route_id = raw["route_id"]
	row.endpoint_a = raw["endpoint_a"]
	row.endpoint_b = raw["endpoint_b"]
	row.region_a = raw.get("region_a")
	row.region_b = raw.get("region_b")
	row.duration_ticks = int(raw["duration_ticks"])
	row.fatigue_cost = float(raw["fatigue_cost"])
	return true


static func _set_location(row: RowModel, raw: Dictionary) -> bool:
	if not _is_string(raw.get("location_id")) or not _optional_string(raw.get("region_id")):
		return false
	for key in ["living_body_count", "dead_body_count", "registered_agent_count", "structure_count", "repository_count", "project_count", "active_journey_count"]:
		if not _nonneg_int(raw.get(key)):
			return false
	for key in ["lifecycle_living_count", "lifecycle_dead_count"]:
		if not _optional_nonneg_int(raw.get(key)):
			return false
	var journeys: Variant = _string_array(raw.get("active_journey_ids"))
	if journeys == null or journeys.size() > int(raw["active_journey_count"]):
		return false
	if journeys.size() < int(raw["active_journey_count"]) and not row.context.detail_truncated:
		return false
	row.location_id = raw["location_id"]
	row.region_id = raw.get("region_id")
	for key in ["living_body_count", "dead_body_count", "registered_agent_count", "structure_count", "repository_count", "project_count", "active_journey_count"]:
		row.set(key, int(raw[key]))
	row.lifecycle_living_count = raw.get("lifecycle_living_count")
	row.lifecycle_dead_count = raw.get("lifecycle_dead_count")
	row.active_journey_ids = journeys
	return true


static func _set_project(row: RowModel, raw: Dictionary) -> bool:
	if not _is_string(raw.get("project_id")) or not _is_string(raw.get("location_id")):
		return false
	if str(raw.get("kind", "")) not in PROJECT_KINDS or str(raw.get("status", "")) not in PROJECT_STATUSES:
		return false
	if not _nonneg_int(raw.get("labor_progress")) or not _nonneg_int(raw.get("labor_required")):
		return false
	if not _nonneg_int(raw.get("material_progress")) or not _nonneg_int(raw.get("material_required")):
		return false
	if int(raw["labor_progress"]) > int(raw["labor_required"]) or int(raw["material_progress"]) > int(raw["material_required"]):
		return false
	if str(raw.get("material_kind", "")) not in ITEM_KINDS:
		return false
	if not _nonneg_int(raw.get("accepted_contribution_count")) or not _nonneg_int(raw.get("shortage_count")):
		return false
	var contributions: Array = []
	for item in _array(raw.get("accepted_contributions")):
		var contribution: Variant = _contribution(item)
		if contribution == null:
			return false
		contributions.append(contribution)
	if contributions.size() > int(raw["accepted_contribution_count"]):
		return false
	if contributions.size() < int(raw["accepted_contribution_count"]) and not row.context.detail_truncated:
		return false
	if not _optional_string(raw.get("linked_structure_id")) or not _optional_string(raw.get("linked_structure_kind")):
		return false
	if raw.get("linked_structure_kind") != null and str(raw["linked_structure_kind"]) not in STRUCTURE_KINDS:
		return false
	var acts: Variant = _public_acts(raw.get("public_acts"))
	if acts == null:
		return false
	row.project_id = raw["project_id"]
	row.location_id = raw["location_id"]
	row.basis = raw["kind"]
	row.status = raw["status"]
	row.labor_progress = int(raw["labor_progress"])
	row.labor_required = int(raw["labor_required"])
	row.material_progress = int(raw["material_progress"])
	row.material_required = int(raw["material_required"])
	row.material_kind = raw["material_kind"]
	row.accepted_contribution_count = int(raw["accepted_contribution_count"])
	row.accepted_contributions = contributions
	row.linked_structure_id = raw.get("linked_structure_id")
	row.linked_structure_kind = raw.get("linked_structure_kind")
	row.shortage_count = int(raw["shortage_count"])
	row.public_acts = acts
	return true


static func _set_repository(row: RowModel, raw: Dictionary) -> bool:
	for key in ["repository_id", "location_id"]:
		if not _is_string(raw.get(key)):
			return false
	if str(raw.get("status", "")) not in REPOSITORY_STATUSES or str(raw.get("access_mode", "")) not in ACCESS_MODES:
		return false
	if not _nonneg_int(raw.get("member_count")):
		return false
	var members: Variant = _string_array(raw.get("member_ids"))
	if members == null or members.size() > int(raw["member_count"]):
		return false
	if members.size() < int(raw["member_count"]) and not row.context.detail_truncated:
		return false
	if not _optional_string(raw.get("linked_structure_id")):
		return false
	for key in ["established_tick", "last_maintained_tick", "neglect_streak"]:
		if not _nonneg_int(raw.get(key)):
			return false
	row.repository_id = raw["repository_id"]
	row.location_id = raw["location_id"]
	row.status = raw["status"]
	row.access_mode = raw["access_mode"]
	row.member_count = int(raw["member_count"])
	row.member_ids = members
	row.linked_structure_id = raw.get("linked_structure_id")
	row.established_tick = int(raw["established_tick"])
	row.last_maintained_tick = int(raw["last_maintained_tick"])
	row.neglect_streak = int(raw["neglect_streak"])
	return true


static func _set_record(row: RowModel, raw: Dictionary) -> bool:
	if not _is_string(raw.get("record_id")) or str(raw.get("kind", "")) not in ARTIFACT_KINDS:
		return false
	if not _optional_string(raw.get("genre")) or not _optional_string(raw.get("integrity")):
		return false
	if raw.get("genre") != null and str(raw["genre"]) not in RECORD_GENRES:
		return false
	if raw.get("integrity") != null and str(raw["integrity"]) not in RECORD_INTEGRITY:
		return false
	for key in ["location_id", "holder_id", "custodian_repository_id", "parent_record_id", "source_record_id"]:
		if not _optional_string(raw.get(key)):
			return false
	for key in ["created_tick", "copy_generation", "annotation_revisions", "lost_mark_count"]:
		if not _nonneg_int(raw.get(key)):
			return false
	row.record_id = raw["record_id"]
	row.representation_id = raw["kind"]
	for key in ["genre", "integrity", "location_id", "holder_id", "custodian_repository_id", "parent_record_id", "source_record_id"]:
		row.set(key, raw.get(key))
	row.created_tick = int(raw["created_tick"])
	row.copy_generation = int(raw["copy_generation"])
	row.annotation_revisions = int(raw["annotation_revisions"])
	row.lost_mark_count = int(raw["lost_mark_count"])
	return true


static func _set_settlement(row: RowModel, raw: Dictionary) -> bool:
	for key in ["candidate_id", "location_id"]:
		if not _is_string(raw.get(key)):
			return false
	if str(raw.get("status", "")) not in SETTLEMENT_STATUSES:
		return false
	for key in ["eligible_occupancy", "infrastructure_count", "observed_streak"]:
		if not _nonneg_int(raw.get(key)):
			return false
	for key in ["first_supported_boundary", "last_supported_boundary", "episode_start_boundary"]:
		if not _optional_nonneg_int(raw.get(key)):
			return false
	if raw.get("first_supported_boundary") != null and raw.get("last_supported_boundary") != null and int(raw["first_supported_boundary"]) > int(raw["last_supported_boundary"]):
		return false
	row.candidate_id = raw["candidate_id"]
	row.location_id = raw["location_id"]
	row.status = raw["status"]
	row.eligible_occupancy = int(raw["eligible_occupancy"])
	row.infrastructure_count = int(raw["infrastructure_count"])
	row.observed_streak = int(raw["observed_streak"])
	row.first_supported_boundary = raw.get("first_supported_boundary")
	row.last_supported_boundary = raw.get("last_supported_boundary")
	row.episode_start_boundary = raw.get("episode_start_boundary")
	return true


static func _set_migration(row: RowModel, raw: Dictionary) -> bool:
	for key in ["journey_id", "route_id", "origin_location_id", "destination_location_id"]:
		if not _is_string(raw.get(key)):
			return false
	if str(raw.get("phase", "")) not in MIGRATION_PHASES:
		return false
	if not _nonneg_int(raw.get("participant_count")):
		return false
	var participants: Variant = _string_array(raw.get("participant_ids"))
	if participants == null or participants.size() > int(raw["participant_count"]):
		return false
	if participants.size() < int(raw["participant_count"]) and not row.context.detail_truncated:
		return false
	for key in ["started_tick", "arrived_tick", "ended_tick"]:
		if not _optional_nonneg_int(raw.get(key)):
			return false
	for key in ["start_count", "arrival_count", "capacity_wait_count", "ended_count"]:
		if not _nonneg_int(raw.get(key)):
			return false
	row.journey_id = raw["journey_id"]
	row.route_id = raw["route_id"]
	row.origin_location_id = raw["origin_location_id"]
	row.destination_location_id = raw["destination_location_id"]
	row.participant_count = int(raw["participant_count"])
	row.participant_ids = participants
	row.phase = raw["phase"]
	for key in ["started_tick", "arrived_tick", "ended_tick"]:
		row.set(key, raw.get(key))
	for key in ["start_count", "arrival_count", "capacity_wait_count", "ended_count"]:
		row.set(key, int(raw[key]))
	return true


static func _set_trade(row: RowModel, raw: Dictionary) -> bool:
	if not _nonneg_int(raw.get("completed_exchange_count")):
		return false
	if not _optional_string(raw.get("occurrence_location_id")):
		return false
	var participants: Variant = _string_array(raw.get("participant_ids"))
	if participants == null or participants.size() < 2 or participants.size() > 64:
		return false
	var forward: Array = _item_counts(raw.get("forward_items"))
	var reverse: Array = _item_counts(raw.get("reverse_items"))
	if forward == null or reverse == null:
		return false
	row.participant_count = participants.size()
	row.participant_ids = participants
	row.completed_exchange_count = int(raw["completed_exchange_count"])
	row.forward_items = forward
	row.reverse_items = reverse
	row.occurrence_location_id = raw.get("occurrence_location_id")
	return true


static func _set_culture(row: RowModel, raw: Dictionary) -> bool:
	for key in ["trait_id", "representation_id"]:
		if not _is_string(raw.get(key)):
			return false
	if str(raw.get("basis", "")) not in CULTURE_BASES:
		return false
	if not _nonneg_int(raw.get("carrier_count")) or not _nonneg_int(raw.get("unavailable_owner_count")):
		return false
	var carriers: Variant = _string_array(raw.get("carrier_ids"))
	if carriers == null or carriers.size() > int(raw["carrier_count"]):
		return false
	if carriers.size() < int(raw["carrier_count"]) and not row.context.detail_truncated:
		return false
	if not _optional_nonneg_int(raw.get("eligible_owner_count")):
		return false
	if not _optional_finite(raw.get("proportion")):
		return false
	var denominator: Variant = raw.get("eligible_owner_count")
	var unavailable := int(raw["unavailable_owner_count"])
	if denominator != null and int(raw["carrier_count"]) > int(denominator):
		return false
	if raw.get("proportion") != null:
		if denominator == null or int(denominator) == 0 or unavailable != 0:
			return false
		if row.history == null or row.history.coverage.state != "complete":
			return false
		if not is_equal_approx(float(raw["proportion"]), float(int(raw["carrier_count"])) / float(int(denominator))):
			return false
	elif denominator != null and int(denominator) > 0 and unavailable == 0 and row.history != null and row.history.coverage.state == "complete":
		return false
	row.trait_id = raw["trait_id"]
	row.representation_id = raw["representation_id"]
	row.basis = raw["basis"]
	row.carrier_count = int(raw["carrier_count"])
	row.carrier_ids = carriers
	row.eligible_owner_count = denominator
	row.unavailable_owner_count = unavailable
	row.proportion = raw.get("proportion")
	return true


static func _set_technology(row: RowModel, raw: Dictionary, scope: ScopeModel) -> bool:
	for key in ["knowledge_id", "holder_id"]:
		if not _is_string(raw.get(key)):
			return false
	if scope.owner_id != null and scope.owner_id != raw["holder_id"]:
		return false
	if str(raw.get("status", "")) not in TECHNOLOGY_STATUSES or str(raw.get("attribution", "")) not in ATTRIBUTIONS or str(raw.get("modality", "")) not in MODALITIES:
		return false
	if not _optional_nonneg_int(raw.get("acquisition_boundary")):
		return false
	if not _optional_string(raw.get("source_owner_id")) or not _optional_string(raw.get("source_knowledge_id")):
		return false
	if str(raw["attribution"]) == "attributable":
		if raw.get("source_owner_id") == null or raw.get("source_knowledge_id") == null:
			return false
	elif raw.get("source_owner_id") != null or raw.get("source_knowledge_id") != null:
		return false
	for key in ["living_holder_count", "eligible_owner_count"]:
		if not _optional_nonneg_int(raw.get(key)):
			return false
	row.knowledge_id = raw["knowledge_id"]
	row.holder_id = raw["holder_id"]
	row.status = raw["status"]
	row.acquisition_boundary = raw.get("acquisition_boundary")
	row.attribution = raw["attribution"]
	row.modality = raw["modality"]
	row.source_owner_id = raw.get("source_owner_id")
	row.source_knowledge_id = raw.get("source_knowledge_id")
	row.living_holder_count = raw.get("living_holder_count")
	row.eligible_owner_count = raw.get("eligible_owner_count")
	if row.acquisition_boundary != null and row.history != null and int(row.acquisition_boundary) > row.history.boundary_tick:
		return false
	return true


static func _set_group(row: RowModel, raw: Dictionary, scope: ScopeModel) -> bool:
	if not _is_string(raw.get("group_id")) or str(raw.get("basis", "")) not in GROUP_BASES:
		return false
	var subjective := scope.evidence_class == Evidence.SUBJECTIVE
	if subjective != (str(raw["basis"]) == "owner_belief"):
		return false
	if not _nonneg_int(raw.get("member_count")):
		return false
	var members: Variant = _string_array(raw.get("member_ids"))
	if members == null or members.size() > int(raw["member_count"]):
		return false
	if members.size() < int(raw["member_count"]) and not row.context.detail_truncated:
		return false
	var lanes: Variant = _string_array(raw.get("missing_lanes"))
	if lanes == null:
		return false
	for lane in lanes:
		if lane not in ["interaction", "residence", "trust"]:
			return false
	row.group_id = raw["group_id"]
	row.basis = raw["basis"]
	row.member_count = int(raw["member_count"])
	row.member_ids = members
	row.missing_lanes = lanes
	return true


static func _set_institution(row: RowModel, raw: Dictionary, scope: ScopeModel) -> bool:
	if not _is_string(raw.get("institution_id")) or not _is_string(raw.get("native_id")):
		return false
	if str(raw.get("kind", "")) not in INSTITUTION_KINDS or str(raw.get("status", "")) not in INSTITUTION_STATUSES:
		return false
	if not _optional_string(raw.get("native_owner_id")):
		return false
	if str(raw["kind"]) in ["concept", "office"] and raw.get("native_owner_id") == null:
		return false
	if str(raw["kind"]) == "episode" and scope.owner_id != null:
		return false
	if scope.owner_id != null and scope.owner_id != raw.get("native_owner_id"):
		return false
	for key in ["first_supported_boundary", "last_supported_boundary", "evidence_start_tick", "evidence_end_tick"]:
		if not _optional_nonneg_int(raw.get(key)):
			return false
	if raw.get("first_supported_boundary") != null and raw.get("last_supported_boundary") != null and int(raw["first_supported_boundary"]) > int(raw["last_supported_boundary"]):
		return false
	row.institution_id = raw["institution_id"]
	row.native_owner_id = raw.get("native_owner_id")
	row.native_id = raw["native_id"]
	row.basis = raw["kind"]
	row.status = raw["status"]
	for key in ["first_supported_boundary", "last_supported_boundary", "evidence_start_tick", "evidence_end_tick"]:
		row.set(key, raw.get(key))
	return true


static func _marker(raw: Variant, scope: Variant, window: WindowModel) -> Variant:
	if typeof(raw) != TYPE_DICTIONARY:
		return null
	for key in ["marker_id", "row_id"]:
		if not _is_string(raw.get(key)):
			return null
	var marker_type := str(raw.get("marker_type", ""))
	if not MARKER_TYPES.has(marker_type):
		return null
	if not _nonneg_int(raw.get("seek_boundary")):
		return null
	var seek := int(raw["seek_boundary"])
	if seek < window.start_tick or seek >= window.end_tick:
		return null
	if str(raw.get("layer", "")) != str(MARKER_TYPES[marker_type]):
		return null
	var evidence := str(raw.get("evidence_class", ""))
	if evidence not in EVIDENCE_VALUES:
		return null
	if not _optional_string(raw.get("owner_id")):
		return null
	if (evidence == "SUBJECTIVE") != (raw.get("owner_id") != null):
		return null
	var display := _evidence_value(evidence)
	if display.is_empty():
		return null
	if scope != null:
		if display != scope.evidence_class or raw.get("owner_id") != scope.owner_id:
			return null
		if scope.layer != null and str(raw["layer"]) != str(scope.layer):
			return null
	var refs: Array = []
	for item in _array(raw.get("source_refs")):
		var ref: Variant = _source_ref(item)
		if ref == null or ref.tick >= seek:
			return null
		if raw.get("owner_id") != null and ref.owner_id != null and ref.owner_id != raw["owner_id"]:
			return null
		refs.append(ref)
	if refs.is_empty() or refs.size() > 32 or not _unique_objects(refs):
		return null
	var coverage: Variant = _coverage(raw.get("coverage"))
	if coverage == null or coverage.state != "complete":
		return null
	var model := MarkerModel.new()
	model.marker_id = raw["marker_id"]
	model.marker_type = marker_type
	model.seek_boundary = seek
	model.evidence_class = display
	model.owner_id = raw.get("owner_id")
	model.layer = raw["layer"]
	model.row_id = raw["row_id"]
	model.source_refs = refs
	model.coverage = coverage
	return model


static func _row_context(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY or not _is_string(value.get("row_id")):
		return null
	var refs: Array = []
	for item in _array(value.get("source_refs")):
		var ref: Variant = _source_ref(item)
		if ref == null:
			return null
		refs.append(ref)
	if refs.is_empty() or refs.size() > 32 or not _unique_objects(refs):
		return null
	var anchors: Array = []
	for item in _array(value.get("anchors")):
		var anchor: Variant = _anchor(item)
		if anchor == null:
			return null
		anchors.append(anchor)
	if anchors.size() > 32 or not _unique_objects(anchors):
		return null
	if typeof(value.get("detail_truncated")) != TYPE_BOOL:
		return null
	var model := RowContextModel.new()
	model.row_id = value["row_id"]
	model.source_refs = refs
	model.anchors = anchors
	model.detail_truncated = bool(value["detail_truncated"])
	return model


static func _source_ref(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if str(value.get("source_kind", "")) not in SOURCE_KINDS:
		return null
	if not _is_string(value.get("source_id")) or not _nonneg_int(value.get("tick")):
		return null
	if not _optional_string(value.get("owner_id")):
		return null
	if str(value["source_kind"]) in OWNER_SOURCE_KINDS and value.get("owner_id") == null:
		return null
	var model := SourceRefModel.new()
	model.source_kind = value["source_kind"]
	model.source_id = value["source_id"]
	model.tick = int(value["tick"])
	model.owner_id = value.get("owner_id")
	return model


static func _anchor(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY or str(value.get("kind", "")) not in ANCHOR_KINDS:
		return null
	var kind := str(value["kind"])
	if kind == "none":
		if value.get("location_id") != null or value.get("entity_id") != null or value.get("evidence_ref") != null or value.get("evidence_tick") != null:
			return null
		return AnchorModel.new()
	if not _is_string(value.get("location_id")) or not _nonneg_int(value.get("evidence_tick")):
		return null
	var evidence: Variant = _source_ref(value.get("evidence_ref"))
	if evidence == null or evidence.tick != int(value["evidence_tick"]):
		return null
	if kind != "location" and not _is_string(value.get("entity_id")):
		return null
	var model := AnchorModel.new()
	model.kind = kind
	model.location_id = value["location_id"]
	model.entity_id = value.get("entity_id")
	model.evidence_ref = evidence
	model.evidence_tick = int(value["evidence_tick"])
	return model


static func _layer_context(value: Variant, scope: ScopeModel, boundary_tick: int) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	var row_scope: Variant = _scope(value.get("scope"))
	var window: Variant = _window(value.get("window"))
	var coverage: Variant = _coverage(value.get("coverage"))
	if row_scope == null or window == null or coverage == null or not _is_string(value.get("policy_version")):
		return null
	if row_scope.layer != scope.layer or row_scope.evidence_class != scope.evidence_class or row_scope.owner_id != scope.owner_id:
		return null
	if not _nonneg_int(value.get("boundary_tick")) or int(value["boundary_tick"]) != boundary_tick:
		return null
	if window.end_tick > boundary_tick:
		return null
	var model := LayerContextModel.new()
	model.scope = row_scope
	model.boundary_tick = boundary_tick
	model.window = window
	model.policy_version = value["policy_version"]
	model.coverage = coverage
	return model


static func _scope(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	var layer: Variant = value.get("layer")
	if layer != null and not _is_string(layer):
		return null
	var evidence := str(value.get("evidence_class", ""))
	if not _optional_string(value.get("owner_id")):
		return null
	if evidence not in EVIDENCE_VALUES:
		return null
	if (evidence == "SUBJECTIVE") != (value.get("owner_id") != null):
		return null
	var model := ScopeModel.new()
	model.layer = layer
	model.evidence_class = _evidence_value(evidence)
	model.owner_id = value.get("owner_id")
	return model


static func _catalogue_scope(value: Variant) -> Variant:
	var scope: Variant = _scope(value)
	if scope == null:
		return null
	if not _optional_string(value.get("layer")):
		return null
	if scope.layer != null and scope.layer not in LAYERS and scope.layer not in SECTIONS:
		return null
	if scope.evidence_class == Evidence.OBJECTIVE:
		if scope.layer != null and scope.layer != "migration" and scope.layer not in SECTIONS:
			return null
	elif scope.layer != null and scope.layer not in LAYERS:
		return null
	return scope


static func _cursor(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if not _is_string(value.get("run_id")) or not _is_string(value.get("world_id")):
		return null
	if not _nonneg_int(value.get("tick")) or not _nonneg_int(value.get("revision")):
		return null
	if not _optional_nonneg_int(value.get("through_sequence")) or not _optional_nonneg_int(value.get("boundary_tick")):
		return null
	if value.get("through_sequence") != null and value.get("boundary_tick") != null:
		return null
	if value.get("boundary_tick") != null and int(value["boundary_tick"]) != int(value["tick"]):
		return null
	var model := CursorModel.new()
	model.run_id = value["run_id"]
	model.world_id = value["world_id"]
	model.tick = int(value["tick"])
	model.through_sequence = value.get("through_sequence")
	model.boundary_tick = value.get("boundary_tick")
	model.revision = int(value["revision"])
	return model


static func _requested_cursor(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if not _optional_nonneg_int(value.get("tick")) or not _optional_nonneg_int(value.get("through_sequence")):
		return null
	if value.get("through_sequence") != null and value.get("tick") == null:
		return null
	var model := RequestedCursorModel.new()
	model.tick = value.get("tick")
	model.through_sequence = value.get("through_sequence")
	return model


static func _publication(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if not _is_string(value.get("publication_id")) or not _is_string(value.get("policy_version")):
		return null
	var digest := str(value.get("digest", ""))
	if digest.length() != 64:
		return null
	for index in digest.length():
		if digest[index] not in "0123456789abcdef":
			return null
	var model := PublicationModel.new()
	model.publication_id = value["publication_id"]
	model.digest = digest
	model.policy_version = value["policy_version"]
	return model


static func _optional_publication(value: Variant) -> Variant:
	return null if value == null else _publication(value)


static func _window(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if not _nonneg_int(value.get("start_tick")) or not _nonneg_int(value.get("end_tick")):
		return null
	if int(value["start_tick"]) > int(value["end_tick"]):
		return null
	var model := WindowModel.new()
	model.start_tick = int(value["start_tick"])
	model.end_tick = int(value["end_tick"])
	return model


static func _coverage(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY or str(value.get("state", "")) not in COVERAGE_STATES:
		return null
	if not _optional_string(value.get("reason")):
		return null
	if value.get("reason") != null and str(value["reason"]) not in COVERAGE_REASONS:
		return null
	for key in ["capture_start", "capture_end", "observed_count", "expected_count"]:
		if not _optional_nonneg_int(value.get(key)):
			return null
	var start: Variant = value.get("capture_start")
	var finish: Variant = value.get("capture_end")
	if (start == null) != (finish == null):
		return null
	if start != null and int(start) > int(finish):
		return null
	var bands: Array = []
	var previous_end := -1
	for item in _array(value.get("missing_intervals")):
		var band: Variant = _window(item)
		if band == null or band.start_tick >= band.end_tick or band.start_tick < previous_end:
			return null
		if start != null and (band.start_tick < int(start) or band.end_tick > int(finish)):
			return null
		previous_end = band.end_tick
		bands.append(band)
	var state := str(value["state"])
	if state == "complete":
		if not bands.is_empty() or value.get("reason") != null:
			return null
		if value.get("observed_count") != null and value.get("expected_count") != null and int(value["observed_count"]) != int(value["expected_count"]):
			return null
	elif value.get("reason") == null:
		return null
	var model := CoverageModel.new()
	model.state = state
	model.reason = value.get("reason")
	model.capture_start = start
	model.capture_end = finish
	model.missing_intervals = bands
	model.observed_count = value.get("observed_count")
	model.expected_count = value.get("expected_count")
	return model


static func _catalogue_boundary(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if not _nonneg_int(value.get("boundary_tick")) or not _nonneg_int(value.get("revision")):
		return null
	var coverage: Variant = _coverage(value.get("coverage"))
	var layers: Variant = _string_array(value.get("layers"))
	if coverage == null or layers == null:
		return null
	for layer in layers:
		if layer not in LAYERS:
			return null
	if not _unique_strings(layers):
		return null
	var model := CatalogueBoundaryModel.new()
	model.boundary_tick = int(value["boundary_tick"])
	model.revision = int(value["revision"])
	model.coverage = coverage
	model.layers = layers
	return model


static func _availability_fields(value: Dictionary, publication: Variant) -> bool:
	var availability := str(value.get("availability", ""))
	if availability not in ["available", "unavailable"]:
		return false
	if not _optional_string(value.get("reason")):
		return false
	if value.get("reason") != null and str(value["reason"]) not in AVAILABILITY_REASONS:
		return false
	if availability == "available" and (publication == null or value.get("reason") != null):
		return false
	if availability == "unavailable" and value.get("reason") == null:
		return false
	return _page_fields(value)


static func _page_fields(value: Dictionary) -> bool:
	if not _optional_string(value.get("next_cursor")) or typeof(value.get("truncated")) != TYPE_BOOL:
		return false
	if bool(value.get("truncated", false)) != (value.get("next_cursor") != null):
		return false
	return true


static func _contribution(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if not _is_string(value.get("actor_id")) or not _nonneg_int(value.get("tick")) or not _nonneg_int(value.get("labor_units")) or not _nonneg_int(value.get("material_count")):
		return null
	if not _optional_string(value.get("item_id")):
		return null
	var model := ContributionModel.new()
	model.actor_id = value["actor_id"]
	model.tick = int(value["tick"])
	model.labor_units = int(value["labor_units"])
	model.material_count = int(value["material_count"])
	model.item_id = value.get("item_id")
	return model


static func _public_acts(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	for key in ["benefit_count", "draw_count", "maintenance_count", "opposition_count"]:
		if not _nonneg_int(value.get(key, 0)):
			return null
	var model := PublicActsModel.new()
	model.benefit_count = int(value.get("benefit_count", 0))
	model.draw_count = int(value.get("draw_count", 0))
	model.maintenance_count = int(value.get("maintenance_count", 0))
	model.opposition_count = int(value.get("opposition_count", 0))
	return model


static func _item_counts(value: Variant) -> Variant:
	if typeof(value) != TYPE_ARRAY:
		return null
	var result: Array = []
	for item in value:
		if typeof(item) != TYPE_DICTIONARY or str(item.get("kind", "")) not in ITEM_KINDS or not _nonneg_int(item.get("count")):
			return null
		var model := ItemCountModel.new()
		model.kind = item["kind"]
		model.count = int(item["count"])
		result.append(model)
	return result


static func _evidence_value(wire: String) -> String:
	match wire:
		"OBJECTIVE":
			return Evidence.OBJECTIVE
		"SUBJECTIVE":
			return Evidence.SUBJECTIVE
		"ANALYTICAL":
			return Evidence.ANALYTICAL
		_:
			return ""


static func _failure(payload: Variant, expected_schema: String) -> Dictionary:
	var code := "civilization_invalid"
	if typeof(payload) == TYPE_DICTIONARY and payload.get("schema_version", expected_schema) != expected_schema:
		code = "civilization_schema_unsupported"
	return {"ok": false, "reason_code": code}


static func _is_string(value: Variant) -> bool:
	return typeof(value) == TYPE_STRING and not str(value).is_empty()


static func _optional_string(value: Variant) -> bool:
	return value == null or _is_string(value)


static func _nonneg_int(value: Variant) -> bool:
	if typeof(value) == TYPE_INT:
		return int(value) >= 0
	if typeof(value) == TYPE_FLOAT:
		return is_finite(value) and float(value) == floor(float(value)) and float(value) >= 0.0
	return false


static func _optional_nonneg_int(value: Variant) -> bool:
	return value == null or _nonneg_int(value)


static func _finite(value: Variant) -> bool:
	if typeof(value) == TYPE_INT:
		return true
	return typeof(value) == TYPE_FLOAT and is_finite(value)


static func _optional_finite(value: Variant) -> bool:
	return value == null or _finite(value)


static func _array(value: Variant) -> Array:
	return value if typeof(value) == TYPE_ARRAY else []


static func _string_array(value: Variant) -> Variant:
	if typeof(value) != TYPE_ARRAY:
		return null
	var result: Array = []
	for item in value:
		if not _is_string(item):
			return null
		result.append(item)
	return result


static func _unique_strings(values: Array) -> bool:
	var seen := {}
	for value in values:
		if seen.has(value):
			return false
		seen[value] = true
	return true


static func _unique_objects(values: Array) -> bool:
	var seen := {}
	for value in values:
		var key := ""
		if value is SourceRefModel:
			key = "%s|%s|%s|%s" % [value.source_kind, value.source_id, value.tick, value.owner_id]
		elif value is AnchorModel:
			key = "%s|%s|%s|%s|%s" % [value.kind, value.location_id, value.entity_id, value.evidence_tick, value.evidence_ref.source_id if value.evidence_ref != null else ""]
		else:
			key = str(value)
		if seen.has(key):
			return false
		seen[key] = true
	return true


static func _sorted_unique(rows: Array, property: String) -> bool:
	var previous := ""
	for row in rows:
		var key := str(row.context.get(property))
		if key <= previous:
			return false
		previous = key
	return true


