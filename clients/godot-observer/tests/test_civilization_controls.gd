extends RefCounted

const Evidence := preload("res://scripts/presentation/evidence_class.gd")
const UIScene := preload("res://scenes/ui/ui_layer.tscn")


func run() -> Array:
	var failures: Array = []
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return ["scene tree missing"]
	var ui: CanvasLayer = UIScene.instantiate()
	tree.root.add_child(ui)
	_expect(failures, _scene_links(ui), "scene links")
	_expect(failures, _defaults_and_access(ui), "defaults/access")
	_expect(failures, _population_sync(ui), "population sync")
	_expect(failures, _toggles_and_modes(ui), "toggles/modes")
	_expect(failures, _states_and_clearing(ui), "states/clearing")
	_expect(failures, _focus_and_legend(ui), "focus/legend")
	ui.free()
	return failures


func _panel(ui: CanvasLayer) -> PanelContainer:
	return ui.get_node_or_null("CivilizationPanel") as PanelContainer


func _toggle(panel: PanelContainer, id: String) -> CheckButton:
	return panel.find_child("Toggle_%s" % id, true, false) as CheckButton


func _status(panel: PanelContainer, layer: String) -> String:
	return str((panel.find_child("Status_%s" % layer, true, false) as Label).text)


func _summary(panel: PanelContainer, layer: String) -> String:
	return str((panel.find_child("Summary_%s" % layer, true, false) as Label).text)


func _button(panel: PanelContainer, name: String) -> Button:
	return panel.find_child(name, true, false) as Button


func _scene_links(ui: CanvasLayer) -> String:
	var panel := _panel(ui)
	if panel == null:
		return "civilization packed scene missing"
	if panel.get_script() == null or not str(panel.get_script().resource_path).ends_with("civilization_panel.gd"):
		return "civilization script link missing"
	if not ui.has_signal("population_toggled") or not ui.has_signal("civilization_layer_toggled"):
		return "ui signals missing"
	for id in ["population", "culture", "technology", "migration", "groups", "institutions"]:
		if _toggle(panel, id) == null:
			return "primary toggle missing: %s" % id
	for id in ["regions_routes", "settlements", "trade", "projects", "records"]:
		if _toggle(panel, id) == null:
			return "facility toggle missing: %s" % id
	for layer in ["technology", "social_groups", "institutions"]:
		if panel.find_child("Mode_%s" % layer, true, false) == null:
			return "mode control missing: %s" % layer
	return ""


func _defaults_and_access(ui: CanvasLayer) -> String:
	var panel := _panel(ui)
	if not panel.visible:
		return "civilization controls hidden without selection"
	var generational := ui.get_node("GenerationalPanel")
	for id in ["population", "culture", "technology", "migration", "groups", "institutions", "regions_routes", "settlements", "trade", "projects", "records"]:
		var toggle := _toggle(panel, id)
		if toggle.button_pressed:
			return "toggle %s should default off" % id
		if toggle.focus_mode != Control.FOCUS_ALL:
			return "toggle %s not keyboard focusable" % id
	if generational._population.button_pressed:
		return "mirrored population should default off"
	if Evidence.short_label(Evidence.OBJECTIVE) != "OBJECTIVE":
		return "objective label changed"
	if not panel.badge_text(Evidence.OBJECTIVE).contains("OBJECTIVE"):
		return "objective badge missing"
	if not panel.badge_text(Evidence.SUBJECTIVE).contains("SUBJECTIVE"):
		return "subjective badge missing"
	if not panel.badge_text(Evidence.ANALYTICAL).contains("ANALYTICAL"):
		return "analytical badge missing"
	for evidence in [Evidence.OBJECTIVE, Evidence.SUBJECTIVE, Evidence.ANALYTICAL]:
		var badge: Label = panel._badges[evidence]
		if str(badge.get_meta("pattern", "")).is_empty():
			return "badge pattern missing"
	for layer in panel.STATUS_LAYERS:
		if not _status(panel, layer).contains("["):
			return "unlabeled status row: %s" % layer
	return ""


func _population_sync(ui: CanvasLayer) -> String:
	var panel := _panel(ui)
	var group := _toggle(panel, "population")
	var generational := ui.get_node("GenerationalPanel")
	var emissions: Array = []
	ui.population_toggled.connect(func(enabled: bool) -> void: emissions.append(enabled))
	group.button_pressed = true
	if not generational._population.button_pressed:
		return "group toggle did not mirror generational control"
	if emissions.size() != 1 or not bool(emissions[0]):
		return "group population transition did not emit exactly once"
	if not generational.visible:
		return "population toggle should keep generational panel visible"
	ui.set_population_enabled(true)
	if emissions.size() != 1:
		return "idempotent population setter emitted again"
	ui.set_population_enabled(false)
	if group.button_pressed or generational._population.button_pressed:
		return "population false did not mirror both controls"
	generational._population.button_pressed = true
	if not group.button_pressed:
		return "generational toggle did not mirror group control"
	if emissions.size() != 3 or not bool(emissions[2]):
		return "generational population transition did not emit exactly once"
	group.button_pressed = false
	return ""


