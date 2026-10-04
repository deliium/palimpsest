extends RefCounted

const TimelineScript := preload("res://scripts/ui/timeline.gd")
const Log := preload("res://scripts/log.gd")


class Event:
	var type: String
	var tick: int
	var sequence: int
	var actor_id: Variant
	var target_id: Variant


func run() -> Array:
	var failures: Array = []
	var timeline: TimelineScript = TimelineScript.new()
	var toggle := CheckButton.new()
	toggle.name = "Toggle"
	timeline.add_child(toggle)
	var categories := HBoxContainer.new()
	categories.name = "Categories"
	timeline.add_child(categories)
	timeline._ready()
	var events: Array = []
	events.append(_event("AGENT_DIED", 1, 0, null, "body-a"))
	events.append(_event("AGENT_ATTACKED", 2, 0, "body-a", "body-b"))
	events.append(_event("WEATHER_CHANGED", 3, 0, null, null))
	events.append(_event("ARTIFACT_CREATED", 4, 0, "body-a", null))
	events.append(_event("STRUCTURE_BUILT", 5, 0, "body-a", null))
	events.append(_event("NEEDS_APPLIED", 6, 0, null, "body-a"))
	timeline.set_window(events, 3, 10, "body-a")
	var marks: Array = timeline.collect_marks_for_test()
	var categories_seen := {}
	for mark in marks:
		categories_seen[str(mark.get("category", ""))] = true
	for needed in ["death", "attack", "weather_environment", "artifact_creation", "structure_creation"]:
		if not categories_seen.has(needed):
			failures.append("missing category mark %s" % needed)
	if categories_seen.has("birth"):
		failures.append("birth marks must not be invented")
	timeline.set_category_enabled("attack", false)
	marks = timeline.collect_marks_for_test()
	for mark in marks:
		if str(mark.get("category", "")) == "attack":
			failures.append("disabled attack category still drawn")
			break
	timeline.set_branch_points([7, 8])
	marks = timeline.collect_marks_for_test()
	var branch_count := 0
	for mark in marks:
		if str(mark.get("category", "")) == "branch_point":
			branch_count += 1
			if not bool(mark.get("seek_tick_start", false)):
				failures.append("branch_point should seek tick-start")
	if branch_count < 2:
		failures.append("branch_point marks missing")
	var many: Array = []
	for index in 80:
		many.append(_event("AGENT_DIED", index, 0, null, "body-a"))
	timeline.set_window(many, 0, 80, "")
	marks = timeline.collect_marks_for_test()
	if marks.size() > TimelineScript.MARK_CAP:
		failures.append("marks should cap at %s" % TimelineScript.MARK_CAP)
	if "truncated=true" not in "\n".join(Log.recent):
		failures.append("truncation should log truncated=true")
	var types: Array = timeline.enabled_enrichment_types(3)
	if types.size() > 3:
		failures.append("enrichment type budget exceeded")
	return failures


func _event(type_name: String, tick: int, sequence: int, actor: Variant, target: Variant) -> Event:
	var event := Event.new()
	event.type = type_name
	event.tick = tick
	event.sequence = sequence
	event.actor_id = actor
	event.target_id = target
	return event
