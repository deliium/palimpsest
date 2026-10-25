extends PanelContainer

signal population_toggled(enabled: bool)
signal layer_toggled(layer_id: String, enabled: bool)
signal layer_mode_selected(layer_id: String, mode: String, owner_id: String)
signal owner_changed(owner_id: String)
signal filters_changed(layer_id: String, filters: Dictionary)
signal load_more_requested(layer_id: String)
signal restart_requested(layer_id: String)
signal retry_requested(layer_id: String)
signal layer_cleared(layer_id: String, reason_code: String)
signal credentials_help_requested

const Evidence := preload("res://scripts/presentation/evidence_class.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")
const ObserverLog := preload("res://scripts/log.gd")

const PRIMARY := [
	{"id": "population", "caption": "Population", "evidence": Evidence.OBJECTIVE, "layers": ["population"]},
	{"id": "culture", "caption": "Culture", "evidence": Evidence.ANALYTICAL, "layers": ["culture"]},
	{"id": "technology", "caption": "Technology", "evidence": Evidence.ANALYTICAL, "layers": ["technology"]},
	{"id": "migration", "caption": "Migration", "evidence": Evidence.OBJECTIVE, "layers": ["migration"]},
	{"id": "groups", "caption": "Social groups", "evidence": Evidence.ANALYTICAL, "layers": ["social_groups"]},
	{"id": "institutions", "caption": "Institutions", "evidence": Evidence.ANALYTICAL, "layers": ["institutions"]},
]
const FACILITIES := [
	{"id": "regions_routes", "caption": "Regions / routes", "evidence": Evidence.OBJECTIVE, "layers": ["regions", "routes"]},
	{"id": "settlements", "caption": "Settlement candidates", "evidence": Evidence.ANALYTICAL, "layers": ["settlements"]},
	{"id": "trade", "caption": "Trade / exchange", "evidence": Evidence.ANALYTICAL, "layers": ["trade"]},
	{"id": "projects", "caption": "Projects / public goods", "evidence": Evidence.OBJECTIVE, "layers": ["projects"]},
	{"id": "records", "caption": "Records / repositories", "evidence": Evidence.OBJECTIVE, "layers": ["records", "repositories"]},
]
const MIXED := {
	"technology": ["Analytical / inferred diffusion", "Selected-owner knowledge"],
	"social_groups": ["Analytical / inferred communities", "Selected-owner beliefs"],
	"institutions": ["Analytical / inferred episodes", "Selected-owner concepts"],
}
const STATUS_LAYERS := [
	"culture", "technology", "migration", "social_groups", "institutions",
	"regions", "routes", "settlements", "trade", "projects", "records", "repositories",
]

var _toggles: Dictionary = {}
var _layer_controls: Dictionary = {}
var _mode_buttons: Dictionary = {}
var _badges: Dictionary = {}
var _owner_input: LineEdit
var _status_labels: Dictionary = {}
var _summary_labels: Dictionary = {}
var _load_buttons: Dictionary = {}
var _restart_buttons: Dictionary = {}
var _retry_buttons: Dictionary = {}
var _credential_buttons: Dictionary = {}
var _states: Dictionary = {}
var _had_rows: Dictionary = {}
var _population_enabled := false
var _owner_id := ""
var _column: VBoxContainer


func _ready() -> void:
	custom_minimum_size = Vector2(420, 220)
	_column = $Scroll/Column
	_build()
	call_deferred("_log_acceptance_controls")


func population_enabled() -> bool:
	return _population_enabled


func set_population_pressed_no_signal(enabled: bool) -> void:
	_population_enabled = enabled
	if _toggles.has("population"):
		var button: CheckButton = _toggles["population"]
		button.set_pressed_no_signal(enabled)


func set_population_enabled(enabled: bool, emit_signal: bool = true) -> void:
	var changed := enabled != _population_enabled
	set_population_pressed_no_signal(enabled)
	if changed and emit_signal:
		population_toggled.emit(enabled)


func selected_owner() -> String:
	return _owner_id


