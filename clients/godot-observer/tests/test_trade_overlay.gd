extends RefCounted

const TradeOverlay := preload("res://scripts/view/trade_overlay.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _layers(), "trade overlay layers")
	_expect(failures, _corridors(), "trade corridor layer")
	_expect(failures, _major_locations(), "trade major location markers")
	_expect(failures, _cross_society(), "trade cross-society anchors")
	_expect(failures, _networks(), "trade network status")
	_expect(failures, _trade_post(), "trade post marker")
	_expect(failures, _forbidden(), "trade forbidden payload")
	_expect(failures, _empty(), "trade empty snapshot")
	_expect(failures, _window_selection(), "trade window selection")
	return failures


func _payload() -> Dictionary:
	return {
		"corridors": [
			{"corridor_id": "trd-cor-0000000000000001", "from_location_id": "loc-a", "to_location_id": "loc-b"},
			{"corridor_id": "trd-cor-0000000000000002", "from_location_id": "loc-b", "to_location_id": "loc-a"},
		],
		"locations": [
			{
				"location_id": "loc-b",
				"is_major": true,
				"trade_post_present": true,
			},
			{
				"location_id": "loc-a",
				"is_major": false,
				"trade_post_present": false,
			},
		],
		"cross_society": [
			{
				"pair_id": "trd-pair-0000000000000001",
				"society_a_location_id": "loc-a",
				"society_b_location_id": "loc-b",
			},
			{
				"pair_id": "trd-pair-0000000000000002",
				"society_a_location_id": "none",
				"society_b_location_id": "loc-b",
			},
		],
		"networks": [
			{
				"network_id": "trd-net-0000000000000001",
				"status": "continued",
				"sustained": true,
				"rerouted": false,
			}
		],
	}


func _layers() -> String:
	for layer in [
		"trade_corridors",
		"trade_major_locations",
		"trade_cross_society",
		"trade_coverage",
	]:
		if TradeOverlay.evidence_for_layer(layer) != EvidenceClass.ANALYTICAL:
			return "trade layers must be analytical"
	if TradeOverlay.evidence_for_layer("unknown") != "":
		return "unknown layer must stay empty"
	return ""


func _corridors() -> String:
	var overlay = TradeOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload(_payload(), "trade_corridors")
	var counts: Dictionary = overlay.layer_counts()
	overlay.free()
	if counts["corridors"] != 2:
		return "two corridor markers"
	return ""


func _major_locations() -> String:
	var overlay = TradeOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload(_payload(), "trade_major_locations")
	var counts: Dictionary = overlay.layer_counts()
	overlay.free()
	if counts["major_locations"] != 1:
		return "one major location"
	return ""


func _cross_society() -> String:
	var overlay = TradeOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload(_payload(), "trade_cross_society")
	var counts: Dictionary = overlay.layer_counts()
	overlay.free()
	if counts["cross_society"] != 1:
		return "one resolved cross-society pair"
	if counts["unresolved_anchors"] != 1:
		return "unresolved anchor must be counted"
	return ""


func _networks() -> String:
	var overlay = TradeOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload(_payload(), "trade_coverage")
	var labels: Array = overlay.network_labels()
	var counts: Dictionary = overlay.layer_counts()
	overlay.free()
	if counts["sustained"] != 1:
		return "sustained network count"
	if labels.is_empty() or not str(labels[0]).contains("sustained"):
		return "sustained network label"
	return ""


func _trade_post() -> String:
	var overlay = TradeOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload(_payload(), "trade_major_locations")
	var kinds: Array = overlay.marker_kinds()
	var counts: Dictionary = overlay.layer_counts()
	overlay.free()
	if counts["trade_posts"] != 1:
		return "trade post count"
	if not kinds.has("trade_post") or not kinds.has("major_location"):
		return "trade post marker must be distinct"
	return ""


func _forbidden() -> String:
	var overlay = TradeOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload({"corridors": [{"price": 1}]}, "trade_corridors")
	if overlay.last_rejection != "forbidden_field":
		overlay.free()
		return "forbidden payload rejected"
	if overlay.get_child_count() != 0:
		overlay.free()
		return "forbidden payload must not render"
	overlay.free()
	return ""


func _empty() -> String:
	var overlay = TradeOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload({}, "trade_corridors")
	if overlay.status_message != "trade_overlay_empty":
		overlay.free()
		return "empty snapshot status"
	if overlay.get_child_count() != 0:
		overlay.free()
		return "empty snapshot no-op"
	overlay.free()
	return ""


func _window_selection() -> String:
	var overlay = TradeOverlay.new()
	overlay.set_window_index(3)
	if overlay.selected_window() != 3:
		overlay.free()
		return "window selection"
	overlay.set_window_index(-5)
	if overlay.selected_window() != -1:
		overlay.free()
		return "negative window clears selection"
	overlay.free()
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
