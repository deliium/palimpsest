extends RefCounted

const Protocol := preload("res://scripts/protocol/models.gd")
const StatusBar := preload("res://scripts/ui/status_bar.gd")

const _ENVIRONMENT_TYPES: Array[String] = [
	"SEASON_CHANGED",
	"TEMPERATURE_BAND_CHANGED",
	"RESOURCE_NODE_DEPLETED",
	"RESOURCE_NODE_RECOVERED",
	"ENVIRONMENTAL_HAZARD_STARTED",
	"ENVIRONMENTAL_HAZARD_ENDED",
]

const _ARTIFACT_TYPES: Array[String] = [
	"ARTIFACT_CREATED",
	"ARTIFACT_MODIFIED",
	"ARTIFACT_MOVED",
	"ARTIFACT_DESTROYED",
]

const _LIFECYCLE_TYPES: Array[String] = [
	"AGENT_CREATED",
	"AGENT_ENTERED_WORLD",
	"LIFECYCLE_STAGE_CHANGED",
]


func run() -> Array:
	var failures: Array = []
	_expect(failures, _every_semantic_fixture(), "semantic fixtures parse")
	_expect(failures, _production_optional_fields(), "production optional fields parse")
	_expect(failures, _reference_frame(), "reference frame parses")
	_expect(failures, _unknown_event(), "unknown event is structured")
	_expect(failures, _rejects_foreign_protocol(), "foreign protocol is rejected")
	_expect(failures, _rejects_catalog_anchor_dict(), "catalog anchor dict is rejected")
	_expect(failures, _status_shows_versions_and_protocol_failure(), "status shows protocol failure")
	_expect(failures, _manifest_branch_lineage_optional(), "manifest branch lineage optional")
	_expect(failures, _branch_list_and_fork_point(), "branch list and fork-point parse")
	return failures


func _branch_list_and_fork_point() -> String:
	var listed: Dictionary = Protocol.parse_branch_list({
		"items": [
			{
				"child_run_id": "run-child",
				"parent_run_id": "run-root",
				"fork_tick": 9,
				"intervention_summary": "seed:abcd",
				"branch_id": "b1",
				"future_field": true,
			},
		],
		"next_cursor": "run-child",
		"count": 1,
	})
	if not bool(listed.get("ok", false)):
		return "branch list parse failed"
	var items: Array = listed.get("items", [])
	if items.size() != 1 or str(items[0].get("child_run_id", "")) != "run-child":
		return "branch list item missing"
	if str(listed.get("next_cursor", "")) != "run-child":
		return "branch next_cursor missing"
	var bad: Dictionary = Protocol.parse_branch_list("nope")
	if bool(bad.get("ok", false)):
		return "invalid branch list should fail"
	var fork: Dictionary = Protocol.parse_branch_fork_point({
		"parent_run_id": "run-root",
		"child_run_id": "run-child",
		"fork_tick": 9,
		"parent_observer_tick": 9,
		"child_observer_tick": 9,
		"ignored": 1,
	})
	if not bool(fork.get("ok", false)):
		return "fork point parse failed"
	if str(fork.get("parent_run_id", "")) != "run-root":
		return "fork parent missing"
	if int(fork.get("parent_observer_tick", -1)) != 9:
		return "parent_observer_tick missing"
	var rootish: Dictionary = Protocol.parse_branch_fork_point({"child_run_id": "x"})
	if bool(rootish.get("ok", false)) or str(rootish.get("reason_code", "")) != "branch_root":
		return "empty parent should be branch_root"
	return ""


func _manifest_branch_lineage_optional() -> String:
	var root = Protocol.parse_manifest({
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"layout_schema_version": "observer-layout-v1",
		"layout_id": "reference-v1",
		"layout_hash": "abc",
		"ordering": "tick_sequence",
		"read_only": true,
		"event_types": [],
		"event_schema_version": 5,
		"projector_version": "projector-v1",
		"run_id": "run-root",
		"unknown_future_key": "ignored",
	})
	if not root.ok:
		return "root manifest failed"
	if str(root.value.run_id) != "run-root":
		return "root run_id missing"
	if not str(root.value.parent_run_id).is_empty():
		return "root should omit parent"
	var fork = Protocol.parse_manifest({
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"layout_schema_version": "observer-layout-v1",
		"layout_id": "reference-v1",
		"layout_hash": "abc",
		"ordering": "tick_sequence",
		"read_only": true,
		"event_types": [],
		"event_schema_version": 5,
		"projector_version": "projector-v1",
		"run_id": "run-child",
		"parent_run_id": "run-root",
		"fork_tick": 3,
		"intervention_summary": "mortality_disabled:aaaaaaaaaaaa",
		"branch_id": "branch-1",
	})
	if not fork.ok:
		return "fork manifest failed"
	if str(fork.value.parent_run_id) != "run-root":
		return "fork parent missing"
	if int(fork.value.fork_tick) != 3:
		return "fork tick missing"
	if str(fork.value.branch_id) != "branch-1":
		return "branch_id missing"
	return ""


