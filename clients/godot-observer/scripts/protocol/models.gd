extends RefCounted
class_name ObserverProtocol

const ObserverLog := preload("res://scripts/log.gd")

const PROTOCOL_VERSION := "observer-protocol-v1"
const LAYOUT_SCHEMA_VERSION := "observer-layout-v1"

const KNOWN_TYPES: Array[String] = [
	"AGENT_MOVED",
	"AGENT_SEARCHED",
	"AGENT_TOOK_ITEM",
	"AGENT_DROPPED_ITEM",
	"AGENT_GAVE_ITEM",
	"AGENT_ATE_ITEM",
	"AGENT_DRANK",
	"AGENT_SLEPT",
	"AGENT_TALKED",
	"AGENT_ASKED",
	"AGENT_TOLD",
	"AGENT_HELPED",
	"AGENT_ATTACKED",
	"AGENT_FLED",
	"AGENT_WAITED",
	"WEATHER_CHANGED",
	"RESOURCE_REGENERATED",
	"NEEDS_APPLIED",
	"EXPOSURE_APPLIED",
	"AGENT_DIED",
	"RESOURCE_HARVESTED",
	"CRAFT_STARTED",
	"ITEM_CRAFTED",
	"STRUCTURE_BUILT",
	"STRUCTURE_REPAIRED",
	"ITEM_STORED",
	"SEASON_CHANGED",
	"TEMPERATURE_BAND_CHANGED",
	"RESOURCE_NODE_DEPLETED",
	"RESOURCE_NODE_RECOVERED",
	"ENVIRONMENTAL_HAZARD_STARTED",
	"ENVIRONMENTAL_HAZARD_ENDED",
	"ARTIFACT_CREATED",
	"ARTIFACT_MODIFIED",
	"ARTIFACT_MOVED",
	"ARTIFACT_DESTROYED",
	"AGENT_CREATED",
	"AGENT_ENTERED_WORLD",
	"LIFECYCLE_STAGE_CHANGED",
]

const BODY_FROM_TARGET: Array[String] = [
	"AGENT_DIED",
	"NEEDS_APPLIED",
	"EXPOSURE_APPLIED",
]


class ParseResult:
	extends RefCounted
	var ok: bool = false
	var reason_code: String = ""
	var value: Variant = null

	static func success(parsed: Variant, kind: String, id_count: int) -> ParseResult:
		ObserverLog.debug("protocol", "parsed kind=%s id_count=%s" % [kind, id_count])
		var result := ParseResult.new()
		result.ok = true
		result.value = parsed
		return result

	static func failure(reason: String) -> ParseResult:
		ObserverLog.error("protocol", "parse_failed reason_code=%s" % reason)
		var result := ParseResult.new()
		result.ok = false
		result.reason_code = reason
		return result


class PointModel:
	extends RefCounted
	var x: float = 0.0
	var y: float = 0.0


class BoundsModel:
	extends RefCounted
	var x: float = 0.0
	var y: float = 0.0
	var width: float = 0.0
	var height: float = 0.0


class SlotModel:
	extends RefCounted
	var slot_index: int = 0
	var local_x: Variant = null
	var local_y: Variant = null

	func has_coordinates() -> bool:
		return local_x != null and local_y != null


class PresentationModel:
	extends RefCounted
	var screen_position: PointModel = null
	var visual_bounds: BoundsModel = null
	var theme: Variant = null
	var icon_ref: Variant = null
	var background_ref: Variant = null
	var connection_anchors: Array = []
	var slot_anchors: Array = []


class LocationModel:
	extends RefCounted
	var location_id: String = ""
	var name: String = ""
	var display_name: String = ""
	var neighbor_ids: Array[String] = []
	var presentation: PresentationModel = null


class MeasuresModel:
	extends RefCounted
	var health: float = 0.0
	var hunger: float = 0.0
	var thirst: float = 0.0
	var fatigue: float = 0.0
	var temperature: float = 0.0


class AgentModel:
	extends RefCounted
	var entity_id: String = ""
	var location_id: String = ""
	var life_status: String = ""
	var inventory_ids: Array[String] = []
	var measures: MeasuresModel = null
	var agent_id: Variant = null
	var presentation_slot: SlotModel = null


class ItemModel:
	extends RefCounted
	var item_id: String = ""
	var name: String = ""
	var kind: String = ""
	var location_id: Variant = null
	var holder_id: Variant = null


