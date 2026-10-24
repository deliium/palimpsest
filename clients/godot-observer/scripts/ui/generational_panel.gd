extends PanelContainer

signal population_toggled(enabled: bool)
signal section_selected(section: String)
signal load_more_requested
signal agent_selected(agent_id: String)
signal lineage_tab_selected(tab: String)
signal back_requested

const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")
const ObserverLog := preload("res://scripts/log.gd")

@onready var _population: CheckButton = $Column/Population
@onready var _summary: Label = $Column/Summary
@onready var _stages: Label = $Column/Stages
@onready var _status: Label = $Column/Status
@onready var _agents: ItemList = $Column/Agents
@onready var _groups: ItemList = $Column/Groups
@onready var _load_more: Button = $Column/LoadMore
@onready var _tabs: HBoxContainer = $Column/Tabs
@onready var _lineage_title: Label = $Column/LineageTitle
@onready var _lineage_body: Label = $Column/LineageBody
@onready var _back: Button = $Column/Actions/Back

var selected_agent_id := ""
var selection_state := "unselected"
var _agent_ids: Array = []


func _ready() -> void:
	visible = true
	_population.toggled.connect(func(enabled: bool) -> void:
		visible = true
		ObserverLog.debug("acceptance", "population_toggle_state enabled=%s" % enabled)
		population_toggled.emit(enabled)
		call_deferred("_log_acceptance_controls")
	)
	_agents.item_selected.connect(func(index: int) -> void:
		if index >= 0 and index < _agent_ids.size():
			agent_selected.emit(str(_agent_ids[index]))
	)
	_load_more.pressed.connect(func() -> void: load_more_requested.emit())
	_back.pressed.connect(func() -> void: back_requested.emit())
	for section in ["agents", "cohorts", "generations"]:
		var button := Button.new()
		button.text = section.capitalize()
		button.pressed.connect(func() -> void: section_selected.emit(section))
		$Column/Sections.add_child(button)
	for tab in ["Parents", "Children", "Teachers", "Students", "Knowledge", "Mentorship"]:
		var button := Button.new()
		button.text = tab
		button.pressed.connect(func() -> void: lineage_tab_selected.emit(tab.to_lower()))
		_tabs.add_child(button)
	show_unavailable("unselected")
	apply_selection(null, "unselected")
	call_deferred("_log_acceptance_controls")


func is_population_enabled() -> bool:
	return _population.button_pressed


func set_population_enabled(enabled: bool) -> void:
	_population.set_pressed_no_signal(enabled)
	if enabled:
		visible = true


func apply_demographics(model: Variant) -> void:
	ObserverLog.debug(
		"acceptance",
		"panel_apply_demographics null=%s availability=%s population_null=%s" % [
			model == null,
			"missing" if model == null else str(model.availability),
			true if model == null else model.population == null,
		],
	)
	if model == null:
		show_unavailable("unavailable")
		return
	if model.availability != "available" or model.population == null:
		show_unavailable(str(model.reason_code) if model.reason_code != null else "unavailable")
		return
	_status.text = "OBJECTIVE | tick %s | %s" % [model.resolved_tick, model.selection_state]
	_summary.text = "living %s | admitted %s | dead %s | max generation %s" % [
		model.population.living,
		model.population.admitted,
		model.population.dead,
		model.population.max_generation_index,
	]
	var stage_lines: Array[String] = []
	for row in model.stage_rows:
		stage_lines.append("%s/%s: %s" % [row.stage, row.life_status, row.count])
	if model.stage_counts_truncated:
		stage_lines.append("stage list truncated")
	_stages.text = "stages: " + ("none" if stage_lines.is_empty() else ", ".join(stage_lines))
	_agent_ids = []
	_agents.clear()
	for row in model.agents:
		_agent_ids.append(row.agent_id)
		_agents.add_item("%s | %s | gen %s | %s | age %s" % [
			row.agent_id,
			row.stage,
			row.generation_index,
			row.life_status,
			"n/a" if row.age_ticks == null else str(row.age_ticks),
		])
	_groups.clear()
	for row in model.cohorts:
		_groups.add_item("cohort %s g%s entry %s: %s/%s/%s" % [
			row.cohort_id, row.generation_index, row.entry_tick,
			row.living, row.dead, row.admitted,
		])
	for row in model.generations:
		_groups.add_item("generation %s: %s/%s/%s" % [
			row.generation_index, row.living, row.dead, row.admitted,
		])
	_load_more.visible = (
		model.next_after_agent_id != null or model.next_after_group_key != null
	)
	_back.visible = not selected_agent_id.is_empty()
	ObserverLog.debug(
		"acceptance",
		"demographics_rendered living=%s admitted=%s dead=%s max_generation=%s stage_truncated=%s stale=%s" % [
			model.population.living,
			model.population.admitted,
			model.population.dead,
			model.population.max_generation_index,
			model.stage_counts_truncated,
			model.availability != "available",
		],
	)
	_log_acceptance_controls()


