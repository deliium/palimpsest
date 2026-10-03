extends RefCounted

const Protocol := preload("res://scripts/protocol/models.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")
const ObjectLayer := preload("res://scripts/view/object_layer.gd")
const SessionScript := preload("res://scripts/net/session.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _frame_paints_from_kind_tokens(), "artifact frame paints from kind")
	_expect(failures, _held_cue_requires_visible_body(), "held cue needs visible body")
	_expect(failures, _artifact_types_are_known(), "artifact semantic types known")
	return failures


func _frame_paints_from_kind_tokens() -> String:
	var parsed: Protocol.ParseResult = Protocol.parse_frame({
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"cursor": {
			"run_id": "run-artifacts",
			"mode": "live",
			"tick": 3,
			"protocol_version": Protocol.PROTOCOL_VERSION,
		},
		"world": {
			"tick": 3,
			"revision": 1,
			"locations": [{
				"location_id": "loc-camp",
				"name": "Camp",
				"display_name": "Camp",
				"neighbor_ids": [],
				"presentation": {
					"screen_position": {"x": 0.0, "y": 0.0},
					"visual_bounds": {"x": -20.0, "y": -20.0, "width": 40.0, "height": 40.0},
					"slot_anchors": [],
					"connection_anchors": [],
				},
			}],
			"agents": [{
				"entity_id": "body-ada",
				"location_id": "loc-camp",
				"life_status": "alive",
				"inventory_ids": [],
				"measures": {
					"health": 1.0,
					"hunger": 0.0,
					"thirst": 0.0,
					"fatigue": 0.0,
					"temperature": 0.0,
				},
				"presentation_slot": {"slot_index": 0, "local_x": -4.0, "local_y": -2.0},
			}],
			"items": [],
			"resources": [],
			"weather": [],
			"artifacts": [
				{
					"artifact_id": "art-sign-1",
					"kind": "sign",
					"author_id": "body-ada",
					"created_tick": 1,
					"content_revision": 0,
					"location_id": "loc-camp",
					"holder_id": null,
					"marks": ["water", "north"],
					"presentation": {
						"visual_category": "artifact",
						"icon_key": "artifact_sign",
						"size_category": "small",
						"display_label": "sign",
					},
				},
				{
					"artifact_id": "art-note-1",
					"kind": "note",
					"author_id": "body-ada",
					"created_tick": 2,
					"content_revision": 1,
					"location_id": null,
					"holder_id": "body-ada",
					"marks": ["memo"],
					"presentation": {
						"visual_category": "artifact",
						"icon_key": "artifact_note",
						"size_category": "small",
						"display_label": "note",
					},
				},
			],
			"artifact_interpretations": [{
				"owner_id": "agent-ada",
				"reading_marks": ["should-not-paint"],
			}],
		},
		"events": [],
	})
	if not parsed.ok:
		return "frame parse %s" % parsed.reason_code
	var world = parsed.value.world
	if world.artifacts.size() != 2:
		return "artifact count"
	if world.get("artifact_interpretations") != null:
		return "interpretation field leaked onto world model"
	var session := SessionScript.new()
	var installed: Array = []
	session.frame_sought.connect(func(frame: Variant, _event: Variant, _forward: bool) -> void:
		installed.append(frame.world)
	)
	session._apply_sought_frame(parsed.value, session._seek_serial)
	if session.world != world or installed.is_empty() or installed[-1] != world:
		session.free()
		return "sought frame did not install the artifact world"
	var layer := ObjectLayer.new()
	layer.show_world(world, {"loc-camp": Vector2(40, 20)})
	var plan: Array = layer.paint_plan()
	layer.free()
	session.free()
	if plan.size() != 2:
		return "paint plan size %s" % plan.size()
	var by_id := {}
	for entry in plan:
		by_id[str(entry["artifact_id"])] = entry
	if not by_id.has("art-sign-1") or not by_id.has("art-note-1"):
		return "missing painted artifact ids"
	var ground: Dictionary = by_id["art-sign-1"]
	if str(ground["placement"]) != "ground" or str(ground["kind"]) != "sign":
		return "ground artifact placement/kind"
	if str(ground["label"]) != "sign" or str(ground["icon"]) != Themes.artifact_icon("sign"):
		return "ground glyph must use kind tokens"
	if ground["color"] != Themes.artifact_color("sign"):
		return "ground color must come from local theme"
	if "water" in str(ground) or "north" in str(ground) or "should-not-paint" in str(ground):
		return "marks or interpretation leaked into paint plan"
	var held: Dictionary = by_id["art-note-1"]
	if str(held["placement"]) != "held" or str(held["holder_id"]) != "body-ada":
		return "held artifact cue"
	if str(held["label"]) != "note" or str(held["icon"]) != Themes.artifact_icon("note"):
		return "held glyph must use kind tokens"
	if held["color"] != Themes.artifact_color("note"):
		return "held color must come from local theme"
	return ""


func _held_cue_requires_visible_body() -> String:
	var parsed: Protocol.ParseResult = Protocol.parse_frame({
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"cursor": {
			"run_id": "run-artifacts",
			"mode": "live",
			"tick": 1,
			"protocol_version": Protocol.PROTOCOL_VERSION,
		},
		"world": {
			"tick": 1,
			"revision": 0,
			"locations": [],
			"agents": [],
			"items": [],
			"resources": [],
			"weather": [],
			"artifacts": [{
				"artifact_id": "art-hidden",
				"kind": "map",
				"author_id": "body-missing",
				"created_tick": 0,
				"content_revision": 0,
				"location_id": null,
				"holder_id": "body-missing",
				"marks": [],
			}],
		},
		"events": [],
	})
	if not parsed.ok:
		return "hidden holder frame parse"
	var layer := ObjectLayer.new()
	layer.show_world(parsed.value.world, {})
	var plan: Array = layer.paint_plan()
	layer.free()
	if not plan.is_empty():
		return "held artifact without visible body should not paint"
	return ""


func _artifact_types_are_known() -> String:
	for type_name in [
		"ARTIFACT_CREATED",
		"ARTIFACT_MODIFIED",
		"ARTIFACT_MOVED",
		"ARTIFACT_DESTROYED",
	]:
		if not Protocol.KNOWN_TYPES.has(type_name):
			return "missing known type %s" % type_name
		var parsed = Protocol.parse_event({
			"protocol_version": Protocol.PROTOCOL_VERSION,
			"type": type_name,
			"domain_kind": type_name.to_lower(),
			"event_id": "evt-%s" % type_name,
			"tick": 1,
			"sequence": 0,
			"artifact_id": "art-1",
		})
		if not parsed.ok or not parsed.value.known:
			return "artifact type should parse as known %s" % type_name
		if parsed.value.artifact_id != "art-1":
			return "artifact_id dropped %s" % type_name
	for type_name in [
		"RESOURCE_HARVESTED",
		"CRAFT_STARTED",
		"ITEM_CRAFTED",
		"STRUCTURE_BUILT",
		"STRUCTURE_REPAIRED",
		"ITEM_STORED",
	]:
		if Protocol.KNOWN_TYPES.has(type_name):
			return "production type must stay unknown %s" % type_name
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