class ResourceModel:
	extends RefCounted
	var resource_id: String = ""
	var name: String = ""
	var kind: String = ""
	var location_id: String = ""
	var quantity: float = 0.0
	var unit: String = ""


class ArtifactPresentationModel:
	extends RefCounted
	var visual_category: Variant = null
	var icon_key: Variant = null
	var size_category: Variant = null
	var display_label: Variant = null


class ArtifactModel:
	extends RefCounted
	var artifact_id: String = ""
	var kind: String = ""
	var author_id: String = ""
	var created_tick: int = 0
	var content_revision: int = 0
	var location_id: Variant = null
	var holder_id: Variant = null
	var marks: Array[String] = []
	var presentation: ArtifactPresentationModel = null


class StructureModel:
	extends RefCounted
	var structure_id: String = ""
	var location_id: String = ""
	var kind: String = ""
	var integrity: float = 0.0
	var stored_quantity: int = 0
	var presentation: ArtifactPresentationModel = null


class WeatherModel:
	extends RefCounted
	var location_id: String = ""
	var condition: String = ""


class TemperatureBandModel:
	extends RefCounted
	var location_id: String = ""
	var band: String = ""


class HazardModel:
	extends RefCounted
	var location_id: String = ""
	var hazard_kind: String = ""
	var remaining_ticks: int = 0


class WorldModel:
	extends RefCounted
	var tick: int = 0
	var revision: int = 0
	var locations: Array = []
	var agents: Array = []
	var items: Array = []
	var resources: Array = []
	var structures: Array = []
	var artifacts: Array = []
	var weather: Array = []
	var season: Variant = null
	var temperature_bands: Array = []
	var hazards: Array = []

	func id_count() -> int:
		return (
			locations.size()
			+ agents.size()
			+ items.size()
			+ resources.size()
			+ structures.size()
			+ artifacts.size()
		)


class CursorModel:
	extends RefCounted
	var run_id: String = ""
	var mode: String = ""
	var tick: int = 0
	var protocol_version: String = ""
	var sequence: Variant = null
	var after_tick: Variant = null
	var after_sequence: Variant = null


class EventModel:
	extends RefCounted
	var known: bool = false
	var protocol_version: String = ""
	var type: String = ""
	var domain_kind: String = ""
	var event_id: String = ""
	var tick: int = 0
	var sequence: int = 0
	var actor_id: Variant = null
	var target_id: Variant = null
	var item_id: Variant = null
	var resource_id: Variant = null
	var artifact_id: Variant = null
	var origin_location_id: Variant = null
	var destination_location_id: Variant = null
	var recipe_id: Variant = null
	var structure_id: Variant = null
	var season: Variant = null
	var temperature_band: Variant = null
	var hazard_kind: Variant = null
	## Speaker-declared confidence band only; omitted when null. Not a strategy verdict.
	var declared_confidence_band: Variant = null

	func affected_entity_id() -> Variant:
		if type in BODY_FROM_TARGET:
			return target_id
		return actor_id


class FrameModel:
	extends RefCounted
	var protocol_version: String = ""
	var cursor: CursorModel = null
	var world: WorldModel = null
	var events: Array = []
	## Events already folded into world. They are not a second animation list.
	var events_are_folded_history: bool = true


class ManifestModel:
	extends RefCounted
	var protocol_version: String = ""
	var layout_schema_version: String = ""
	var layout_id: String = ""
	var layout_hash: String = ""
	var ordering: String = ""
	var read_only: bool = false
	var event_types: Array[String] = []
	var event_schema_version: int = 0
	var projector_version: String = ""
	var run_id: String = ""
	var parent_run_id: String = ""
	var fork_tick: int = -1
	var intervention_summary: String = ""
	var branch_id: String = ""


class EventPageModel:
	extends RefCounted
	var count: int = 0
	var events: Array = []
	var limit: int = 0


