extends SceneTree

const SUITES: Array[String] = [
	"res://tests/test_regional_travel.gd",
	"res://tests/test_models.gd",
	"res://tests/test_cursor.gd",
	"res://tests/test_urls.gd",
	"res://tests/test_research_ui_link.gd",
	"res://tests/test_playback.gd",
	"res://tests/test_transport.gd",
	"res://tests/test_slots.gd",
	"res://tests/test_session_cursor.gd",
	"res://tests/test_session_switch.gd",
	"res://tests/test_branch_panel.gd",
	"res://tests/test_timeline_markers.gd",
	"res://tests/test_focus_playback.gd",
	"res://tests/test_bookmarks.gd",
	"res://tests/test_status_copy.gd",
	"res://tests/test_advanced_replay_integration.gd",
	"res://tests/test_observer_graphical_controls.gd",
	"res://tests/test_event_log.gd",
	"res://tests/test_reducer.gd",
	"res://tests/test_event_router.gd",
	"res://tests/test_artifact_paint.gd",
	"res://tests/test_structure_paint.gd",
	"res://tests/test_environment_paint.gd",
	"res://tests/test_label_overlay.gd",
	"res://tests/test_evidence_class.gd",
	"res://tests/test_fixture_playback.gd",
	"res://tests/test_v2_mechanics_safety.gd",
	"res://tests/test_motion_path.gd",
	"res://tests/test_web_run_id.gd",
	"res://tests/test_debugger_panel.gd",
	"res://tests/test_debugger_labels.gd",
	"res://tests/test_session_debugger.gd",
]


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var failed := 0
	for path in SUITES:
		var existing_orphans := Node.get_orphan_node_ids()
		var existing_children := root.get_children()
		var script: Script = load(path)
		if script == null:
			print("FAIL %s load" % path)
			failed += 1
			continue
		var suite: RefCounted = script.new()
		var result: Variant = suite.call("run")
		if typeof(result) != TYPE_ARRAY:
			print("FAIL %s suite returned no failures array" % path)
			failed += 1
			continue
		var failures: Array = result
		if failures.is_empty():
			print("PASS %s" % path)
		else:
			failed += failures.size()
			for item in failures:
				print("FAIL %s %s" % [path, item])
		# Each suite owns its fixtures, including detached view/session nodes.
		# Free fixture roots rather than leaking their children and rendering RIDs
		# until engine shutdown. Preserve nodes that predate this suite.
		for child in root.get_children():
			if child not in existing_children:
				child.free()
		for instance_id in Node.get_orphan_node_ids():
			if instance_id in existing_orphans:
				continue
			var orphan := instance_from_id(instance_id) as Node
			if is_instance_valid(orphan) and orphan.get_parent() == null:
				orphan.free()
		suite = null
		await process_frame
	print("godot_protocol_tests failed=%s" % failed)
	quit(1 if failed > 0 else 0)