func set_selected_owner(owner_id: String) -> void:
	_owner_id = owner_id
	if _owner_input != null:
		_owner_input.text = owner_id
	_update_subjective_badge()


func mode_for(layer_id: String) -> String:
	if not _mode_buttons.has(layer_id):
		return "analytical"
	return "subjective" if _mode_buttons[layer_id].selected == 1 else "analytical"


func select_mode(layer_id: String, mode: String, emit_signal: bool = true) -> void:
	if not _mode_buttons.has(layer_id):
		return
	var button: OptionButton = _mode_buttons[layer_id]
	var index := 1 if mode == "subjective" else 0
	if button.selected != index:
		button.select(index)
		_update_toggle_caption(layer_id)
		if emit_signal:
			_emit_mode(layer_id)


func set_layer_enabled(layer_id: String, enabled: bool) -> void:
	for key in _layer_controls.keys():
		var layers: Array = _layer_controls[key]
		if layer_id in layers and _toggles.has(key):
			(_toggles[key] as CheckButton).set_pressed_no_signal(enabled)


func set_owner_input_visible(value: bool) -> void:
	_owner_input.get_parent().visible = value


func apply_layer_state(layer_id: String, state: Dictionary) -> void:
	_states[layer_id] = state.duplicate(true)
	if not _status_labels.has(layer_id):
		return
	var evidence := str(state.get("evidence_class", _default_evidence(layer_id)))
	if evidence.is_empty():
		evidence = _default_evidence(layer_id)
	var status := str(state.get("status", "off"))
	var reason := str(state.get("reason_code", ""))
	var label: Label = _status_labels[layer_id]
	label.text = "%s [%s] %s" % [
		layer_id.capitalize(),
		Evidence.short_label(evidence),
		_phrase(status, reason),
	]
	var summary: Label = _summary_labels[layer_id]
	summary.text = _summary_text(layer_id, state, evidence)
	(_load_buttons[layer_id] as Button).visible = (
		status in ["available", "partial", "empty"]
		and state.get("next_cursor", null) != null
	)
	(_restart_buttons[layer_id] as Button).visible = bool(state.get("restart_required", false))
	(_retry_buttons[layer_id] as Button).visible = (
		status in ["stale", "error"]
		or (status == "unavailable" and not bool(state.get("restart_required", false)))
	)
	(_credential_buttons[layer_id] as Button).visible = (
		status == "restricted" or reason == "restricted"
	)
	if status == "off":
		set_layer_enabled(layer_id, false)
	var has_rows: bool = not _state_rows(state).is_empty() and status in ["available", "partial", "empty"]
	if not has_rows and bool(_had_rows.get(layer_id, false)):
		_had_rows[layer_id] = false
		layer_cleared.emit(layer_id, reason if not reason.is_empty() else status)
	elif has_rows:
		_had_rows[layer_id] = true
	ObserverLog.debug(
		"acceptance",
		"civilization_layer layer=%s status=%s evidence=%s rows=%s reason=%s" % [
			layer_id,
			status,
			evidence,
			_state_rows(state).size(),
			reason,
		],
	)


func clear_all_states(reason_code: String = "cleared") -> void:
	for layer_id in _states.keys():
		if bool(_had_rows.get(layer_id, false)):
			layer_cleared.emit(layer_id, reason_code)
	_states.clear()
	_had_rows.clear()
	for layer_id in _status_labels.keys():
		(_status_labels[layer_id] as Label).text = "%s [%s] off" % [
			layer_id.capitalize(),
			Evidence.short_label(_default_evidence(layer_id)),
		]
		(_summary_labels[layer_id] as Label).text = ""
		(_load_buttons[layer_id] as Button).visible = false
		(_restart_buttons[layer_id] as Button).visible = false
		(_retry_buttons[layer_id] as Button).visible = false
		(_credential_buttons[layer_id] as Button).visible = false


func has_layer_rows(layer_id: String) -> bool:
	return bool(_had_rows.get(layer_id, false))


func status_text(layer_id: String) -> String:
	return (_status_labels[layer_id] as Label).text if _status_labels.has(layer_id) else ""