func _toggles_and_modes(ui: CanvasLayer) -> String:
	var panel := _panel(ui)
	var layers: Array = []
	var modes: Array = []
	var owners: Array = []
	ui.civilization_layer_toggled.connect(func(layer_id: String, enabled: bool) -> void:
		layers.append([layer_id, enabled])
	)
	ui.civilization_layer_mode_selected.connect(func(layer_id: String, mode: String, owner_id: String) -> void:
		modes.append([layer_id, mode, owner_id])
	)
	ui.civilization_owner_changed.connect(func(owner_id: String) -> void: owners.append(owner_id))
	_toggle(panel, "culture").button_pressed = true
	if not _has_layer(layers, "culture", true):
		return "culture toggle signal missing"
	_toggle(panel, "regions_routes").button_pressed = true
	if not _has_layer(layers, "regions", true) or not _has_layer(layers, "routes", true):
		return "regions/routes facility did not emit both layers"
	_toggle(panel, "settlements").button_pressed = true
	if not _has_layer(layers, "settlements", true):
		return "settlement facility signal missing"
	panel._owner_input.text = "agent-a"
	panel._owner_input.text_submitted.emit("agent-a")
	if owners != ["agent-a"]:
		return "owner change not emitted"
	var technology_mode = panel.find_child("Mode_technology", true, false)
	technology_mode.select(1)
	technology_mode.item_selected.emit(1)
	panel._emit_mode("technology")
	if not modes.is_empty():
		var last: Array = modes[modes.size() - 1]
		if str(last[0]) != "technology" or str(last[1]) != "subjective" or str(last[2]) != "agent-a":
			return "technology submode not explicit"
	if not _toggle(panel, "technology").text.contains("SUBJECTIVE"):
		return "technology toggle caption did not expose submode badge"
	for layer in ["social_groups", "institutions"]:
		panel.select_mode(layer, "subjective", false)
		if panel.mode_for(layer) != "subjective":
			return "%s submode not selectable" % layer
	return ""


func _states_and_clearing(ui: CanvasLayer) -> String:
	var panel := _panel(ui)
	panel.apply_layer_state("settlements", _settlement_state())
	if not _status(panel, "settlements").contains("ready"):
		return "settlement ready state missing"
	var settlement_summary := _summary(panel, "settlements")
	for text in ["B=4", "window 3..4", "policy civilization-overlays.v1", "coverage complete", "occupancy 2"]:
		if not settlement_summary.contains(text):
			return "settlement summary missing %s" % text
	panel.apply_layer_state("culture", _culture_state())
	var culture_summary := _summary(panel, "culture")
	if not culture_summary.contains("carriers 1/2") or not culture_summary.contains("50.0%"):
		return "culture denominator/proportion missing"
	if not culture_summary.contains("nonspatial"):
		return "culture unplaced state missing"
	panel.apply_layer_state("technology", _technology_state())
	if not _summary(panel, "technology").contains("holders 1/2"):
		return "technology denominator missing"
	panel.apply_layer_state("institutions", _institution_state())
	if not _summary(panel, "institutions").contains("unplaced/nonspatial"):
		return "institution unplaced state missing"
	panel.apply_layer_state("trade", {
		"status": "empty", "evidence_class": Evidence.ANALYTICAL,
		"cursor": {"tick": 4, "boundary_tick": 4, "revision": 4},
		"coverage": _coverage("complete", null), "rows": [], "next_cursor": null,
	})
	if not _status(panel, "trade").contains("complete-empty"):
		return "complete-empty status missing"
	if not _summary(panel, "trade").contains("complete-empty"):
		return "complete-empty must not render zero"
	var partial := _culture_state()
	partial["status"] = "partial"
	partial["next_cursor"] = "next"
	partial["truncated"] = true
	partial["coverage"] = _coverage("partial", "partial_owner_coverage")
	panel.apply_layer_state("culture", partial)
	if not _status(panel, "culture").contains("partial/truncated"):
		return "partial/truncated status missing"
	if not _button(panel, "LoadMore_culture").visible:
		return "partial Load more missing"
	var cleared: Array = []
	ui.civilization_layer_cleared.connect(func(layer_id: String, reason: String) -> void:
		cleared.append([layer_id, reason])
	)
	panel.apply_layer_state("technology", {"status": "error", "reason_code": "request_failed", "rows": []})
	if not _button(panel, "Retry_technology").visible:
		return "retry control missing for error"
	if _summary(panel, "technology") != "":
		return "error summary not cleared"
	var retries: Array = []
	ui.civilization_retry_requested.connect(func(layer_id: String) -> void: retries.append(layer_id))
	_button(panel, "Retry_technology").pressed.emit()
	if retries != ["technology"]:
		return "retry action missing"
	panel.apply_layer_state("technology", {"status": "unavailable", "reason_code": "capture_gap", "rows": []})
	if not _has_clear(cleared, "technology", "request_failed"):
		return "unavailable clearing signal missing"
	var restricted := _institution_state()
	restricted["status"] = "restricted"
	restricted["reason_code"] = "restricted"
	restricted["rows"] = []
	restricted["rows_count_hidden"] = true
	panel.apply_layer_state("institutions", restricted)
	if not _button(panel, "Credentials_institutions").visible:
		return "restricted credential guidance missing"
	var helps: Array = []
	ui.civilization_credentials_help_requested.connect(func() -> void: helps.append(true))
	_button(panel, "Credentials_institutions").pressed.emit()
	if helps.size() != 1:
		return "credential guidance action missing"
	if _summary(panel, "institutions") != "":
		return "restricted summary should not expose counts"
	var restart := _settlement_state()
	restart["status"] = "unavailable"
	restart["reason_code"] = "cursor_gone"
	restart["restart_required"] = true
	restart["rows"] = []
	panel.apply_layer_state("settlements", restart)
	if not _button(panel, "Restart_settlements").visible:
		return "restart control missing"
	if _summary(panel, "settlements") != "":
		return "unavailable rows left a historical summary"
	return ""


