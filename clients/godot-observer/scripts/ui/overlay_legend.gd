extends VBoxContainer

signal overlay_toggled(kind: String, evidence_class: String, enabled: bool)

const ObserverLog := preload("res://scripts/log.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")

## Default-off researcher overlays. Evidence class is mandatory per kind.
const _TOGGLE_ROWS: Array = [
	{"kind": "communication_flows", "caption": "Comm flows", "class": EvidenceClass.OBJECTIVE},
	{"kind": "relationships", "caption": "Relationships", "class": EvidenceClass.SUBJECTIVE},
	{"kind": "territorial_claims", "caption": "Claims", "class": EvidenceClass.SUBJECTIVE},
	{"kind": "narrative_hops", "caption": "Narrative hops", "class": EvidenceClass.SUBJECTIVE},
	{"kind": "spatial_control", "caption": "Spatial control", "class": EvidenceClass.ANALYTICAL},
	{"kind": "emergent_group_formation", "caption": "Groups", "class": EvidenceClass.ANALYTICAL},
	{"kind": "emergent_social_norms", "caption": "Norms", "class": EvidenceClass.ANALYTICAL},
	{"kind": "persistent_social_conventions", "caption": "Conventions", "class": EvidenceClass.ANALYTICAL},
	{"kind": "distributed_reputation", "caption": "Reputation", "class": EvidenceClass.ANALYTICAL},
	{"kind": "communication_strategy_audit", "caption": "Strategy audit", "class": EvidenceClass.ANALYTICAL},
	{"kind": "cultural_transmission", "caption": "Teaching", "class": EvidenceClass.ANALYTICAL},
	{"kind": "skill_learning", "caption": "Skills", "class": EvidenceClass.ANALYTICAL},
]

var _enabled := {}
var _buttons := {}


func _ready() -> void:
	_build_legend()
	_build_toggles()


func is_overlay_enabled(kind: String) -> bool:
	return bool(_enabled.get(kind, false))


func set_overlay_enabled(kind: String, enabled: bool, emit_signal := true) -> void:
	_enabled[kind] = enabled
	if _buttons.has(kind):
		var button: CheckButton = _buttons[kind]
		if button.button_pressed != enabled:
			button.set_pressed_no_signal(enabled)
	var evidence := EvidenceClass.for_overlay(kind)
	ObserverLog.debug(
		"ui",
		"overlay_toggled kind=%s evidence_class=%s enabled=%s" % [kind, evidence, enabled],
	)
	if emit_signal:
		overlay_toggled.emit(kind, evidence, enabled)


func badge_text(evidence_class: String) -> String:
	return EvidenceClass.short_label(evidence_class)


func _build_legend() -> void:
	var title := Label.new()
	title.text = "Evidence classes"
	add_child(title)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	add_child(row)
	for entry in [
		[EvidenceClass.OBJECTIVE, EvidenceClass.LABEL_OBJECTIVE],
		[EvidenceClass.SUBJECTIVE, EvidenceClass.LABEL_SUBJECTIVE],
		[EvidenceClass.ANALYTICAL, EvidenceClass.LABEL_ANALYTICAL],
	]:
		var badge := Label.new()
		badge.text = str(entry[1])
		badge.modulate = Themes.evidence_color(str(entry[0]))
		badge.set_meta("evidence_class", entry[0])
		row.add_child(badge)


func _build_toggles() -> void:
	var title := Label.new()
	title.text = "Researcher overlays (default off)"
	add_child(title)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 4)
	add_child(grid)
	for row in _TOGGLE_ROWS:
		var kind := str(row["kind"])
		var evidence := str(row["class"])
		_enabled[kind] = false
		var button := CheckButton.new()
		button.text = "%s [%s]" % [str(row["caption"]), EvidenceClass.short_label(evidence)]
		button.button_pressed = false
		button.toggled.connect(func(pressed: bool) -> void:
			_on_toggle(kind, evidence, pressed)
		)
		_buttons[kind] = button
		grid.add_child(button)


func _on_toggle(kind: String, evidence_class: String, enabled: bool) -> void:
	_enabled[kind] = enabled
	ObserverLog.debug(
		"ui",
		"overlay_toggled kind=%s evidence_class=%s enabled=%s" % [kind, evidence_class, enabled],
	)
	ObserverLog.info(
		"ui",
		"overlay_%s kind=%s evidence_class=%s" % [
			"enabled" if enabled else "disabled",
			kind,
			evidence_class,
		],
	)
	overlay_toggled.emit(kind, evidence_class, enabled)
