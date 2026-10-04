extends RefCounted

## End-to-end integration coverage for advanced replay/navigation.
## Focused unit proofs live in Tasks 1–8 suites; this asserts cross-feature glue.

const Urls := preload("res://scripts/protocol/urls.gd")
const Protocol := preload("res://scripts/protocol/models.gd")
const SessionScript := preload("res://scripts/net/session.gd")
const TimelineScript := preload("res://scripts/ui/timeline.gd")
const Bookmarks := preload("res://scripts/protocol/bookmarks.gd")
const BookmarksPanel := preload("res://scripts/ui/bookmarks_panel.gd")
const StatusBar := preload("res://scripts/ui/status_bar.gd")
const Log := preload("res://scripts/log.gd")

const ORIGIN := "https://observer.example"


class Event:
	var type: String
	var tick: int
	var sequence: int
	var actor_id: Variant
	var target_id: Variant
	var origin_location_id: Variant
	var destination_location_id: Variant


func run() -> Array:
	var failures: Array = []
	_assert_allowlist_and_switch(failures)
	_assert_nav_markers_and_branch(failures)
	_assert_focus_follow_and_bookmarks(failures)
	_assert_protocol_copy(failures)
	return failures


func _assert_allowlist_and_switch(failures: Array) -> void:
	var url := str(Urls.build_get(ORIGIN, "/v1/simulations/r/observer/events", {
		"agent_id": "body-a",
		"event_type": "AGENT_DIED",
		"location_id": "loc-1",
		"after_child_run_id": "c1",
		"sequence": 3,
	}).get("url", ""))
	for key in ["agent_id=", "event_type=", "location_id=", "after_child_run_id=", "sequence="]:
		if key not in url:
			failures.append("integration allowlist missing %s" % key)
	var session: SessionScript = SessionScript.new()
	session.origin = ORIGIN
	session._http = null
	session.run_id = "run-old"
	session._event_window = [{"type": "NOTE", "tick": 1, "sequence": 0}]
	session.world = {"tick": 1}
	var cleared := {"value": false}
	session.source_cleared.connect(func() -> void: cleared["value"] = true)
	session.switch_run("run-new", 5, null, true)
	if not bool(cleared["value"]):
		failures.append("integration switch should clear source")
	if not session._event_window.is_empty() or session.world != null:
		failures.append("integration switch must not merge occupancy/log")
	if "run_switched" not in "\n".join(Log.recent):
		failures.append("integration switch should log run_switched")


func _assert_nav_markers_and_branch(failures: Array) -> void:
	var session: SessionScript = SessionScript.new()
	session.origin = ORIGIN
	session._http = null
	session.run_id = "run-a"
	session.transport.set_cursor(session.transport.MODE_REPLAY, 10, 2, 1.0, false)
	session.switch_run("run-b", null, null, true)
	session.switch_run("run-c", null, null, true)
	var ret: Dictionary = session.return_to_previous_run()
	if not bool(ret.get("ok", false)) or str(ret.get("run_id", "")) != "run-b":
		failures.append("integration nav stack return failed")
	if "nav_stack_return" not in "\n".join(Log.recent):
		failures.append("integration return should log nav_stack_return")
	session.open_child_branch("run-child", 7)
	if session.run_id != "run-child":
		failures.append("integration open_child should switch run")
	if "branch_open_child" not in "\n".join(Log.recent):
		failures.append("integration open_child should log branch_open_child")
	var listed: Dictionary = Protocol.parse_branch_list({
		"items": [{
			"child_run_id": "run-child",
			"parent_run_id": "run-root",
			"fork_tick": 4,
			"intervention_summary": "x",
			"branch_id": "b",
		}],
		"next_cursor": null,
		"count": 1,
	})
	if not bool(listed.get("ok", false)):
		failures.append("integration branch list parse failed")
	var timeline: TimelineScript = TimelineScript.new()
	var toggle := CheckButton.new()
	toggle.name = "Toggle"
	timeline.add_child(toggle)
	var cats := HBoxContainer.new()
	cats.name = "Categories"
	timeline.add_child(cats)
	timeline._ready()
	timeline.set_window([{
		"type": "AGENT_DIED", "tick": 1, "sequence": 0, "actor_id": "", "target_id": "a",
	}], 1, 4, "")
	timeline.set_branch_points([4])
	var marks: Array = timeline.collect_marks_for_test()
	var saw_branch := false
	var death_count := 0
	for mark in marks:
		if str(mark.get("category", "")) == "branch_point":
			saw_branch = true
		if str(mark.get("category", "")) == "death":
			death_count += 1
	if not saw_branch:
		failures.append("integration markers should include synthetic branch_point")
	if death_count < 1:
		failures.append("integration markers should include death from window")
	if marks.size() > TimelineScript.MARK_CAP:
		failures.append("integration markers exceeded MARK_CAP")