func summary_text(layer_id: String) -> String:
	return (_summary_labels[layer_id] as Label).text if _summary_labels.has(layer_id) else ""


func badge_text(evidence_class: String) -> String:
	return (_badges[evidence_class] as Label).text if _badges.has(evidence_class) else ""


func focus_first_control() -> void:
	if _toggles.has("population"):
		(_toggles["population"] as Control).grab_focus()


func _build() -> void:
	var title := Label.new()
	title.text = "Civilization overlays (default off)"
	title.add_theme_font_size_override("font_size", 15)
	_column.add_child(title)

	var badges := HBoxContainer.new()
	badges.add_theme_constant_override("separation", 8)
	_column.add_child(badges)
	for entry in [
		[Evidence.OBJECTIVE, "O | OBJECTIVE", "solid"],
		[Evidence.SUBJECTIVE, "S <> SUBJECTIVE (no owner)", "dashed"],
		[Evidence.ANALYTICAL, "A ~ ANALYTICAL / INFERRED", "dotted"],
	]:
		var badge := Label.new()
		badge.text = str(entry[1])
		badge.modulate = Themes.evidence_color(str(entry[0]))
		badge.set_meta("evidence_class", entry[0])
		badge.set_meta("pattern", entry[2])
		badges.add_child(badge)
		_badges[str(entry[0])] = badge

	var owner_row := HBoxContainer.new()
	owner_row.add_theme_constant_override("separation", 6)
	_column.add_child(owner_row)
	var owner_caption := Label.new()
	owner_caption.text = "Selected owner"
	owner_row.add_child(owner_caption)
	_owner_input = LineEdit.new()
	_owner_input.name = "OwnerInput"
	_owner_input.placeholder_text = "agent id"
	_owner_input.custom_minimum_size = Vector2(180, 0)
	_owner_input.set_meta("acceptance_id", "civilization_owner")
	owner_row.add_child(_owner_input)
	var owner_apply := Button.new()
	owner_apply.name = "OwnerApply"
	owner_apply.text = "Apply owner"
	owner_apply.set_meta("acceptance_id", "civilization_owner_apply")
	owner_apply.pressed.connect(_on_owner_apply)
	owner_row.add_child(owner_apply)
	_owner_input.text_submitted.connect(func(_text: String) -> void: _on_owner_apply())

	var primary_title := Label.new()
	primary_title.text = "Primary overlays"
	_column.add_child(primary_title)
	var primary_grid := GridContainer.new()
	primary_grid.columns = 2
	primary_grid.add_theme_constant_override("h_separation", 10)
	primary_grid.add_theme_constant_override("v_separation", 4)
	_column.add_child(primary_grid)
	for row in PRIMARY:
		var button := _make_toggle(row, primary_grid)
		_toggles[str(row["id"])] = button

	var mode_title := Label.new()
	mode_title.text = "Evidence submodes"
	_column.add_child(mode_title)
	var mode_grid := GridContainer.new()
	mode_grid.columns = 2
	mode_grid.add_theme_constant_override("h_separation", 10)
	mode_grid.add_theme_constant_override("v_separation", 4)
	_column.add_child(mode_grid)
	for layer_id in MIXED.keys():
		var caption := Label.new()
		caption.text = layer_id.capitalize()
		mode_grid.add_child(caption)
		var button := OptionButton.new()
		button.name = "Mode_%s" % layer_id
		button.set_meta("acceptance_id", "civilization_mode_%s" % layer_id)
		for option in MIXED[layer_id]:
			button.add_item(str(option))
		button.item_selected.connect(func(_index: int) -> void:
			_update_toggle_caption(layer_id)
			_emit_mode(layer_id)
		)
		mode_grid.add_child(button)
		_mode_buttons[layer_id] = button

	var facility_title := Label.new()
	facility_title.text = "Facilities and context"
	_column.add_child(facility_title)
	var facility_grid := GridContainer.new()
	facility_grid.columns = 2
	facility_grid.add_theme_constant_override("h_separation", 10)
	facility_grid.add_theme_constant_override("v_separation", 4)
	_column.add_child(facility_grid)
	for row in FACILITIES:
		var button := _make_toggle(row, facility_grid)
		_toggles[str(row["id"])] = button

	var legend := Label.new()
	legend.name = "FacilityLegend"
	legend.text = (
		"Legend: solid = world neighbor; dashed = configured route; "
		+ "envelope = region (overlap is not adjacency); "
		+ "containers = records / repositories (archive evidence)"
	)
	legend.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	legend.set_meta("acceptance_id", "civilization_facility_legend")
	_column.add_child(legend)

	var flow_legend := Label.new()
	flow_legend.name = "FlowLegend"
	flow_legend.text = (
		"Flows: dashed = intention; solid = outcome; dotted/dash-dot = knowledge modality; "
		+ "local loop = co-located completed exchange; hatch = analytical culture"
	)
	flow_legend.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	flow_legend.set_meta("acceptance_id", "civilization_flow_legend")
	_column.add_child(flow_legend)

	var status_title := Label.new()
	status_title.text = "Layer availability"
	_column.add_child(status_title)
	for layer_id in STATUS_LAYERS:
		var block := VBoxContainer.new()
		block.name = "StatusBlock_%s" % layer_id
		block.add_theme_constant_override("separation", 1)
		_column.add_child(block)
		var label := Label.new()
		label.name = "Status_%s" % layer_id
		label.text = "%s [%s] off" % [layer_id.capitalize(), Evidence.short_label(_default_evidence(layer_id))]
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		block.add_child(label)
		_status_labels[layer_id] = label
		var summary := Label.new()
		summary.name = "Summary_%s" % layer_id
		summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		block.add_child(summary)
		_summary_labels[layer_id] = summary
		var actions := HBoxContainer.new()
		block.add_child(actions)
		var load := Button.new()
		load.name = "LoadMore_%s" % layer_id
		load.text = "Load more"
		load.visible = false
		load.pressed.connect(func() -> void: load_more_requested.emit(layer_id))
		actions.add_child(load)
		_load_buttons[layer_id] = load
		var restart := Button.new()
		restart.name = "Restart_%s" % layer_id
		restart.text = "Restart"
		restart.visible = false
		restart.pressed.connect(func() -> void: restart_requested.emit(layer_id))
		actions.add_child(restart)
		_restart_buttons[layer_id] = restart
		var retry := Button.new()
		retry.name = "Retry_%s" % layer_id
		retry.text = "Retry"
		retry.visible = false
		retry.pressed.connect(func() -> void: retry_requested.emit(layer_id))
		actions.add_child(retry)
		_retry_buttons[layer_id] = retry
		var credentials := Button.new()
		credentials.name = "Credentials_%s" % layer_id
		credentials.text = "Credentials"
		credentials.visible = false
		credentials.pressed.connect(func() -> void: credentials_help_requested.emit())
		actions.add_child(credentials)
		_credential_buttons[layer_id] = credentials


