extends RefCounted

const DebuggerPanel := preload("res://scripts/ui/debugger_panel.gd")
const DebuggerLabels := preload("res://scripts/presentation/debugger_labels.gd")
const Log := preload("res://scripts/log.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _render_and_focus(), "render focus")
	_expect(failures, _compact_and_expand(), "compact expand")
	_expect(failures, _seek_keeps_primary(), "seek keeps primary")
	_expect(failures, _provenance_and_return(), "provenance return")
	_expect(failures, _seek_vs_provenance_separate(), "seek vs provenance")
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


func _seek_keeps_primary() -> String:
	var panel: PanelContainer = DebuggerPanel.new()
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	tree.root.add_child(panel)
	panel.open_payload(_sample_payload())
	panel.seek_at_expanded(0)
	if panel.primary_payload().is_empty():
		panel.queue_free()
		return "seek must retain primary payload"
	if not panel.is_open():
		panel.queue_free()
		return "seek must keep panel open"
	if str(panel.primary_payload().get("address", {}).get("event_id", "")) != "evt-attack":
		panel.queue_free()
		return "primary address lost after seek"
	if panel.nav_depth() != 0:
		panel.queue_free()
		return "seek must not push provenance nav"
	panel.queue_free()
	return ""


func _provenance_and_return() -> String:
	var panel: PanelContainer = DebuggerPanel.new()
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	tree.root.add_child(panel)
	var provenance: Array = []
	panel.provenance_requested.connect(
		func(lineage_kind: String, subject_id: String, owner_id: String) -> void:
			provenance.append({
				"kind": lineage_kind,
				"subject_id": subject_id,
				"owner_id": owner_id,
			})
	)
	panel.open_payload(_sample_payload())
	# goals is index 2 in ordered chain for the sample (observation, emotion, goals, action)
	panel.request_provenance_at_expanded(2)
	if provenance.size() != 1:
		panel.queue_free()
		return "provenance not emitted"
	if provenance[0]["kind"] != "goal_ancestry" or provenance[0]["subject_id"] != "goal-1":
		panel.queue_free()
		return "provenance map mismatch"
	if provenance[0]["owner_id"] != "alice":
		panel.queue_free()
		return "owner_id must come from address.agent_id"
	if panel.nav_depth() != 1:
		panel.queue_free()
		return "provenance should push nav frame"
	panel.open_lineage_payload({
		"entries": [
			{
				"entry_id": "goal-1",
				"status": "available",
				"reason_code": "",
				"observer_focus": [{"tick": 100, "sequence": 2, "event_id": "evt-goal"}],
			},
		],
	})
	var secondary: ItemList = panel.get_node("Column/SecondaryProvenance")
	if not secondary.visible or secondary.get_item_count() != 1:
		panel.queue_free()
		return "secondary provenance pane missing"
	panel.return_to_decision()
	if panel.nav_depth() != 0:
		panel.queue_free()
		return "return should clear nav stack"
	if secondary.visible:
		panel.queue_free()
		return "return should clear secondary pane"
	if str(panel.primary_payload().get("address", {}).get("event_id", "")) != "evt-attack":
		panel.queue_free()
		return "return must restore primary decision"
	var logged := "\n".join(Log.recent)
	if "debugger_nav_push" not in logged or "debugger_return_to_decision" not in logged:
		panel.queue_free()
		return "nav logs missing"
	panel.queue_free()
	return ""


func _seek_vs_provenance_separate() -> String:
	var panel: PanelContainer = DebuggerPanel.new()
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	tree.root.add_child(panel)
	var focuses: Array = []
	var provenance: Array = []
	panel.focus_requested.connect(func(tick: int, sequence: int, event_id: String) -> void:
		focuses.append(true)
	)
	panel.provenance_requested.connect(
		func(_k: String, _s: String, _o: String) -> void:
			provenance.append(true)
	)
	panel.open_payload(_sample_payload())
	var seek_btn: Button = panel.get_node("Column").get_child(0).get_node("SeekButton")
	var prov_btn: Button = panel.get_node("Column").get_child(0).get_node("ProvenanceButton")
	if seek_btn == null or prov_btn == null:
		panel.queue_free()
		return "Seek/Provenance buttons missing"
	if seek_btn.disabled:
		panel.queue_free()
		return "Seek should enable when observer_focus rows exist"
	if prov_btn.disabled:
		panel.queue_free()
		return "Provenance should enable when mapped id_refs exist"
	panel.seek_at_expanded(0)
	if focuses.size() != 1 or provenance.size() != 0:
		panel.queue_free()
		return "seek must not trigger provenance"
	panel.request_provenance_at_expanded(2)
	if provenance.size() != 1:
		panel.queue_free()
		return "provenance path missing"
	# Missing owner_id must skip lineage.
	var bare := _sample_payload()
	bare["address"].erase("agent_id")
	panel.open_payload(bare)
	prov_btn = panel.get_node("Column").get_child(0).get_node("ProvenanceButton")
	if not prov_btn.disabled:
		panel.queue_free()
		return "Provenance must disable when owner_id missing"
	var before := provenance.size()
	panel.request_provenance_at_expanded(2)
	if provenance.size() != before:
		panel.queue_free()
		return "missing owner_id must skip provenance emit"
	var logged := "\n".join(Log.recent)
	if "owner_id_missing" not in logged:
		panel.queue_free()
		return "owner_id_missing warn missing"
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