func _every_semantic_fixture() -> String:
	for type_name in Protocol.KNOWN_TYPES:
		if type_name in _ENVIRONMENT_TYPES or type_name in _ARTIFACT_TYPES or type_name in _LIFECYCLE_TYPES:
			continue
		var path := "res://fixtures/protocol/events/%s.json" % type_name
		var parsed = Protocol.parse_text("event", FileAccess.get_file_as_string(path))
		if parsed == null or not parsed.ok:
			return "event fixture failed %s" % type_name
		if not parsed.value.known or parsed.value.type != type_name:
			return "event fixture mismatch %s" % type_name
		if parsed.value.protocol_version != Protocol.PROTOCOL_VERSION:
			return "event protocol mismatch %s" % type_name
	for type_name in _ARTIFACT_TYPES:
		var parsed_artifact = Protocol.parse_event({
			"protocol_version": Protocol.PROTOCOL_VERSION,
			"type": type_name,
			"event_id": "evt-%s" % type_name,
			"tick": 1,
			"sequence": 0,
			"artifact_id": "art-1",
		})
		if not parsed_artifact.ok or not parsed_artifact.value.known:
			return "artifact type should be known %s" % type_name
	for type_name in _LIFECYCLE_TYPES:
		var parsed_lifecycle = Protocol.parse_event({
			"protocol_version": Protocol.PROTOCOL_VERSION,
			"type": type_name,
			"event_id": "evt-%s" % type_name,
			"tick": 1,
			"sequence": 0,
			"target_id": "body-1",
		})
		if not parsed_lifecycle.ok or not parsed_lifecycle.value.known:
			return "lifecycle type should be known %s" % type_name
	return ""


func _production_optional_fields() -> String:
	var crafted = Protocol.parse_text(
		"event",
		FileAccess.get_file_as_string("res://fixtures/protocol/events/ITEM_CRAFTED.json")
	)
	if not crafted.ok or crafted.value.recipe_id != "recipe-axe":
		return "recipe_id missing on ITEM_CRAFTED"
	if crafted.value.item_id != "item-axe":
		return "item_id missing on ITEM_CRAFTED"
	var built = Protocol.parse_text(
		"event",
		FileAccess.get_file_as_string("res://fixtures/protocol/events/STRUCTURE_BUILT.json")
	)
	if not built.ok or built.value.structure_id != "struct-shelter-1":
		return "structure_id missing on STRUCTURE_BUILT"
	var with_band = Protocol.parse_event({
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"type": "AGENT_TALKED",
		"domain_kind": "talk",
		"event_id": "evt-talk-band",
		"tick": 1,
		"sequence": 0,
		"actor_id": "body-ada",
		"target_id": "body-bo",
		"declared_confidence_band": "medium",
	})
	if not with_band.ok or with_band.value.declared_confidence_band != "medium":
		return "declared_confidence_band missing"
	return ""


func _reference_frame() -> String:
	var text := FileAccess.get_file_as_string("res://fixtures/protocol/reference_frame.json")
	var parsed = Protocol.parse_text("frame", text)
	if not parsed.ok:
		return "frame parse %s" % parsed.reason_code
	var frame = parsed.value
	if not frame.events_are_folded_history:
		return "folded history flag"
	if frame.cursor.after_tick != null or frame.cursor.after_sequence != null:
		return "null resume cursor was filled"
	if frame.cursor.sequence != null:
		return "sequence was not null"
	if frame.world.locations.size() != 4:
		return "location count"
	var expected := ["loc-camp", "loc-spring", "loc-grove", "loc-ridge"]
	for index in expected.size():
		if frame.world.locations[index].location_id != expected[index]:
			return "location order"
	var camp = frame.world.locations[0]
	var anchors: Array = camp.presentation.connection_anchors
	if anchors.is_empty() or anchors[0][0] != "loc-spring":
		return "wire connection anchor"
	if not is_equal_approx(float(anchors[0][1].y), -28.0):
		return "anchor y was negated"
	var spring = frame.world.locations[1]
	if not is_equal_approx(spring.presentation.screen_position.y, -80.0):
		return "spring y was negated"
	if frame.events.is_empty():
		return "folded events missing"
	if frame.world.agents[0].location_id != frame.events[0].destination_location_id:
		return "folded move was not already in world"
	if frame.world.structures.size() != 1:
		return "structure count"
	var structure = frame.world.structures[0]
	if structure.structure_id != "struct-shelter-1":
		return "structure id"
	if structure.location_id != "loc-camp":
		return "structure location"
	if structure.kind != "shelter":
		return "structure kind"
	if not is_equal_approx(structure.integrity, 1.0):
		return "structure integrity"
	if structure.stored_quantity != 2:
		return "structure stored_quantity"
	if structure.presentation == null or structure.presentation.icon_key != "shelter":
		return "structure presentation"
	return ""