func apply_selection(row: Variant, state: String) -> void:
	selection_state = state
	if row == null:
		_lineage_title.text = "Selection at cursor: %s" % state
		return
	_lineage_title.text = "Selected %s | %s | %s" % [
		row.agent_id, row.stage, row.life_status
	]
	call_deferred("_log_acceptance_controls")


func apply_lineage(panel: String, data: Dictionary) -> void:
	_lineage_title.text = panel.capitalize()
	if data.is_empty():
		_lineage_body.text = "unavailable"
		return
	var status := str(data.get("status", ""))
	if status != "available":
		_lineage_body.text = status if str(data.get("reason_code", "")) == "" else "%s (%s)" % [status, data["reason_code"]]
		return
	var lines: Array[String] = []
	if panel == "genealogy":
		lines.append("parents: " + _agent_list(data.get("parents", [])))
		lines.append("children: " + _agent_list(data.get("children", [])))
	elif panel == "participants":
		lines.append("evidence: %s | owner %s | role %s" % [
			data.get("evidence_class", ""), data.get("owner_id", ""), data.get("role", "")
		])
		var attempt := 0
		var evidence := 0
		for card in data.get("items", []):
			lines.append("%s -> %s | %s | %s | evidence %s | attempts %s" % [
				card.teacher_id, card.learner_id, card.content_kind,
				card.learning_state, card.learning_evidence_count, card.attempt_count,
			])
			if card.learning_state == "attempt_only":
				attempt += 1
			else:
				evidence += 1
		lines.append("loaded cards: %s (learning evidence %s, attempt-only %s)" % [
			data.get("items", []).size(), evidence, attempt,
		])
		if bool(data.get("scan_limited", false)):
			lines.append("scan limited: more candidates remain")
	else:
		lines.append("nodes: %s" % data.get("items", []).size())
	_lineage_body.text = "\n".join(lines)
	ObserverLog.debug(
		"acceptance",
		"lineage_applied panel=%s status=%s item_count=%s" % [
			panel, status, data.get("items", []).size() if panel == "participants" else lines.size(),
		],
	)
	_back.visible = not selected_agent_id.is_empty()


func set_selected_agent(agent_id: String) -> void:
	selected_agent_id = agent_id
	_back.visible = not agent_id.is_empty()
	if agent_id.is_empty():
		_lineage_body.text = "Select an agent to navigate lineage."


func set_back_available(available: bool) -> void:
	_back.visible = available


func show_unavailable(reason: String) -> void:
	_status.text = "OBJECTIVE | unavailable"
	_summary.text = "N/A (%s)" % reason
	_stages.text = ""
	_groups.clear()
	_agents.clear()


func _agent_list(values: Array) -> String:
	var ids: Array[String] = []
	for node in values:
		ids.append(str(node.ref.native_id))
	return "none" if ids.is_empty() else ", ".join(ids)


func _log_acceptance_controls() -> void:
	var controls: Array = [
		["population_toggle", _population],
		["population_load_more", _load_more],
		["population_back", _back],
		["population_agents", _agents],
	]
	var index := 0
	for child in $Column/Sections.get_children():
		controls.append(["demographic_section_%s" % index, child])
		index += 1
	index = 0
	for child in _tabs.get_children():
		controls.append(["lineage_tab_%s" % index, child])
		index += 1
	for entry in controls:
		var control := entry[1] as Control
		if control == null:
			continue
		var rect := control.get_global_rect()
		ObserverLog.debug(
			"acceptance",
			"control id=%s x=%s y=%s w=%s h=%s" % [
				entry[0], rect.position.x, rect.position.y, rect.size.x, rect.size.y,
			],
		)
