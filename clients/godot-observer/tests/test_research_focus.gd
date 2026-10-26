extends RefCounted

const FocusScript := preload("res://scripts/net/research_focus.gd")
const PanelScene := preload("res://scenes/ui/research_focus_panel.tscn")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _lineage_resolution(), "lineage focus")
	_expect(failures, _identity_mismatch(), "identity mismatch")
	_expect(failures, _civ_resolution(), "civilization focus")
	_expect(failures, _panel_mount(), "focus panel")
	return failures


func _expect(failures: Array, result: String, label: String) -> void:
	if result != "":
		failures.append("%s: %s" % [label, result])


func _lineage_resolution() -> String:
	var controller = FocusScript.new()
	var captured := {"meta": {}, "query": {}}
	controller.set_request_sink(func(_kind: String, _path: String, meta: Dictionary, query: Dictionary) -> void:
		captured["meta"] = meta.duplicate(true)
		captured["query"] = query.duplicate(true)
	)
	controller.set_context("run-1", 1, 0)
	controller.resolve_selection({
		"institution_id": "office-1",
		"entity_source": "lineage",
		"lineage_family": "office_succession",
		"native_kind": "office",
		"evidence_class": "subjective",
		"owner_id": "agent-a",
		"identity_owner": "agent-a",
		"tick": 4,
	})
	var meta: Dictionary = captured["meta"]
	if str(meta.get("source", "")) != "research_focus":
		return "request source missing"
	if str(meta.get("focus_source", "")) != "lineage":
		return "focus source missing"
	var query: Dictionary = captured["query"]
	if str(query.get("owner_id", "")) != "agent-a":
		return "subjective scope owner dropped"
	if query.has("publication_id") or query.has("identity_owner"):
		return "unsupported query key sent"
	controller.handle_response(meta, {
		"snapshot": {"publication_id": "pub-1", "digest": "d", "boundary_tick": 4},
		"items": [
			{"ref": {"family": "office_succession", "evidence_class": "subjective", "native_kind": "office", "native_id": "office-1", "identity_owner": "agent-a", "key": "k"}},
		],
		"coverage": {},
	}, "", 200)
	if str(controller.state().get("resolution", "")) != "resolved":
		return "subjective office not resolved"
	return ""


func _identity_mismatch() -> String:
	var controller = FocusScript.new()
	var meta := {}
	controller.set_request_sink(func(_kind: String, _path: String, request_meta: Dictionary, _query: Dictionary) -> void:
		meta = request_meta.duplicate(true)
	)
	controller.set_context("run-1", 1, 0)
	controller.resolve_selection({
		"technology_id": "tech-1",
		"entity_source": "lineage",
		"lineage_family": "technology",
		"native_kind": "technique",
		"evidence_class": "analytical",
		"identity_owner": "agent-a",
	})
	controller.handle_response(meta, {
		"snapshot": {"publication_id": "pub-1", "digest": "d", "boundary_tick": 4},
		"items": [
			{"ref": {"family": "technology", "evidence_class": "analytical", "native_kind": "technique", "native_id": "tech-1", "identity_owner": "agent-b", "key": "k"}},
		],
		"coverage": {},
	}, "", 200)
	if str(controller.state().get("resolution", "")) != "unresolved":
		return "wrong identity owner accepted"
	if str(controller.state().get("reason_code", "")) != "lineage_node_not_found":
		return "missing safe reason"
	return ""


func _civ_resolution() -> String:
	var controller = FocusScript.new()
	var meta := {}
	var query := {}
	controller.set_request_sink(func(_kind: String, _path: String, request_meta: Dictionary, request_query: Dictionary) -> void:
		meta = request_meta.duplicate(true)
		query = request_query.duplicate(true)
	)
	controller.set_context("run-1", 1, 0)
	controller.resolve_selection({
		"institution_id": "concept-1",
		"entity_source": "civilization",
		"evidence_class": "subjective",
		"owner_id": "agent-a",
		"identity_owner": "agent-a",
		"civilization_row_id": "row-1",
		"tick": 4,
	})
	if str(query.get("layer", "")) != "institutions":
		return "institutions layer missing"
	if str(query.get("owner_id", "")) != "agent-a":
		return "subjective civilization scope owner missing"
	controller.handle_response(meta, {
		"publication": {"publication_id": "pub-1"},
		"resolved_cursor": {"boundary_tick": 4},
		"coverage": {},
		"rows": [{"context": {"row_id": "row-1"}}],
	}, "", 200)
	if str(controller.state().get("resolution", "")) != "resolved":
		return "exact civilization row not resolved"
	return ""


func _panel_mount() -> String:
	var panel: PanelContainer = PanelScene.instantiate()
	var tree := Engine.get_main_loop() as SceneTree
	tree.root.add_child(panel)
	panel.set_research_focus({
		"active": true, "kind": "institution", "source": "civilization",
		"evidence_class": "subjective", "identity_owner": "agent-a",
		"native_kind": "concept", "native_id": "concept-1",
		"civilization_row_id": "row-1", "resolution": "resolved",
		"root_status": "matched_row", "reason_code": "",
		"requested_tick": 4, "captured_tick": 4, "rows": [],
	})
	if not panel.visible:
		return "panel not visible"
	var box: VBoxContainer = panel.get_child(0)
	var title: Label = box.get_child(0)
	if not title.text.contains("institution"):
		return "focus kind missing"
	panel.set_research_focus({"active": false, "reason_code": "capture_absent"})
	if not panel.visible:
		return "unavailable reason not shown"
	panel.free()
	return ""