func _unknown_event() -> String:
	var parsed = Protocol.parse_event({
		"type": "RESOURCE_FOUND",
		"event_id": "evt-unknown",
		"tick": 4,
		"sequence": 0,
	})
	if not parsed.ok or parsed.value.known:
		return "unknown event raised or was marked known"
	if parsed.value.type != "RESOURCE_FOUND":
		return "unknown type dropped"
	return ""


func _rejects_foreign_protocol() -> String:
	var event = Protocol.parse_event({
		"protocol_version": "observer-protocol-v0",
		"type": "AGENT_MOVED",
		"domain_kind": "move",
		"event_id": "evt-bad",
		"tick": 1,
		"sequence": 0,
	})
	if event.ok or event.reason_code != "unsupported_observer_protocol":
		return "known event protocol"
	var frame = Protocol.parse_frame({"world": {}})
	if frame.ok or frame.reason_code != "unsupported_observer_protocol":
		return "missing frame protocol"
	var manifest = Protocol.parse_manifest({"layout_id": "reference-v1"})
	if manifest.ok or manifest.reason_code != "unsupported_observer_protocol":
		return "missing manifest protocol"
	return ""


func _rejects_catalog_anchor_dict() -> String:
	var parsed = Protocol.parse_frame({
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"cursor": {
			"run_id": "run-1",
			"mode": "live",
			"tick": 0,
			"protocol_version": Protocol.PROTOCOL_VERSION,
			"sequence": null,
			"after_tick": null,
			"after_sequence": null,
		},
		"world": {
			"tick": 0,
			"revision": 0,
			"locations": [{
				"location_id": "loc-camp",
				"name": "Camp",
				"display_name": "Camp",
				"neighbor_ids": ["loc-spring"],
				"presentation": {
					"connection_anchors": {"loc-spring": {"x": 0.0, "y": -28.0}},
				},
			}],
		},
	})
	if parsed.ok or parsed.reason_code != "invalid_connection_anchors":
		return "dict anchors parsed as wire shape"
	return ""


func _status_shows_versions_and_protocol_failure() -> String:
	var event = Protocol.parse_event({
		"protocol_version": "observer-protocol-v0",
		"type": "AGENT_MOVED",
		"domain_kind": "move",
		"event_id": "evt-bad",
		"tick": 1,
		"sequence": 0,
	})
	var frame = Protocol.parse_frame({"world": {}})
	var manifest = Protocol.parse_manifest({"layout_id": "reference-v1"})
	if event.ok or frame.ok or manifest.ok:
		return "payload was applied"
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	var bar: StatusBar = load("res://scenes/ui/status_bar.tscn").instantiate() as StatusBar
	if bar == null:
		return "status bar missing"
	tree.root.add_child(bar)
	var lines := preload("res://scripts/net/version_client.gd").local_lines()
	if str(lines["protocol_version"]) != Protocol.PROTOCOL_VERSION:
		bar.queue_free()
		return "local protocol constant"
	if str(lines["export_engine"]) != "4.7.2-stable":
		bar.queue_free()
		return "local export engine"
	if str(lines["revision"]) != "unknown":
		bar.queue_free()
		return "local revision"
	bar.show_state(event.reason_code, event.reason_code)
	var text := bar.status_text()
	bar.show_state(frame.reason_code, frame.reason_code)
	text = bar.status_text()
	bar.show_state(manifest.reason_code, manifest.reason_code)
	text = bar.status_text()
	bar.queue_free()
	if "observer-protocol-v1" not in text:
		return "status missing protocol"
	if "4.7.2-stable" not in text:
		return "status missing export engine"
	if "revision unknown" not in text:
		return "status missing revision"
	if "unsupported_observer_protocol" not in text:
		return "status missing protocol failure"
	var logged := "\n".join(preload("res://scripts/log.gd").recent)
	if "version_loaded application=" not in logged:
		return "version_loaded missing"
	if "protocol=observer-protocol-v1" not in logged:
		return "version_loaded protocol"
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
