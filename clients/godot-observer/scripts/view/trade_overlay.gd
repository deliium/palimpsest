extends Node2D

## Read-only trade-network overlay. Analytical presentation only: it never
## advances simulation state, plans routes, or invents a market or score.

const ObserverLog := preload("res://scripts/log.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")

const TRADE_CORRIDORS := "trade_corridors"
const TRADE_MAJOR_LOCATIONS := "trade_major_locations"
const TRADE_CROSS_SOCIETY := "trade_cross_society"
const TRADE_COVERAGE := "trade_coverage"

const LAYERS := {
	"trade_corridors": EvidenceClass.ANALYTICAL,
	"trade_major_locations": EvidenceClass.ANALYTICAL,
	"trade_cross_society": EvidenceClass.ANALYTICAL,
	"trade_coverage": EvidenceClass.ANALYTICAL,
}

const FORBIDDEN_FIELDS := [
	"price",
	"money",
	"currency",
	"planner",
	"quota",
	"allocation",
	"score",
	"ranking",
	"trade_score",
]

var enabled := false
var window_index := -1
var _payload: Variant = null
var _layer := ""
var _counts := {
	"corridors": 0,
	"major_locations": 0,
	"trade_posts": 0,
	"cross_society": 0,
	"unresolved_anchors": 0,
	"networks": 0,
	"sustained": 0,
}
var last_rejection := ""
var status_message := ""


static func is_valid_layer(layer: String) -> bool:
	return LAYERS.has(layer)


static func evidence_for_layer(layer: String) -> String:
	return str(LAYERS.get(layer, ""))


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


func set_enabled(value: bool) -> void:
	enabled = value
	_rebuild()


func set_window_index(value: int) -> void:
	window_index = value if value >= 0 else -1


func selected_window() -> int:
	return window_index


func clear() -> void:
	_payload = null
	_layer = ""
	last_rejection = ""
	status_message = ""
	_counts = {
		"corridors": 0,
		"major_locations": 0,
		"trade_posts": 0,
		"cross_society": 0,
		"unresolved_anchors": 0,
		"networks": 0,
		"sustained": 0,
	}
	_rebuild()


func apply_payload(payload: Variant, layer: String = "") -> void:
	if typeof(payload) != TYPE_DICTIONARY:
		clear()
		status_message = "trade_overlay_empty"
		return
	if _contains_forbidden(payload):
		ObserverLog.warn("view", "trade_overlay_rejected reason_code=forbidden_field")
		clear()
		last_rejection = "forbidden_field"
		return
	if layer != "" and not is_valid_layer(layer):
		clear()
		last_rejection = "unknown_layer"
		return
	_payload = payload
	_layer = layer
	last_rejection = ""
	status_message = ""
	_rebuild()


func layer_counts() -> Dictionary:
	return _counts.duplicate(true)


func marker_kinds() -> Array:
	var kinds: Array = []
	for child in get_children():
		kinds.append(str(child.get_meta("marker_kind", "")))
	return kinds


func network_labels() -> Array:
	var labels: Array = []
	for child in get_children():
		var label := str(child.get_meta("network_label", ""))
		if label != "":
			labels.append(label)
	return labels


func _rows(payload: Dictionary, key: String) -> Array:
	var value: Variant = payload.get(key, [])
	return value if typeof(value) == TYPE_ARRAY else []


func _rebuild() -> void:
	for child in get_children():
		remove_child(child)
		child.free()
	_counts = {
		"corridors": 0,
		"major_locations": 0,
		"trade_posts": 0,
		"cross_society": 0,
		"unresolved_anchors": 0,
		"networks": 0,
		"sustained": 0,
	}
	if not enabled or typeof(_payload) != TYPE_DICTIONARY:
		return
	var payload: Dictionary = _payload
	for row in _rows(payload, "corridors"):
		if typeof(row) != TYPE_DICTIONARY:
			continue
		_counts["corridors"] += 1
		_add_marker("corridor", str(row.get("corridor_id", "")), TRADE_CORRIDORS)
	for row in _rows(payload, "locations"):
		if typeof(row) != TYPE_DICTIONARY:
			continue
		var is_major := bool(row.get("is_major", false))
		var trade_post := bool(row.get("trade_post_present", false))
		if trade_post:
			_counts["trade_posts"] += 1
			_add_marker("trade_post", str(row.get("location_id", "")), TRADE_MAJOR_LOCATIONS)
		if is_major:
			_counts["major_locations"] += 1
			_add_marker("major_location", str(row.get("location_id", "")), TRADE_MAJOR_LOCATIONS)
	for row in _rows(payload, "cross_society"):
		if typeof(row) != TYPE_DICTIONARY:
			continue
		var left := str(row.get("society_a_location_id", "none"))
		var right := str(row.get("society_b_location_id", "none"))
		if left == "none" or right == "none" or left == "" or right == "":
			_counts["unresolved_anchors"] += 1
			continue
		_counts["cross_society"] += 1
		_add_marker("cross_society", str(row.get("pair_id", "")), TRADE_CROSS_SOCIETY)
	for row in _rows(payload, "networks"):
		if typeof(row) != TYPE_DICTIONARY:
			continue
		_counts["networks"] += 1
		var sustained := bool(row.get("sustained", false))
		if sustained:
			_counts["sustained"] += 1
		var marker := _add_marker(
			"network", str(row.get("network_id", "")), TRADE_COVERAGE
		)
		marker.set_meta(
			"network_label",
			"%s:%s" % [str(row.get("status", "observed")), "sustained" if sustained else "single"],
		)
	if _counts["corridors"] + _counts["major_locations"] + _counts["cross_society"] + _counts["networks"] == 0:
		status_message = "trade_overlay_empty"


func _add_marker(kind: String, token: String, layer: String) -> Node2D:
	var marker := Node2D.new()
	marker.name = "TradeMarker"
	marker.set_meta("marker_kind", kind)
	marker.set_meta("layer", layer)
	marker.set_meta("evidence_class", evidence_for_layer(layer))
	marker.set_meta("token", token)
	add_child(marker)
	return marker