static func parse_manifest(data: Variant) -> ParseResult:
	if typeof(data) != TYPE_DICTIONARY:
		return ParseResult.failure("unsupported_observer_protocol")
	if not _protocol_matches(data):
		return ParseResult.failure("unsupported_observer_protocol")
	var manifest := ManifestModel.new()
	manifest.protocol_version = PROTOCOL_VERSION
	manifest.layout_schema_version = str(
		data.get("layout_schema_version", LAYOUT_SCHEMA_VERSION)
	)
	manifest.layout_id = str(data.get("layout_id", ""))
	manifest.layout_hash = str(data.get("layout_hash", ""))
	manifest.ordering = str(data.get("ordering", ""))
	manifest.read_only = bool(data.get("read_only", false))
	manifest.event_schema_version = int(data.get("event_schema_version", 0))
	manifest.projector_version = str(data.get("projector_version", ""))
	manifest.run_id = str(data.get("run_id", "")).strip_edges()
	manifest.parent_run_id = str(data.get("parent_run_id", "")).strip_edges()
	if data.has("fork_tick") and data.get("fork_tick") != null:
		manifest.fork_tick = int(data.get("fork_tick"))
	manifest.intervention_summary = str(data.get("intervention_summary", "")).strip_edges()
	manifest.branch_id = str(data.get("branch_id", "")).strip_edges()
	var raw_types: Variant = data.get("event_types", [])
	if raw_types is Array:
		for item in raw_types:
			manifest.event_types.append(str(item))
	return ParseResult.success(manifest, "manifest", manifest.event_types.size())


static func parse_branch_list(data: Variant) -> Dictionary:
	## BranchListOut — unknown keys ignored; never invents children.
	if typeof(data) != TYPE_DICTIONARY:
		return {"ok": false, "reason_code": "invalid_json", "items": [], "next_cursor": null, "count": 0}
	var items: Array = []
	var raw_items: Variant = data.get("items", [])
	if raw_items is Array:
		for item in raw_items:
			if typeof(item) != TYPE_DICTIONARY:
				continue
			items.append({
				"child_run_id": str(item.get("child_run_id", "")).strip_edges(),
				"parent_run_id": str(item.get("parent_run_id", "")).strip_edges(),
				"fork_tick": int(item.get("fork_tick", 0)),
				"intervention_summary": str(item.get("intervention_summary", "")).strip_edges(),
				"branch_id": str(item.get("branch_id", "")).strip_edges(),
			})
	var next_cursor: Variant = data.get("next_cursor", null)
	if next_cursor != null:
		next_cursor = str(next_cursor).strip_edges()
		if str(next_cursor).is_empty():
			next_cursor = null
	return {
		"ok": true,
		"reason_code": "",
		"items": items,
		"next_cursor": next_cursor,
		"count": int(data.get("count", items.size())),
	}


static func parse_branch_fork_point(data: Variant) -> Dictionary:
	## BranchForkPointOut — unknown keys ignored.
	if typeof(data) != TYPE_DICTIONARY:
		return {"ok": false, "reason_code": "invalid_json"}
	var parent_run_id := str(data.get("parent_run_id", "")).strip_edges()
	if parent_run_id.is_empty():
		return {"ok": false, "reason_code": "branch_root"}
	return {
		"ok": true,
		"reason_code": "",
		"parent_run_id": parent_run_id,
		"child_run_id": str(data.get("child_run_id", "")).strip_edges(),
		"fork_tick": int(data.get("fork_tick", 0)),
		"parent_observer_tick": int(data.get("parent_observer_tick", data.get("fork_tick", 0))),
		"child_observer_tick": int(data.get("child_observer_tick", data.get("fork_tick", 0))),
	}


static func parse_frame(data: Variant) -> ParseResult:
	if typeof(data) != TYPE_DICTIONARY:
		return ParseResult.failure("unsupported_observer_protocol")
	if not _protocol_matches(data):
		return ParseResult.failure("unsupported_observer_protocol")
	var cursor = _cursor(data.get("cursor", null))
	if cursor is String:
		return ParseResult.failure(cursor)
	var world = _world(data.get("world", null))
	if world is String:
		return ParseResult.failure(world)
	var frame := FrameModel.new()
	frame.protocol_version = PROTOCOL_VERSION
	frame.cursor = cursor
	frame.world = world
	frame.events_are_folded_history = true
	var raw_events: Variant = data.get("events", null)
	if raw_events is Array:
		for item in raw_events:
			var parsed := parse_event(item)
			if not parsed.ok:
				return parsed
			frame.events.append(parsed.value)
	return ParseResult.success(frame, "frame", 1)


