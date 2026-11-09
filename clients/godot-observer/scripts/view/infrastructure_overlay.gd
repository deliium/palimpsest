extends Node2D

## Read-only four-kind infrastructure overlay. Presentation only: it never
## advances simulation state and never invents a civilization score.

const ObserverLog := preload("res://scripts/log.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")

const INFRASTRUCTURE_NODE := "infrastructure_node"
const INFRASTRUCTURE_EDGE := "infrastructure_edge"
const INFRASTRUCTURE_DAMAGED := "infrastructure_damaged"
const INFRASTRUCTURE_DESTROYED := "infrastructure_destroyed"

const LAYERS := {
	"infrastructure_node": EvidenceClass.OBJECTIVE,
	"infrastructure_edge": EvidenceClass.OBJECTIVE,
	"infrastructure_damaged": EvidenceClass.OBJECTIVE,
	"infrastructure_destroyed": EvidenceClass.OBJECTIVE,
}

const KIND_TO_LAYER := {
	"infrastructure_node": "infrastructure_node",
	"infrastructure_edge": "infrastructure_edge",
	"infrastructure_damaged": "infrastructure_damaged",
	"infrastructure_destroyed": "infrastructure_destroyed",
}

const FORBIDDEN_FIELDS := [
	"score",
	"infrastructure_score",
	"civilization_score",
	"composite",
	"planner",
	"auto_maintain",
	"raw_agent_id",
	"raw_entity_id",
	"raw_owner_id",
	"agent_id",
	"entity_id",
	"owner_id",
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
	return "iloc-" + context.finish().hex_encode().substr(0, 16)


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
		ObserverLog.warn("view", "infrastructure_overlay_rejected reason_code=unknown_kind")
		_payload = null
		_layer = ""
		_rebuild()
		return
	if _contains_forbidden(payload):
		ObserverLog.warn("view", "infrastructure_overlay_rejected reason_code=forbidden_field")
		_payload = null
		_layer = ""
		_rebuild()
		return
	_payload = payload
	_layer = layer
	_rebuild()


func _marker_style(layer: String) -> String:
	match layer:
		"infrastructure_node":
			return "solid"
		"infrastructure_edge":
			return "line"
		"infrastructure_damaged":
			return "dashed"
		"infrastructure_destroyed":
			return "dotted"
		_:
			return "unknown"


func _rebuild() -> void:
	for child in get_children():
		remove_child(child)
		child.free()
	if not enabled or _payload == null:
		return
	var seen := {}
	for row in _rows():
		if typeof(row) != TYPE_DICTIONARY:
			continue
		if not _row_matches_layer(row):
			continue
		var location := str(row.get("location_id", row.get("location_token", "")))
		var endpoint := str(row.get("endpoint_location_id", ""))
		var key := location
		if _layer == "infrastructure_edge" and endpoint != "":
			key = "%s|%s" % [location, endpoint]
		if key == "" or seen.has(key):
			continue
		seen[key] = true
		var marker := Node2D.new()
		marker.name = "InfrastructureMarker"
		marker.position = _centers_by_token.get(location, Vector2.ZERO)
		marker.set_meta("overlay_kind", _layer)
		marker.set_meta("evidence_class", evidence_for_layer(_layer))
		marker.set_meta("layer", _layer)
		marker.set_meta("style", _marker_style(_layer))
		marker.set_meta("location_id", location)
		marker.set_meta("endpoint_location_id", endpoint)
		marker.set_meta("copy", _copy())
		add_child(marker)


func _row_matches_layer(row: Dictionary) -> bool:
	var status := str(row.get("status", ""))
	var topology := str(row.get("topology", ""))
	match _layer:
		"infrastructure_node":
			return topology == "node" and status == "operational"
		"infrastructure_edge":
			return topology == "edge" and status == "operational"
		"infrastructure_damaged":
			return status == "damaged"
		"infrastructure_destroyed":
			return status == "destroyed"
		_:
			return false


func _rows() -> Array:
	if typeof(_payload) != TYPE_DICTIONARY:
		return []
	var value: Variant = _payload.get("rows", _payload.get("items", []))
	if typeof(value) != TYPE_ARRAY:
		return []
	return value


func _copy() -> String:
	match _layer:
		"infrastructure_node":
			return "OBJECTIVE operational node infrastructure"
		"infrastructure_edge":
			return "OBJECTIVE operational edge infrastructure"
		"infrastructure_damaged":
			return "OBJECTIVE damaged infrastructure"
		_:
			return "OBJECTIVE destroyed infrastructure"
