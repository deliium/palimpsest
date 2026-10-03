extends RefCounted

const DebuggerPanel := preload("res://scripts/ui/debugger_panel.gd")
const Log := preload("res://scripts/log.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _render_and_focus(), "render focus")
	_expect(failures, _unavailable(), "unavailable")
	return failures


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
	panel.open_payload({
		"availability": "available",
		"reason_code": "",
		"address": {"tick": 1832, "sequence": 17, "event_id": "evt-attack"},
		"nodes": [
			{
				"stage_code": "observation",
				"status": "available",
				"reason_code": "",
				"command_kind": "",
				"observer_focus": [
					{"tick": 1832, "sequence": 17, "event_id": "evt-attack"},
				],
			},
			{
				"stage_code": "action",
				"status": "available",
				"command_kind": "attack",
				"observer_focus": [],
			},
		],
	})
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