func _make_toggle(row: Dictionary, parent: Control) -> CheckButton:
	var button := CheckButton.new()
	var id := str(row["id"])
	button.name = "Toggle_%s" % id
	button.text = "%s [%s]" % [str(row["caption"]), Evidence.short_label(str(row["evidence"]))]
	button.button_pressed = false
	button.focus_mode = Control.FOCUS_ALL
	button.set_meta("acceptance_id", "civilization_%s_toggle" % id)
	var layers: Array = row["layers"]
	_layer_controls[id] = layers
	if id == "population":
		button.toggled.connect(_on_population_pressed)
	else:
		button.toggled.connect(func(pressed: bool) -> void:
			for layer_id in layers:
				layer_toggled.emit(str(layer_id), pressed)
		)
	parent.add_child(button)
	return button


func _on_population_pressed(pressed: bool) -> void:
	if pressed == _population_enabled:
		return
	_population_enabled = pressed
	population_toggled.emit(pressed)


func _on_owner_apply() -> void:
	_owner_id = _owner_input.text.strip_edges()
	_update_subjective_badge()
	owner_changed.emit(_owner_id)


func _emit_mode(layer_id: String) -> void:
	var mode := mode_for(layer_id)
	var owner := _owner_id if mode == "subjective" else ""
	layer_mode_selected.emit(layer_id, mode, owner)