static func parse_event(data: Variant) -> ParseResult:
	if typeof(data) != TYPE_DICTIONARY:
		return ParseResult.failure("invalid_event")
	var type_name := str(data.get("type", ""))
	var known := KNOWN_TYPES.has(type_name)
	if known and not _protocol_matches(data):
		return ParseResult.failure("unsupported_observer_protocol")
	if not known:
		ObserverLog.warn("protocol", "unknown_event_type type=%s" % type_name)
	var event := EventModel.new()
	event.known = known
	event.protocol_version = str(data.get("protocol_version", ""))
	event.type = type_name
	event.domain_kind = str(data.get("domain_kind", ""))
	event.event_id = str(data.get("event_id", ""))
	event.tick = int(data.get("tick", 0))
	event.sequence = int(data.get("sequence", 0))
	event.actor_id = _optional_text(data, "actor_id")
	event.target_id = _optional_text(data, "target_id")
	event.item_id = _optional_text(data, "item_id")
	event.resource_id = _optional_text(data, "resource_id")
	event.artifact_id = _optional_text(data, "artifact_id")
	event.origin_location_id = _optional_text(data, "origin_location_id")
	event.destination_location_id = _optional_text(data, "destination_location_id")
	event.recipe_id = _optional_text(data, "recipe_id")
	event.structure_id = _optional_text(data, "structure_id")
	event.season = _optional_text(data, "season")
	event.temperature_band = _optional_text(data, "temperature_band")
	event.hazard_kind = _optional_text(data, "hazard_kind")
	event.declared_confidence_band = _optional_text(data, "declared_confidence_band")
	return ParseResult.success(event, "event", 1)


static func parse_event_page(data: Variant) -> ParseResult:
	if typeof(data) != TYPE_DICTIONARY:
		return ParseResult.failure("invalid_event_page")
	var page := EventPageModel.new()
	page.count = int(data.get("count", 0))
	page.limit = int(data.get("limit", 0))
	var raw_events: Variant = data.get("events", [])
	if raw_events is Array:
		for item in raw_events:
			var parsed := parse_event(item)
			if not parsed.ok:
				return parsed
			page.events.append(parsed.value)
	return ParseResult.success(page, "event_page", page.events.size())


static func parse_text(kind: String, text: String) -> ParseResult:
	var parsed: Variant = JSON.parse_string(text)
	match kind:
		"manifest":
			return parse_manifest(parsed)
		"frame":
			return parse_frame(parsed)
		"event":
			return parse_event(parsed)
		"event_page":
			return parse_event_page(parsed)
		_:
			return ParseResult.failure("unsupported_observer_protocol")


static func _protocol_matches(data: Dictionary) -> bool:
	if not data.has("protocol_version") or data["protocol_version"] == null:
		return false
	return str(data["protocol_version"]) == PROTOCOL_VERSION


static func _optional_text(data: Dictionary, key: String) -> Variant:
	if not data.has(key) or data[key] == null:
		return null
	return str(data[key])


static func _optional_number(data: Dictionary, key: String) -> Variant:
	if not data.has(key) or data[key] == null:
		return null
	return float(data[key])


static func _cursor(data: Variant) -> Variant:
	if typeof(data) != TYPE_DICTIONARY:
		return "unsupported_observer_protocol"
	if not _protocol_matches(data):
		return "unsupported_observer_protocol"
	var cursor := CursorModel.new()
	cursor.run_id = str(data.get("run_id", ""))
	cursor.mode = str(data.get("mode", ""))
	cursor.tick = int(data.get("tick", 0))
	cursor.protocol_version = PROTOCOL_VERSION
	cursor.sequence = _optional_number(data, "sequence")
	if cursor.sequence != null and is_equal_approx(float(cursor.sequence), floor(float(cursor.sequence))):
		cursor.sequence = int(cursor.sequence)
	cursor.after_tick = _optional_number(data, "after_tick")
	if cursor.after_tick != null:
		cursor.after_tick = int(cursor.after_tick)
	cursor.after_sequence = _optional_number(data, "after_sequence")
	if cursor.after_sequence != null:
		cursor.after_sequence = int(cursor.after_sequence)
	return cursor