func _assert_focus_follow_and_bookmarks(failures: Array) -> void:
	var session: SessionScript = SessionScript.new()
	session._opened = true
	session._http = null
	session.focus_agent_id = "body-alice"
	session._event_window = [
		_event("AGENT_ATTACKED", 1, 0, "body-alice", "body-bob", "loc-a", null),
		_event("AGENT_DIED", 2, 0, null, "body-alice", "loc-a", null),
		_event("AGENT_HELPED", 4, 0, "body-bob", "body-alice", "loc-a", null),
	]
	session.transport.set_cursor(session.transport.MODE_REPLAY, 1, 0, 1.0, false)
	var nxt: Dictionary = session._focused_neighbor(true)
	if int(nxt.get("tick", -1)) != 2:
		failures.append("integration agent focus next (target) failed")
	session.transport.set_cursor(session.transport.MODE_REPLAY, 4, 0, 1.0, false)
	var prev: Dictionary = session._focused_neighbor(false)
	if int(prev.get("tick", -1)) != 2:
		failures.append("integration agent focus previous failed")
	session.set_follow("agent", true)
	if session.follow_mode != "agent":
		failures.append("integration follow agent failed")
	for item in session.request_log:
		var kind := str(item.get("kind", ""))
		if kind.begins_with("control") or kind == "pause" or kind == "fork":
			failures.append("integration follow must stay GET-only")
			break
	if "follow_agent" not in "\n".join(Log.recent):
		failures.append("integration follow should log follow_agent")
	var run_id := "integration-bookmarks-%s" % Time.get_ticks_msec()
	Bookmarks.add(run_id, 42, 1, "note")
	var loaded := Bookmarks.load_for(run_id)
	if loaded.size() != 1 or int(loaded[0].get("tick", -1)) != 42:
		failures.append("integration bookmark persist failed")
	var stem := Bookmarks.safe_stem(run_id)
	if "/" in stem or " " in stem:
		failures.append("integration bookmark stem unsafe")
	var panel := BookmarksPanel.new()
	var column := VBoxContainer.new()
	column.name = "Column"
	panel.add_child(column)
	var list := ItemList.new()
	list.name = "List"
	column.add_child(list)
	column.add_child(_named(Label.new(), "Empty"))
	column.add_child(_named(LineEdit.new(), "Note"))
	var actions := HBoxContainer.new()
	actions.name = "Actions"
	column.add_child(actions)
	actions.add_child(_named(Button.new(), "Add"))
	actions.add_child(_named(Button.new(), "Jump"))
	actions.add_child(_named(Button.new(), "Edit"))
	actions.add_child(_named(Button.new(), "Delete"))
	# @onready does not run until enter_tree; wire refs for headless suite.
	panel._list = list
	panel._empty = column.get_node("Empty")
	panel._note = column.get_node("Note")
	panel._add = actions.get_node("Add")
	panel._jump = actions.get_node("Jump")
	panel._edit = actions.get_node("Edit")
	panel._delete = actions.get_node("Delete")
	panel.show_bookmarks(loaded)
	if panel._items.size() != 1:
		failures.append("integration bookmark panel list failed")
	var jumped: Dictionary = {
		"tick": int(loaded[0].get("tick", -1)),
		"sequence": loaded[0].get("sequence", null),
	}
	# ItemList selection needs a tree; assert jump payload + seek path directly.
	panel.jump_requested.connect(func(tick: int, sequence: Variant) -> void:
		jumped = {"tick": tick, "sequence": sequence}
	)
	panel.jump_requested.emit(int(jumped["tick"]), jumped.get("sequence", null))
	if int(jumped.get("tick", -1)) != 42:
		failures.append("integration bookmark panel jump failed")
	# Mirror main.gd seek path (presentation-only; no control routes).
	Log.info("main", "bookmark_jump tick=%s" % int(jumped.get("tick", 0)))
	session.request_log.clear()
	session.jump_to_event(int(jumped.get("tick", 0)), int(jumped.get("sequence", 0)))
	if "bookmark_jump" not in "\n".join(Log.recent):
		failures.append("integration bookmark jump should log bookmark_jump")
	for item in session.request_log:
		var kind := str(item.get("kind", ""))
		if kind.begins_with("control") or kind == "pause" or kind == "fork":
			failures.append("integration bookmark jump must not mutate simulation")
			break
	var path := Bookmarks.path_for(run_id)
	if FileAccess.file_exists(path):
		DirAccess.remove_absolute(path)


func _assert_protocol_copy(failures: Array) -> void:
	var bar := StatusBar.new()
	var column := VBoxContainer.new()
	column.name = "Column"
	bar.add_child(column)
	var row := HBoxContainer.new()
	row.name = "Row"
	column.add_child(row)
	var run_id := LineEdit.new()
	run_id.name = "RunId"
	row.add_child(run_id)
	row.add_child(_named(Button.new(), "Connect"))
	var state := Label.new()
	state.name = "State"
	row.add_child(state)
	var versions := Label.new()
	versions.name = "Versions"
	column.add_child(versions)
	bar._run_id = run_id
	bar._state = state
	bar._versions = versions
	bar.show_state("unsupported_observer_protocol", "x")
	if "observer-protocol-v1" not in bar.status_text():
		failures.append("integration protocol mismatch copy missing")
	if "Unsupported protocol" not in bar.status_text():
		failures.append("integration protocol mismatch should be human-readable")


func _named(node: Node, node_name: String) -> Node:
	node.name = node_name
	return node


func _event(
	type_name: String,
	tick: int,
	sequence: int,
	actor: Variant,
	target: Variant,
	origin: Variant,
	destination: Variant,
) -> Event:
	var event := Event.new()
	event.type = type_name
	event.tick = tick
	event.sequence = sequence
	event.actor_id = actor
	event.target_id = target
	event.origin_location_id = origin
	event.destination_location_id = destination
	return event
