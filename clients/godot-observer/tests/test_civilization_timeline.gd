extends RefCounted

const UiScene := preload("res://scenes/ui/ui_layer.tscn")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _packed_scene(), "packed scene")
	_expect(failures, _timeline_flow(), "timeline flow")
	_expect(failures, _bounds_and_gaps(), "bounds and gaps")
	_expect(failures, _owner_and_recorded_clear(), "owner and recorded clearing")
	return failures


func _packed_scene() -> String:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	var ui: CanvasLayer = UiScene.instantiate()
	tree.root.add_child(ui)
	var timeline = ui.get_node_or_null("CivilizationTimeline")
	if timeline == null:
		ui.free()
		return "civilization timeline node missing"
	if timeline.get_script() == null or not str(timeline.get_script().resource_path).ends_with("civilization_timeline.gd"):
		ui.free()
		return "civilization timeline script missing"
	for signal_name in ["seek_requested", "marker_window_requested", "catalogue_requested", "recorded_mode_changed"]:
		if not timeline.has_signal(signal_name):
			ui.free()
			return "timeline signal missing %s" % signal_name
	var legacy = ui.get_node_or_null("Timeline")
	if legacy == null or not legacy.has_signal("generation_seek_requested"):
		ui.free()
		return "existing generation timeline lost"
	if not ui.has_signal("civilization_timeline_seek_requested"):
		ui.free()
		return "ui routing signal missing"
	ui.free()
	return ""


func _marker(
	marker_id: String,
	marker_type: String,
	seek: int,
	evidence: String,
	owner: Variant,
	layer: String,
) -> Dictionary:
	return {
		"marker_id": marker_id,
		"marker_type": marker_type,
		"seek_boundary": seek,
		"evidence_class": evidence,
		"owner_id": owner,
		"layer": layer,
		"row_id": "row:%s" % marker_id,
		"source_refs": [],
		"coverage": {"state": "complete", "reason": null, "missing_intervals": []},
	}


func _marker_state(
	key: String,
	evidence: String,
	owner: Variant,
	start: int,
	end: int,
	markers: Array,
	next_cursor: Variant = null,
	pages: int = 1,
	gaps: Array = [],
) -> Dictionary:
	return {
		"status": "available",
		"reason_code": null,
		"evidence_class": evidence,
		"owner_id": owner,
		"layer": "",
		"markers": markers,
		"missing_intervals": gaps,
		"requested_window": {"start_tick": start, "end_tick": end},
		"next_cursor": next_cursor,
		"truncated": next_cursor != null,
		"pages": pages,
		"window_key": key,
	}


func _timeline_flow() -> String:
	var tree := Engine.get_main_loop() as SceneTree
	var ui: CanvasLayer = UiScene.instantiate()
	tree.root.add_child(ui)
	var timeline = ui.get_node("CivilizationTimeline")
	var catalogue_requests: Array = []
	var window_requests: Array = []
	var seeks: Array = []
	timeline.catalogue_requested.connect(func(evidence: String, owner: String) -> void:
		catalogue_requests.append({"evidence": evidence, "owner": owner})
	)
	timeline.marker_window_requested.connect(
		func(from_tick: int, to_tick: int, evidence: String, owner: String, layer: String) -> void:
			window_requests.append({"from": from_tick, "to": to_tick, "evidence": evidence, "owner": owner, "layer": layer})
	)
	timeline.seek_requested.connect(func(tick: int) -> void: seeks.append(tick))
	timeline.set_context("run-capture", "agent-a", true, true)
	timeline.set_span(2, 12)
	timeline.refresh()
	if catalogue_requests.size() != 1 or str(catalogue_requests[0]["evidence"]) != "ANALYTICAL":
		ui.free()
		return "catalogue request missing"
	var evidence_seen := {}
	for request in window_requests:
		evidence_seen[str(request["evidence"])] = true
	for needed in ["OBJECTIVE", "ANALYTICAL", "SUBJECTIVE"]:
		if not evidence_seen.has(needed):
			ui.free()
			return "marker window missing %s" % needed
	timeline.apply_catalogue({
		"status": "available",
		"evidence_class": "ANALYTICAL",
		"owner_id": null,
		"boundaries": [{"boundary_tick": 4}, {"boundary_tick": 6}],
		"next_cursor": null,
		"truncated": false,
		"pages": 1,
	})
	if not timeline.recorded_available() or timeline.catalogue_boundary_count() != 2:
		ui.free()
		return "recorded catalogue boundaries missing"
	timeline.apply_markers(_marker_state(
		"objective",
		"OBJECTIVE",
		null,
		2,
		12,
		[_marker("m-journey", "journey_arrived", 4, "OBJECTIVE", null, "migration")],
	))
	timeline.apply_markers(_marker_state(
		"subjective",
		"SUBJECTIVE",
		"agent-a",
		2,
		12,
		[_marker("m-tech", "technology_acquired", 6, "SUBJECTIVE", "agent-a", "technology")],
	))
	if timeline.marker_count() != 2:
		ui.free()
		return "merged marker count wrong"
	var tracks: Dictionary = timeline.tracks_for_test()
	if int(tracks.get("movement", 0)) != 1 or int(tracks.get("knowledge", 0)) != 1:
		ui.free()
		return "marker tracks missing"
	var marks: Array = timeline.collect_marks_for_test()
	var tech: Dictionary = marks[1]
	if str(tech.get("owner_id", "")) != "agent-a":
		ui.free()
		return "subjective owner badge missing"
	var point: Vector2 = timeline._position_for(tech, timeline._span())
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.position = point
	timeline._gui_input(event)
	if seeks.size() != 1 or int(seeks[0]) != 6:
		ui.free()
		return "marker click did not seek its post-event boundary"
	ui.free()
	return ""


