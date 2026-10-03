extends RefCounted

const DebuggerPanel := preload("res://scripts/ui/debugger_panel.gd")
const DebuggerLabels := preload("res://scripts/presentation/debugger_labels.gd")
const Log := preload("res://scripts/log.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _render_and_focus(), "render focus")
	_expect(failures, _compact_and_expand(), "compact expand")
	_expect(failures, _unavailable(), "unavailable")
	return failures


func _sample_payload() -> Dictionary:
	return {
		"availability": "available",
		"ambiguity": false,
		"reason_code": "",
		"address": {
			"tick": 1832,
			"sequence": 17,
			"event_id": "evt-attack",
			"agent_id": "alice",
		},
		"nodes": [
			{
				"stage_code": "observation",
				"status": "available",
				"reason_code": "",
				"command_kind": "",
				"id_refs": [],
				"observer_focus": [
					{"tick": 1832, "sequence": 17, "event_id": "evt-attack"},
				],
			},
			{
				"stage_code": "emotional_state",
				"status": "available",
				"id_refs": [],
				"observer_focus": [],
			},
			{
				"stage_code": "goals",
				"status": "available",
				"id_refs": [["goal", "goal-1"]],
				"observer_focus": [],
			},
			{
				"stage_code": "action",
				"status": "available",
				"command_kind": "attack",
				"id_refs": [],
				"observer_focus": [],
			},
		],
		"supporting_nodes": [
			{"stage_code": "situation_model", "status": "unavailable", "reason_code": "stage_missing", "secondary": true},
		],
	}


func _render_and_focus() -> String:
	var panel: PanelContainer = DebuggerPanel.new()
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	tree.root.add_child(panel)
	var focuses: Array = []
	panel.focus_requested.connect(func(tick: int, sequence: int, event_id: String) -> void:
		focuses.append({"tick": tick, "sequence": sequence, "event_id": event_id})
	)
	panel.open_payload(_sample_payload())
	if not panel.is_open():
		panel.queue_free()
		return "panel should open"
	panel._on_node_activated(0)
	if focuses.size() != 1:
		panel.queue_free()
		return "focus not emitted"
	if focuses[0]["tick"] != 1832 or focuses[0]["sequence"] != 17:
		panel.queue_free()
		return "focus cursor mismatch"
	if focuses[0]["event_id"] != "evt-attack":
		panel.queue_free()
		return "focus event_id mismatch"
	var logged := "\n".join(Log.recent)
	if "debugger_opened" not in logged or "seek_from_debugger" not in logged:
		panel.queue_free()
		return "debugger logs missing"
	panel.close_panel()
	if panel.is_open():
		panel.queue_free()
		return "panel should close"
	panel.queue_free()
	return ""


func _compact_and_expand() -> String:
	var panel: PanelContainer = DebuggerPanel.new()
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	tree.root.add_child(panel)
	panel.open_payload(_sample_payload())
	var compact: ItemList = panel.get_node("Column/CompactStrip")
	if compact.get_item_count() != 8:
		panel.queue_free()
		return "compact strip should have 8 cells"
	var texts: Array[String] = []
	for i in compact.get_item_count():
		texts.append(compact.get_item_text(i))
	for label in DebuggerLabels.COMPACT_SEQUENCE:
		var found := false
		for text in texts:
			if text.begins_with(label + " "):
				found = true
				break
		if not found:
			panel.queue_free()
			return "missing compact label %s" % label
	if panel.is_expanded():
		panel.queue_free()
		return "default should be compact"
	panel._toggle_expanded()
	if not panel.is_expanded():
		panel.queue_free()
		return "expand should toggle"
	var expanded: ItemList = panel.get_node("Column/ExpandedArtifacts")
	var emotion_idx := -1
	var goals_idx := -1
	for i in expanded.get_item_count():
		var text := expanded.get_item_text(i)
		if text.begins_with("Emotion "):
			emotion_idx = i
		if text.begins_with("Goals "):
			goals_idx = i
	if emotion_idx < 0 or goals_idx < 0 or emotion_idx >= goals_idx:
		panel.queue_free()
		return "Emotion must precede Goals in expanded order"
	var header: Label = panel.get_node("Column").get_child(1)
	if "agent_id=alice" not in header.text:
		panel.queue_free()
		return "header should show agent_id"
	var supporting: ItemList = panel.get_node("Column/SupportingNodes")
	if supporting.get_item_count() < 1:
		panel.queue_free()
		return "supporting nodes should stay secondary"
	panel.queue_free()
	return ""


func _unavailable() -> String:
	var panel: PanelContainer = DebuggerPanel.new()
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	tree.root.add_child(panel)
	panel.show_unavailable("capability_forbidden")
	if not panel.is_open():
		panel.queue_free()
		return "unavailable should open panel"
	var logged := "\n".join(Log.recent)
	if "debugger_unavailable reason_code=capability_forbidden" not in logged:
		panel.queue_free()
		return "unavailable log missing"
	panel.queue_free()
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
