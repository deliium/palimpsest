extends RefCounted

const PanelScene := preload("res://scenes/ui/generational_panel.tscn")
const Demographics := preload("res://scripts/protocol/demographics.gd")
const Lineage := preload("res://scripts/protocol/lineage.gd")
const TimelineScript := preload("res://scripts/ui/timeline.gd")
const BASE := "res://fixtures/protocol/generational/"


func run() -> Array:
	var failures: Array = []
	_expect(failures, _panel_totals(), "panel totals")
	_expect(failures, _participant_groups(), "participant groups")
	_expect(failures, _generation_timeline(), "generation timeline")
	return failures


func _load(name: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(BASE + name))


func _panel_totals() -> String:
	var parsed: Dictionary = Demographics.parse_demographics(_load("demographics_agents.json"))
	if not bool(parsed.get("ok", false)):
		return "fixture parse failed"
	var panel: PanelContainer = PanelScene.instantiate()
	var tree := Engine.get_main_loop() as SceneTree
	tree.root.add_child(panel)
	panel.apply_demographics(parsed["value"])
	var summary := str(panel.get_node("Column/Summary").text)
	if not summary.contains("living 2") or not summary.contains("admitted 3"):
		return "exact totals missing"
	var status := str(panel.get_node("Column/Status").text)
	if not status.contains("OBJECTIVE"):
		return "objective chrome missing"
	var list: ItemList = panel.get_node("Column/Agents")
	if list.item_count != 2:
		return "agent rows missing"
	panel.apply_lineage("participants", {
		"status": "available",
		"evidence_class": "subjective",
		"owner_id": "agent-founder",
		"role": "learner",
		"items": [
			{"teacher_id": "t", "learner_id": "l", "content_kind": "skill", "learning_state": "attempt_only", "learning_evidence_count": 0, "attempt_count": 2},
			{"teacher_id": "t", "learner_id": "l", "content_kind": "skill", "learning_state": "learning_evidence", "learning_evidence_count": 1, "attempt_count": 1},
		],
		"scan_limited": true,
	})
	var body := str(panel.get_node("Column/LineageBody").text)
	if not body.contains("attempt-only 1") or not body.contains("scan limited"):
		return "participant grouping/scan state missing"
	panel.free()
	return ""


func _participant_groups() -> String:
	var parsed: Dictionary = Lineage.parse_participants(_load("lineage_participants.json"))
	if not bool(parsed.get("ok", false)):
		return "participant fixture parse failed"
	var card = parsed["value"].items[0]
	if card.learning_state != "learning_evidence":
		return "learning evidence state missing"
	if card.owner_id != "agent-founder":
		return "owner provenance lost"
	return ""


func _generation_timeline() -> String:
	var timeline: Control = TimelineScript.new()
	var toggle := CheckButton.new()
	toggle.name = "Toggle"
	timeline.add_child(toggle)
	var categories := HBoxContainer.new()
	categories.name = "Categories"
	timeline.add_child(categories)
	timeline._ready()
	timeline.set_generation_markers([
		{"generation_index": 0, "seek_tick": 0},
		{"generation_index": 1, "seek_tick": 6},
	])
	if timeline.generation_mark_count() != 2:
		return "generation markers missing"
	var marks: Array = timeline.collect_marks_for_test()
	var found := false
	for mark in marks:
		if str(mark.get("category", "")) == "generation" and int(mark.get("tick", -1)) == 6:
			found = true
			if not bool(mark.get("seek_tick_start", false)):
				return "generation marker must seek a full boundary"
	if not found:
		return "generation mark not collected"
	var emitted: Array = []
	timeline.generation_seek_requested.connect(func(tick: int) -> void: emitted.append(tick))
	timeline.set_category_enabled("generation", false)
	if timeline.collect_marks_for_test().any(func(mark: Dictionary) -> bool: return str(mark.get("category", "")) == "generation"):
		return "disabled generation markers still drawn"
	timeline.free()
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