func _update_toggle_caption(layer_id: String) -> void:
	if not _mode_buttons.has(layer_id):
		return
	var id := ""
	match layer_id:
		"technology":
			id = "technology"
		"social_groups":
			id = "groups"
		"institutions":
			id = "institutions"
	if id.is_empty() or not _toggles.has(id):
		return
	var evidence := Evidence.SUBJECTIVE if mode_for(layer_id) == "subjective" else Evidence.ANALYTICAL
	(_toggles[id] as CheckButton).text = "%s [%s]" % [
		layer_id.capitalize(),
		Evidence.short_label(evidence),
	]


func _update_subjective_badge() -> void:
	if not _badges.has(Evidence.SUBJECTIVE):
		return
	var owner_text := _owner_id if not _owner_id.is_empty() else "no owner"
	(_badges[Evidence.SUBJECTIVE] as Label).text = "S <> SUBJECTIVE (%s)" % owner_text


func _default_evidence(layer_id: String) -> String:
	if layer_id in ["regions", "routes", "migration", "projects", "records", "repositories", "population"]:
		return Evidence.OBJECTIVE
	if layer_id in ["culture", "settlements", "trade"]:
		return Evidence.ANALYTICAL
	if layer_id in MIXED:
		return Evidence.SUBJECTIVE if mode_for(layer_id) == "subjective" else Evidence.ANALYTICAL
	return Evidence.ANALYTICAL


func _phrase(status: String, reason: String) -> String:
	match status:
		"off":
			return "off"
		"loading":
			return "loading"
		"available":
			return "ready"
		"empty":
			return "complete-empty"
		"partial":
			return "partial/truncated"
		"stale":
			return "stale"
		"restricted":
			return "restricted (%s)" % ("credentials required" if reason.is_empty() else reason)
		"error":
			return "error (%s)" % ("unknown" if reason.is_empty() else reason)
		"unavailable":
			return "unavailable (%s)" % ("unknown" if reason.is_empty() else reason)
		_:
			return status


func _summary_text(layer_id: String, state: Dictionary, evidence: String) -> String:
	var status := str(state.get("status", "off"))
	if status in ["off", "loading", "unavailable", "restricted", "error", "stale"]:
		return ""
	var rows := _state_rows(state)
	var parts: Array[String] = []
	parts.append("evidence %s" % Evidence.short_label(evidence))
	var cursor: Dictionary = state.get("cursor", {}) if state.get("cursor", null) != null else {}
	var boundary: Variant = cursor.get("boundary_tick", null)
	if boundary == null:
		boundary = state.get("resolved_cursor", {}).get("boundary_tick", null) if state.get("resolved_cursor", null) != null else null
	if boundary != null:
		parts.append("B=%s" % str(boundary))
	elif not cursor.is_empty():
		parts.append("tick=%s" % str(cursor.get("tick", "?")))
	var window: Variant = state.get("window", null)
	if window != null:
		parts.append("window %s..%s" % [str(window.start_tick), str(window.end_tick)])
	var policy := str(state.get("policy_version", ""))
	if not policy.is_empty():
		parts.append("policy %s" % policy)
	var coverage: Variant = state.get("coverage", null)
	if coverage != null:
		var coverage_text := str(coverage.state)
		if coverage.reason != null:
			coverage_text += "(%s)" % str(coverage.reason)
		if coverage.observed_count != null and coverage.expected_count != null:
			coverage_text += " %s/%s" % [str(coverage.observed_count), str(coverage.expected_count)]
		parts.append("coverage %s" % coverage_text)
	if state.get("client_cap", "") != "":
		parts.append("client cap %s" % str(state.get("client_cap")))
	if rows.is_empty():
		parts.append("complete-empty; no zero-substitution")
		return " | ".join(parts)
	parts.append("rows %s" % str(rows.size()))
	var detail: Array[String] = []
	for row in rows.slice(0, mini(3, rows.size())):
		var text := _row_summary(layer_id, row)
		if not text.is_empty():
			detail.append(text)
	if rows.size() > 3:
		detail.append("+%s more" % str(rows.size() - 3))
	if not detail.is_empty():
		parts.append("; ".join(detail))
	return " | ".join(parts)