func _bounds_and_gaps() -> String:
	var tree := Engine.get_main_loop() as SceneTree
	var ui: CanvasLayer = UiScene.instantiate()
	tree.root.add_child(ui)
	var timeline = ui.get_node("CivilizationTimeline")
	timeline.set_context("run-capture", "agent-a", true, true)
	var many: Array = []
	for index in range(250):
		many.append(_marker(
			"m-%04d" % index,
			"settlement_activated",
			index + 1,
			"ANALYTICAL",
			null,
			"settlements",
		))
	timeline.apply_markers(_marker_state("many", "ANALYTICAL", null, 0, 300, many, "next-page", 1))
	if timeline.marker_count() != 200 or not timeline.truncated():
		ui.free()
		return "displayed marker cap missing"
	if not timeline.load_more_enabled():
		ui.free()
		return "sparse continuation did not enable load more"
	timeline.apply_markers(_marker_state(
		"gaps",
		"ANALYTICAL",
		null,
		0,
		300,
		[],
		null,
		1,
		[{"start_tick": 10, "end_tick": 12}],
	))
	if timeline.gap_count() != 1:
		ui.free()
		return "missing interval not disclosed"
	if timeline.marker_count() != 200:
		ui.free()
		return "missing span fabricated a transition"
	ui.free()
	return ""


func _owner_and_recorded_clear() -> String:
	var tree := Engine.get_main_loop() as SceneTree
	var ui: CanvasLayer = UiScene.instantiate()
	tree.root.add_child(ui)
	var timeline = ui.get_node("CivilizationTimeline")
	var mode_changes: Array = []
	timeline.recorded_mode_changed.connect(func(enabled: bool) -> void: mode_changes.append(enabled))
	timeline.set_context("run-capture", "agent-a", true, true)
	timeline.apply_markers(_marker_state(
		"objective",
		"OBJECTIVE",
		null,
		0,
		10,
		[_marker("m-journey", "journey_arrived", 4, "OBJECTIVE", null, "migration")],
	))
	timeline.apply_markers(_marker_state(
		"subjective",
		"SUBJECTIVE",
		"agent-a",
		0,
		10,
		[_marker("m-tech", "technology_acquired", 6, "SUBJECTIVE", "agent-a", "technology")],
	))
	if timeline.marker_count() != 2:
		ui.free()
		return "owner fixture markers missing"
	timeline.set_context("run-capture", "agent-b", true, true)
	if timeline.marker_count() != 1:
		ui.free()
		return "owner change did not clear private markers"
	timeline.apply_catalogue({
		"status": "available",
		"evidence_class": "ANALYTICAL",
		"owner_id": null,
		"boundaries": [{"boundary_tick": 4}],
		"next_cursor": null,
		"truncated": false,
		"pages": 1,
	})
	timeline._recorded_button.button_pressed = true
	if mode_changes.is_empty() or int(mode_changes.back()) != 1 or not timeline.recorded_mode_enabled():
		ui.free()
		return "recorded boundary mode did not enable"
	timeline.apply_catalogue({
		"status": "available",
		"evidence_class": "ANALYTICAL",
		"owner_id": null,
		"boundaries": [],
		"next_cursor": null,
		"truncated": false,
		"pages": 1,
	})
	if timeline.recorded_available() or timeline.recorded_mode_enabled():
		ui.free()
		return "empty catalogue left recorded mode enabled"
	if mode_changes.is_empty() or int(mode_changes.back()) != 0:
		ui.free()
		return "empty catalogue did not disable recorded mode"
	timeline.clear_private()
	if timeline.marker_count() != 1:
		ui.free()
		return "debug revocation removed objective markers"
	ui.free()
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
