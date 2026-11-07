extends Node2D

## Read-only four-layer border overlay. Presentation only: it never advances
## simulation state and never reads world authority.

const ObserverLog := preload("res://scripts/log.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")

const LAYERS := {
	"physical_control": EvidenceClass.OBJECTIVE,
	"subjective_claims": EvidenceClass.SUBJECTIVE,
	"subjective_agreements": EvidenceClass.SUBJECTIVE,
	"analytical_pattern": EvidenceClass.ANALYTICAL,
}

const KIND_TO_LAYER := {
	"border_physical": "physical_control",
	"border_claims": "subjective_claims",
	"border_agreements": "subjective_agreements",
	"border_patterns": "analytical_pattern",
}

const FORBIDDEN_FIELDS := [
	"winner",
	"loser",
	"legitimate",
	"legitimacy",
	"sovereignty",
	"sovereign",
	"score",
	"composite",
	"ownership",
	"country_owner",
	"raw_agent_id",
	"raw_entity_id",
	"raw_owner_id",
	"agent_id",
	"entity_id",
	"owner_id",
]

var enabled := false
var _payload: Variant = null
var _centers := {}
var _centers_by_token := {}
var _layer := ""


static func layer_for_kind(kind: String) -> String:
	return str(KIND_TO_LAYER.get(kind, ""))


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
	return "bloc-" + context.finish().hex_encode().substr(0, 16)


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
		ObserverLog.warn("view", "border_overlay_rejected reason_code=unknown_layer")
		_payload = null
		_layer = ""
		_rebuild()
		return
	if _contains_forbidden(payload):
		ObserverLog.warn("view", "border_overlay_rejected reason_code=forbidden_field")
		_payload = null
		_layer = ""
		_rebuild()
		return
	_payload = payload
	_layer = layer
	_rebuild()


func _marker_style(layer: String) -> String:
	match layer:
		"physical_control":
			return "solid"
		"subjective_claims":
			return "dashed"
		"subjective_agreements":
			return "double_outline"
		"analytical_pattern":
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
		var domain := str(row.get("domain_token", ""))
		var tokens: Array = []
		var listed: Variant = row.get("location_tokens", null)
		if typeof(listed) == TYPE_ARRAY:
			tokens = listed
		else:
			var single := str(row.get("location_id", row.get("location_token", "")))
			if single != "":
				tokens = [single]
		if tokens.is_empty():
			tokens = [""]
		for item in tokens:
			var location := str(item)
			var key := location if location != "" else domain
			if key == "" or seen.has(key):
				continue
			seen[key] = true
			var marker := Node2D.new()
			marker.name = "BorderMarker"
			marker.position = _centers_by_token.get(key, Vector2.ZERO)
			marker.set_meta("overlay_kind", _kind_for_layer())
			marker.set_meta("evidence_class", evidence_for_layer(_layer))
			marker.set_meta("layer", _layer)
			marker.set_meta("style", _marker_style(_layer))
			marker.set_meta("location_id", location)
			marker.set_meta("domain_token", domain)
			marker.set_meta("copy", _copy())
			add_child(marker)


func _rows() -> Array:
	if typeof(_payload) != TYPE_DICTIONARY:
		return []
	var value: Variant = _payload.get("rows", _payload.get("items", []))
	if typeof(value) != TYPE_ARRAY:
		return []
	return value


func _kind_for_layer() -> String:
	for key in KIND_TO_LAYER.keys():
		if KIND_TO_LAYER[key] == _layer:
			return key
	return "border_patterns"


func _copy() -> String:
	match _layer:
		"physical_control":
			return "OBJECTIVE physical presence and use evidence"
		"subjective_claims":
			return "SUBJECTIVE selected-owner claim"
		"subjective_agreements":
			return "SUBJECTIVE selected-owner agreement belief"
		_:
			return "ANALYTICAL control pattern"