static func _world(data: Variant) -> Variant:
	if typeof(data) != TYPE_DICTIONARY:
		return "invalid_world"
	var world := WorldModel.new()
	world.tick = int(data.get("tick", 0))
	world.revision = int(data.get("revision", 0))
	for item in _array(data, "locations"):
		var location = _location(item)
		if location is String:
			return location
		world.locations.append(location)
	for item in _array(data, "agents"):
		var agent = _agent(item)
		if agent is String:
			return agent
		world.agents.append(agent)
	for item in _array(data, "items"):
		world.items.append(_item(item))
	for item in _array(data, "resources"):
		world.resources.append(_resource(item))
	for item in _array(data, "structures"):
		var structure = _structure(item)
		if structure is String:
			return structure
		world.structures.append(structure)
	for item in _array(data, "artifacts"):
		var artifact = _artifact(item)
		if artifact is String:
			return artifact
		world.artifacts.append(artifact)
	for item in _array(data, "weather"):
		world.weather.append(_weather(item))
	if data.has("season") and data["season"] != null:
		world.season = str(data["season"])
	for item in _array(data, "temperature_bands"):
		if typeof(item) != TYPE_DICTIONARY:
			return "invalid_temperature_band"
		var band := TemperatureBandModel.new()
		band.location_id = str(item.get("location_id", ""))
		band.band = str(item.get("band", ""))
		world.temperature_bands.append(band)
	for item in _array(data, "hazards"):
		if typeof(item) != TYPE_DICTIONARY:
			return "invalid_hazard"
		var hazard := HazardModel.new()
		hazard.location_id = str(item.get("location_id", ""))
		hazard.hazard_kind = str(item.get("hazard_kind", ""))
		hazard.remaining_ticks = int(item.get("remaining_ticks", 0))
		world.hazards.append(hazard)
	# Claim and analytics keys on world are ignored and do not change occupants.
	return world


static func _array(data: Dictionary, key: String) -> Array:
	var raw: Variant = data.get(key, [])
	if raw is Array:
		return raw
	return []


static func _location(data: Variant) -> Variant:
	if typeof(data) != TYPE_DICTIONARY:
		return "invalid_location"
	var location := LocationModel.new()
	location.location_id = str(data.get("location_id", ""))
	location.name = str(data.get("name", ""))
	location.display_name = str(data.get("display_name", ""))
	for neighbor in _array(data, "neighbor_ids"):
		location.neighbor_ids.append(str(neighbor))
	var presentation = _presentation(data.get("presentation", null))
	if presentation is String:
		return presentation
	location.presentation = presentation
	return location


static func _presentation(data: Variant) -> Variant:
	if data == null:
		return null
	if typeof(data) != TYPE_DICTIONARY:
		return "invalid_presentation"
	var raw_anchors: Variant = data.get("connection_anchors", [])
	if raw_anchors is Dictionary:
		return "invalid_connection_anchors"
	var presentation := PresentationModel.new()
	presentation.screen_position = _point(data.get("screen_position", null))
	presentation.visual_bounds = _bounds(data.get("visual_bounds", null))
	presentation.theme = _optional_text(data, "theme")
	presentation.icon_ref = _optional_text(data, "icon_ref")
	presentation.background_ref = _optional_text(data, "background_ref")
	if raw_anchors is Array:
		for pair in raw_anchors:
			if not pair is Array or pair.size() < 2:
				return "invalid_connection_anchors"
			var point := _point(pair[1])
			if point == null:
				return "invalid_connection_anchors"
			presentation.connection_anchors.append([str(pair[0]), point])
	elif raw_anchors != null:
		return "invalid_connection_anchors"
	for anchor in _array(data, "slot_anchors"):
		var point := _point(anchor)
		if point != null:
			presentation.slot_anchors.append(point)
	return presentation


static func _point(data: Variant) -> PointModel:
	if typeof(data) != TYPE_DICTIONARY:
		return null
	var point := PointModel.new()
	point.x = float(data.get("x", 0.0))
	point.y = float(data.get("y", 0.0))
	return point


static func _bounds(data: Variant) -> BoundsModel:
	if typeof(data) != TYPE_DICTIONARY:
		return null
	var bounds := BoundsModel.new()
	bounds.x = float(data.get("x", 0.0))
	bounds.y = float(data.get("y", 0.0))
	bounds.width = float(data.get("width", 0.0))
	bounds.height = float(data.get("height", 0.0))
	return bounds


