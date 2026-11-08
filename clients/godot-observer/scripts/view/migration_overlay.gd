extends Node2D

## Read-only four-kind migration overlay. Presentation only: it never advances
## simulation state and never reads world authority.

const ObserverLog := preload("res://scripts/log.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")

const MIGRATION_ROUTE := "migration_route"
const MIGRATION_CAUSE := "migration_cause"
const MIGRATION_WAVE := "migration_wave"
const MIGRATION_INTEGRATION := "migration_integration"

const LAYERS := {
	"migration_route": EvidenceClass.OBJECTIVE,
	"migration_cause": EvidenceClass.SUBJECTIVE,
	"migration_wave": EvidenceClass.ANALYTICAL,
	"migration_integration": EvidenceClass.ANALYTICAL,
}

const KIND_TO_LAYER := {
	"migration_route": "migration_route",
	"migration_cause": "migration_cause",
	"migration_wave": "migration_wave",
	"migration_integration": "migration_integration",
}

const FORBIDDEN_FIELDS := [
	"refugee",
	"asylum",
	"forced",
	"displaced",
	"wellbeing",
	"assimilation",
	"score",
	"composite",
	"raw_agent_id",
	"raw_entity_id",
	"raw_owner_id",
	"agent_id",
	"entity_id",
	"owner_id",
	"cause_text",
	"frame_body",
	"evidence_body",
]

var enabled := false
var _payload: Variant = null
var _centers := {}
var _centers_by_token := {}
var _layer := ""


static func layer_for_kind(kind: String) -> String:
	return str(KIND_TO_LAYER.get(kind, ""))


static func evidence_for_kind(kind: String) -> String:
	var layer := layer_for_kind(kind)
	if layer == "":
		return ""
	return str(LAYERS.get(layer, ""))


static func evidence_for_layer(layer: String) -> String:
	return str(LAYERS.get(layer, ""))


static func is_valid_layer(layer: String) -> bool:
	return LAYERS.has(layer)


static func _contains_forbidden(value: Variant) -> bool:
	if typeof(value) == TYPE_DICTIONARY:
		for key in value.keys():
			if FORBIDDEN_FIELDS.has(str(key)):
				return true
			if _contains_forbidden(value[key]):
				return true
	elif typeof(value) == TYPE_ARRAY:
		for item in value:
			if _contains_forbidden(item):
				return true
	return false


func _location_token(value: String) -> String:
	if value == "":
		return ""
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(value.to_utf8_buffer())
	return "mdl-" + context.finish().hex_encode().substr(0, 16)


func set_centers(centers: Dictionary) -> void:
	_centers = centers
	_centers_by_token = {}
	for key in centers.keys():
		var text := str(key)
		_centers_by_token[text] = centers[key]
		_centers_by_token[_location_token(text)] = centers[key]
	_rebuild()


func set_enabled(value: bool) -> void:
	enabled = value
	_rebuild()


func clear() -> void:
	_payload = null
	_layer = ""
	_rebuild()


func apply_payload(payload: Variant, kind: String = "") -> void:
	if typeof(payload) != TYPE_DICTIONARY:
		_payload = null
		_layer = ""
		_rebuild()
		return
	var layer := layer_for_kind(kind)
	if layer == "":
		layer = str(payload.get("layer", ""))
	if not is_valid_layer(layer):
		ObserverLog.warn("view", "migration_overlay_rejected reason_code=unknown_kind")
		_payload = null
		_layer = ""
		_rebuild()
		return
	if _contains_forbidden(payload):
		ObserverLog.warn("view", "migration_overlay_rejected reason_code=forbidden_field")
		_payload = null
		_layer = ""
		_rebuild()
		return
	_payload = payload
	_layer = layer
	_rebuild()


func _marker_style(layer: String) -> String:
	match layer:
		"migration_route":
			return "solid"
		"migration_cause":
			return "dashed"
		"migration_wave":
			return "dotted"
		"migration_integration":
			return "double_outline"
		_:
			return "hidden"


func _rebuild() -> void:
	for child in get_children():
		remove_child(child)
		child.free()
	if not enabled or _payload == null or _layer == "":
		return
	var seen := {}
	for row in _rows():
		if typeof(row) != TYPE_DICTIONARY:
			continue
		var tokens: Array = _row_tokens(row)
		if tokens.is_empty():
			tokens = [""]
		for item in tokens:
			var location := str(item)
			var key := location if location != "" else str(row.get("wave_token", row.get("route_token", row.get("cause_token", row.get("outcome_token", "")))))
			if key == "" or seen.has(key):
				continue
			seen[key] = true
			var marker := Node2D.new()
			marker.name = "MigrationMarker"
			marker.position = _centers_by_token.get(key, Vector2.ZERO)
			marker.set_meta("overlay_kind", _layer)
			marker.set_meta("evidence_class", evidence_for_layer(_layer))
			marker.set_meta("layer", _layer)
			marker.set_meta("style", _marker_style(_layer))
			marker.set_meta("location_id", location)
			marker.set_meta("copy", _copy())
			add_child(marker)


func _row_tokens(row: Dictionary) -> Array:
	match _layer:
		"migration_route":
			var listed: Variant = row.get("route_tokens", null)
			if typeof(listed) == TYPE_ARRAY and not listed.is_empty():
				return listed
			var origin := str(row.get("origin_token", ""))
			var destination := str(row.get("destination_token", ""))
			var out: Array = []
			if origin != "":
				out.append(origin)
			if destination != "":
				out.append(destination)
			return out
		"migration_cause":
			var anchor := str(row.get("anchor_token", ""))
			if anchor != "":
				return [anchor]
			return [str(row.get("cause_token", ""))]
		"migration_wave":
			var wave_routes: Variant = row.get("route_tokens", null)
			if typeof(wave_routes) == TYPE_ARRAY and not wave_routes.is_empty():
				return wave_routes
			return [str(row.get("destination_token", row.get("origin_token", "")))]
		"migration_integration":
			return [str(row.get("destination_token", ""))]
		_:
			return []


func _rows() -> Array:
	if typeof(_payload) != TYPE_DICTIONARY:
		return []
	var value: Variant = _payload.get("rows", _payload.get("items", []))
	if typeof(value) != TYPE_ARRAY:
		return []
	return value


func _copy() -> String:
	match _layer:
		"migration_route":
			return "OBJECTIVE published route tokens"
		"migration_cause":
			return "SUBJECTIVE owner cause evidence"
		"migration_wave":
			return "ANALYTICAL wave / displacement_like classification"
		_:
			return "ANALYTICAL integration outcome counts"