func _row_summary(layer_id: String, row: Variant) -> String:
	match layer_id:
		"culture":
			var denominator: Variant = _value(row, "eligible_owner_count", null)
			var denominator_text := "unknown" if denominator == null else str(denominator)
			var proportion: Variant = _value(row, "proportion", null)
			var proportion_text := "unknown" if proportion == null else "%s%%" % str(round(float(proportion) * 1000.0) / 10.0)
			var basis := str(_value(row, "basis", ""))
			var spatial := "unplaced/nonspatial" if _anchors(row).is_empty() else "placed"
			return "%s carriers %s/%s (%s) basis %s %s" % [
				str(_value(row, "trait_id", "?")), str(_value(row, "carrier_count", 0)),
				denominator_text, proportion_text, basis, spatial,
			]
		"settlements":
			return "%s %s occupancy %s" % [
				str(_value(row, "location_id", "?")), str(_value(row, "status", "?")),
				str(_value(row, "eligible_occupancy", 0)),
			]
		"trade":
			return "%s completed %s" % [
				",".join(_string_list(_value(row, "participant_ids", []))),
				str(_value(row, "completed_exchange_count", 0)),
			]
		"technology":
			return "%s %s holders %s/%s" % [
				str(_value(row, "knowledge_id", "?")), str(_value(row, "attribution", "?")),
				"unknown" if _value(row, "living_holder_count", null) == null else str(_value(row, "living_holder_count")),
				"unknown" if _value(row, "eligible_owner_count", null) == null else str(_value(row, "eligible_owner_count")),
			]
		"social_groups":
			return "%s %s members %s" % [
				str(_value(row, "group_id", "?")), str(_value(row, "basis", "?")),
				str(_value(row, "member_count", 0)),
			]
		"institutions":
			var placement := "unplaced/nonspatial" if _anchors(row).is_empty() else "placed"
			return "%s %s %s" % [str(_value(row, "institution_id", "?")), str(_value(row, "status", "?")), placement]
		"migration":
			return "%s %s" % [str(_value(row, "journey_id", "?")), str(_value(row, "phase", "?"))]
		_:
			return str(_value(row, "location_id", _value(row, "region_id", _value(row, "project_id", _value(row, "record_id", _value(row, "repository_id", _value(row, "route_id", "")))))))


func _state_rows(state: Dictionary) -> Array:
	var rows: Variant = state.get("rows", [])
	return rows if typeof(rows) == TYPE_ARRAY else []


func _anchors(row: Variant) -> Array:
	var context: Variant = _value(row, "context", null)
	if context == null:
		return []
	var anchors: Variant = _value(context, "anchors", [])
	return anchors if typeof(anchors) == TYPE_ARRAY else []


func _value(value: Variant, key: String, default: Variant = null) -> Variant:
	if value == null:
		return default
	if typeof(value) == TYPE_DICTIONARY:
		return value.get(key, default)
	var result: Variant = value.get(key)
	return default if result == null else result


func _string_list(value: Variant) -> Array:
	return value if typeof(value) == TYPE_ARRAY else []


func _log_acceptance_controls() -> void:
	var controls: Array = []
	for id in _toggles.keys():
		controls.append(["civilization_%s_toggle" % id, _toggles[id]])
	for id in _mode_buttons.keys():
		controls.append(["civilization_mode_%s" % id, _mode_buttons[id]])
	controls.append(["civilization_owner", _owner_input])
	for entry in controls:
		var control: Control = entry[1]
		var rect := control.get_global_rect()
		ObserverLog.debug(
			"acceptance",
			"control id=%s x=%s y=%s w=%s h=%s" % [
				entry[0], rect.position.x, rect.position.y, rect.size.x, rect.size.y,
			],
		)