static func _agent(data: Variant) -> Variant:
	if typeof(data) != TYPE_DICTIONARY:
		return "invalid_agent"
	var agent := AgentModel.new()
	agent.entity_id = str(data.get("entity_id", ""))
	agent.location_id = str(data.get("location_id", ""))
	agent.life_status = str(data.get("life_status", ""))
	agent.agent_id = _optional_text(data, "agent_id")
	for item_id in _array(data, "inventory_ids"):
		agent.inventory_ids.append(str(item_id))
	var measures = _measures(data.get("measures", null))
	if measures is String:
		return measures
	agent.measures = measures
	var slot_raw: Variant = data.get("presentation_slot", null)
	if slot_raw is Dictionary:
		var slot := SlotModel.new()
		slot.slot_index = int(slot_raw.get("slot_index", 0))
		slot.local_x = _optional_number(slot_raw, "local_x")
		slot.local_y = _optional_number(slot_raw, "local_y")
		agent.presentation_slot = slot
	return agent


static func _measures(data: Variant) -> Variant:
	if data == null:
		return null
	if typeof(data) != TYPE_DICTIONARY:
		return "invalid_measures"
	var measures := MeasuresModel.new()
	measures.health = float(data.get("health", 0.0))
	measures.hunger = float(data.get("hunger", 0.0))
	measures.thirst = float(data.get("thirst", 0.0))
	measures.fatigue = float(data.get("fatigue", 0.0))
	measures.temperature = float(data.get("temperature", 0.0))
	return measures


static func _item(data: Dictionary) -> ItemModel:
	var item := ItemModel.new()
	item.item_id = str(data.get("item_id", ""))
	item.name = str(data.get("name", ""))
	item.kind = str(data.get("kind", ""))
	item.location_id = _optional_text(data, "location_id")
	item.holder_id = _optional_text(data, "holder_id")
	return item


static func _resource(data: Dictionary) -> ResourceModel:
	var resource := ResourceModel.new()
	resource.resource_id = str(data.get("resource_id", ""))
	resource.name = str(data.get("name", ""))
	resource.kind = str(data.get("kind", ""))
	resource.location_id = str(data.get("location_id", ""))
	resource.quantity = float(data.get("quantity", 0.0))
	resource.unit = str(data.get("unit", ""))
	return resource


static func _structure(data: Variant) -> Variant:
	if typeof(data) != TYPE_DICTIONARY:
		return "invalid_structure"
	var structure := StructureModel.new()
	structure.structure_id = str(data.get("structure_id", ""))
	structure.location_id = str(data.get("location_id", ""))
	structure.kind = str(data.get("kind", ""))
	structure.integrity = float(data.get("integrity", 0.0))
	structure.stored_quantity = int(data.get("stored_quantity", 0))
	var presentation_raw: Variant = data.get("presentation", null)
	if presentation_raw != null:
		if typeof(presentation_raw) != TYPE_DICTIONARY:
			return "invalid_structure_presentation"
		var presentation := ArtifactPresentationModel.new()
		presentation.visual_category = _optional_text(presentation_raw, "visual_category")
		presentation.icon_key = _optional_text(presentation_raw, "icon_key")
		presentation.size_category = _optional_text(presentation_raw, "size_category")
		presentation.display_label = _optional_text(presentation_raw, "display_label")
		structure.presentation = presentation
	return structure


static func _artifact(data: Variant) -> Variant:
	if typeof(data) != TYPE_DICTIONARY:
		return "invalid_artifact"
	var artifact := ArtifactModel.new()
	artifact.artifact_id = str(data.get("artifact_id", ""))
	artifact.kind = str(data.get("kind", ""))
	artifact.author_id = str(data.get("author_id", ""))
	artifact.created_tick = int(data.get("created_tick", 0))
	artifact.content_revision = int(data.get("content_revision", 0))
	artifact.location_id = _optional_text(data, "location_id")
	artifact.holder_id = _optional_text(data, "holder_id")
	for mark in _array(data, "marks"):
		artifact.marks.append(str(mark))
	var presentation_raw: Variant = data.get("presentation", null)
	if presentation_raw != null:
		if typeof(presentation_raw) != TYPE_DICTIONARY:
			return "invalid_artifact_presentation"
		var presentation := ArtifactPresentationModel.new()
		presentation.visual_category = _optional_text(presentation_raw, "visual_category")
		presentation.icon_key = _optional_text(presentation_raw, "icon_key")
		presentation.size_category = _optional_text(presentation_raw, "size_category")
		presentation.display_label = _optional_text(presentation_raw, "display_label")
		artifact.presentation = presentation
	return artifact


static func _weather(data: Dictionary) -> WeatherModel:
	var weather := WeatherModel.new()
	weather.location_id = str(data.get("location_id", ""))
	weather.condition = str(data.get("condition", ""))
	return weather
