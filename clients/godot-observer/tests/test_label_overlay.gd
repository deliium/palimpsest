extends RefCounted

const LabelOverlay := preload("res://scripts/view/label_overlay.gd")
const LocationLayer := preload("res://scripts/view/location_layer.gd")
const Protocol := preload("res://scripts/protocol/models.gd")
const SessionScript := preload("res://scripts/net/session.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _secondary_caption_does_not_replace_objective(), "secondary captions")
	_expect(failures, _wrong_layer_is_ignored(), "wrong layer ignored")
	_expect(failures, _session_requests_labels_route(), "labels route")
	return failures


func _secondary_caption_does_not_replace_objective() -> String:
	var locations := LocationLayer.new()
	var parsed: Protocol.ParseResult = Protocol.parse_frame({
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"cursor": {
			"run_id": "run-labels",
			"mode": "live",
			"tick": 1,
			"protocol_version": Protocol.PROTOCOL_VERSION,
		},
		"world": {
			"tick": 1,
			"revision": 1,
			"locations": [{
				"location_id": "location_17",
				"name": "Northern Forest",
				"display_name": "Northern Forest",
				"neighbor_ids": [],
			}],
			"agents": [],
			"items": [],
			"resources": [],
			"weather": [],
		},
		"events": [],
	})
	if not parsed.ok:
		locations.free()
		return "objective frame should parse"
	locations.show_world(parsed.value.world)
	var overlay := LabelOverlay.new()
	overlay.set_objective_names({"location_17": "Northern Forest"})
	overlay.set_centers({"location_17": Vector2(12, 8)})
	overlay.apply_payload({
		"layer": "subjective_labels",
		"readings": [{
			"objective_id": "location_17",
			"objective_display_name": "Northern Forest",
			"referent_kind": "location",
			"label_token": "dead_a1b2c3d4",
			"label_display": "Dead A1b2c3d4",
			"sense_revision": 0,
			"strength_band": "high",
			"label_source": "agent_perspective",
		}],
	})
	overlay.set_enabled(true)
	if overlay.get_child_count() != 1:
		overlay.free()
		locations.free()
		return "enabled overlay should paint one subjective marker"
	var marker: Node = overlay.get_child(0)
	if str(marker.get_meta("objective_display")) != "Northern Forest":
		overlay.free()
		locations.free()
		return "objective display must remain Northern Forest"
	if str(marker.get_meta("subjective_label")) != "Dead A1b2c3d4":
		overlay.free()
		locations.free()
		return "subjective secondary caption missing"
	if not str(marker.get_meta("copy")).begins_with("~ "):
		overlay.free()
		locations.free()
		return "subjective caption should be marked"
	if overlay.primary_caption("location_17") != "Northern Forest":
		overlay.free()
		locations.free()
		return "primary caption helper must keep researcher identity"
	overlay.free()
	locations.free()
	return ""


func _wrong_layer_is_ignored() -> String:
	var overlay := LabelOverlay.new()
	overlay.set_centers({"location_17": Vector2.ZERO})
	overlay.apply_payload({
		"layer": "subjective_claims",
		"readings": [{
			"objective_id": "location_17",
			"label_display": "Dead A1b2c3d4",
		}],
	})
	overlay.set_enabled(true)
	if overlay.get_child_count() != 0:
		overlay.free()
		return "non-label layer must not paint markers"
	overlay.free()
	return ""


func _session_requests_labels_route() -> String:
	var session := SessionScript.new()
	session.run_id = "run-1"
	session.origin = "http://127.0.0.1:8000"
	session.request_label_overlay("alice")
	var logged_path := str(session.last_request.get("path", ""))
	if "/observer/agents/alice/labels" not in logged_path:
		session.free()
		return "label overlay should request the labels route"
	if "memories" in logged_path or "beliefs" in logged_path:
		session.free()
		return "labels request must not widen to memories/beliefs"
	session.free()
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