func _focus_and_legend(ui: CanvasLayer) -> String:
	var panel := _panel(ui)
	panel.size = Vector2(420.0, 220.0)
	for id in ["population", "culture", "technology", "migration", "groups", "institutions"]:
		var toggle := _toggle(panel, id)
		if not toggle.is_visible_in_tree():
			return "compact panel hid %s" % id
	panel.focus_first_control()
	if not _toggle(panel, "population").has_focus():
		return "keyboard focus helper failed"
	if ui.is_overlay_enabled("relationships"):
		return "V2 legend default changed"
	ui.set_overlay_enabled("relationships", true)
	if not ui.is_overlay_enabled("relationships"):
		return "V2 legend toggle broken"
	ui.set_overlay_enabled("relationships", false)
	return ""


func _settlement_state() -> Dictionary:
	return {
		"status": "available",
		"evidence_class": Evidence.ANALYTICAL,
		"cursor": {"tick": 4, "boundary_tick": 4, "revision": 4},
		"window": {"start_tick": 3, "end_tick": 4},
		"policy_version": "civilization-overlays.v1",
		"coverage": _coverage("complete", null),
		"rows": [{"location_id": "loc-1", "status": "active", "eligible_occupancy": 2, "context": {"anchors": []}}],
		"next_cursor": null,
	}


func _culture_state() -> Dictionary:
	return {
		"status": "available",
		"evidence_class": Evidence.ANALYTICAL,
		"cursor": {"tick": 4, "boundary_tick": 4, "revision": 4},
		"window": {"start_tick": 3, "end_tick": 4},
		"policy_version": "civilization-overlays.v1",
		"coverage": _coverage("complete", null),
		"rows": [{
			"trait_id": "trait-a", "carrier_count": 1, "eligible_owner_count": 2,
			"proportion": 0.5, "basis": "living_population", "context": {"anchors": []},
		}],
		"next_cursor": null,
	}


func _technology_state() -> Dictionary:
	return {
		"status": "available",
		"evidence_class": Evidence.ANALYTICAL,
		"cursor": {"tick": 4, "boundary_tick": 4, "revision": 4},
		"coverage": _coverage("complete", null),
		"rows": [{
			"knowledge_id": "knowledge-1", "attribution": "unknown",
			"living_holder_count": 1, "eligible_owner_count": 2, "context": {"anchors": []},
		}],
	}


func _institution_state() -> Dictionary:
	return {
		"status": "available",
		"evidence_class": Evidence.SUBJECTIVE,
		"owner_id": "agent-a",
		"cursor": {"tick": 4, "boundary_tick": 4, "revision": 4},
		"coverage": _coverage("complete", null),
		"rows": [{"institution_id": "concept-1", "status": "recognized", "context": {"anchors": []}}],
	}


func _coverage(state: String, reason: Variant) -> Dictionary:
	return {
		"state": state, "reason": reason, "capture_start": null, "capture_end": null,
		"missing_intervals": [], "observed_count": null, "expected_count": null,
	}


func _has_layer(entries: Array, layer_id: String, enabled: bool) -> bool:
	for entry in entries:
		if str(entry[0]) == layer_id and bool(entry[1]) == enabled:
			return true
	return false


func _has_clear(entries: Array, layer_id: String, reason: String) -> bool:
	for entry in entries:
		if str(entry[0]) == layer_id and str(entry[1]) == reason:
			return true
	return false


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
