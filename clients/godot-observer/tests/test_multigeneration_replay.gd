extends RefCounted

const TimelineScript := preload("res://scripts/ui/timeline.gd")


class Event:
	var type: String
	var tick: int
	var sequence: int
	var actor_id: Variant
	var target_id: Variant


func run() -> Array:
	var failures: Array = []
	_expect(failures, _eight_marker_timeline(), "eight marker timeline")
	_expect(failures, _generation_and_branch_navigation(), "generation and branch navigation")
	return failures


func _event(type: String, tick: int, actor_id: Variant, target_id: Variant) -> Event:
	var event := Event.new()
	event.type = type
	event.tick = tick
	event.sequence = 0
	event.actor_id = actor_id
	event.target_id = target_id
	return event


func _timeline() -> Control:
	var timeline: Control = TimelineScript.new()
	var toggle := CheckButton.new()
	toggle.name = "Toggle"
	timeline.add_child(toggle)
	var categories := HBoxContainer.new()
	categories.name = "Categories"
	timeline.add_child(categories)
	timeline._ready()
	return timeline


func _eight_marker_timeline() -> String:
	var timeline := _timeline()
	var events: Array = [
		_event("AGENT_CREATED", 2, "body-entrant", null),
		_event("AGENT_DIED", 8, null, "body-founder"),
		_event("STRUCTURE_BUILT", 9, "body-founder", null),
		_event("ARTIFACT_CREATED", 10, "body-founder", null),
	]
	timeline.set_window(events, 0, 16, "")
	var seen := {}
	for mark in timeline.collect_marks_for_test():
		seen[str(mark.get("category", ""))] = true
	for expected in ["birth", "death", "structure_creation", "artifact_creation"]:
		if not seen.has(expected):
			timeline.free()
			return "missing %s marker" % expected
	timeline.free()
	return ""


func _generation_and_branch_navigation() -> String:
	var timeline := _timeline()
	timeline.set_generation_markers([
		{"generation_index": 0, "seek_tick": 0},
		{"generation_index": 1, "seek_tick": 6},
		{"generation_index": 2, "seek_tick": 12},
	])
	if timeline.generation_mark_count() != 3:
		timeline.free()
		return "generation markers missing"
	var events: Array = [_event("AGENT_CREATED", 4, "body-entrant", null)]
	timeline.set_window(events, 0, 16, "")
	timeline.set_branch_points([4, 12])
	var branch_ticks: Array = []
	for mark in timeline.collect_marks_for_test():
		if str(mark.get("category", "")) == "branch_point":
			branch_ticks.append(int(mark.get("tick", -1)))
	if not branch_ticks.has(4) or not branch_ticks.has(12):
		timeline.free()
		return "branch markers missing"
	if timeline.collect_marks_for_test().any(
		func(mark: Dictionary) -> bool:
			return str(mark.get("action", "")) in ["commit", "advance", "mutate"]
	):
		timeline.free()
		return "read-only markers expose mutation actions"
	timeline.free()
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
