extends PanelContainer

## Small research-focus inspector. Presentation only; never commands the world.

signal open_research_requested
signal shared_requested
signal back_requested
signal share_requested

const ObserverLog := preload("res://scripts/log.gd")

var _title: Label
var _meta: RichTextLabel
var _rows: RichTextLabel
var _open_button: Button
var _share_button: Button
var _state: Dictionary = {}


func _ready() -> void:
	var box := VBoxContainer.new()
	add_child(box)
	_title = Label.new()
	_title.text = "Research focus"
	box.add_child(_title)
	_meta = RichTextLabel.new()
	_meta.fit_content = true
	_meta.custom_minimum_size = Vector2(420, 110)
	box.add_child(_meta)
	_rows = RichTextLabel.new()
	_rows.fit_content = true
	_rows.custom_minimum_size = Vector2(420, 130)
	box.add_child(_rows)
	var actions := HBoxContainer.new()
	box.add_child(actions)
	_open_button = Button.new()
	_open_button.text = "Open Research"
	_open_button.pressed.connect(func() -> void: open_research_requested.emit())
	actions.add_child(_open_button)
	_share_button = Button.new()
	_share_button.text = "Share"
	_share_button.pressed.connect(func() -> void: share_requested.emit())
	actions.add_child(_share_button)
	var back := Button.new()
	back.text = "Back"
	back.pressed.connect(func() -> void: back_requested.emit())
	actions.add_child(back)
	visible = false


func set_research_focus(state: Dictionary) -> void:
	_state = state.duplicate(true)
	if not bool(_state.get("active", false)):
		visible = bool(_state.get("reason_code", "") != "")
		if not visible:
			return
	_title.text = "Research focus · %s" % str(_state.get("kind", "unavailable"))
	_meta.text = _meta_text()
	_rows.text = _rows_text()
	_open_button.disabled = str(_state.get("resolution", "")) != "resolved"
	_share_button.disabled = str(_state.get("native_id", "")).is_empty()
	visible = true


func focus_state() -> Dictionary:
	return _state.duplicate(true)


func _meta_text() -> String:
	var lines: Array = []
	lines.append("source=%s class=%s" % [str(_state.get("source", "")), str(_state.get("evidence_class", ""))])
	if str(_state.get("identity_owner", "")) != "":
		lines.append("identity_owner=%s" % str(_state.get("identity_owner", "")))
	if str(_state.get("family", "")) != "":
		lines.append("family=%s native=%s:%s" % [str(_state.get("family", "")), str(_state.get("native_kind", "")), str(_state.get("native_id", ""))])
	if str(_state.get("civilization_row_id", "")) != "":
		lines.append("row=%s" % str(_state.get("civilization_row_id", "")))
	if str(_state.get("publication_id", "")) != "":
		lines.append("publication=%s" % str(_state.get("publication_id", "")))
	lines.append("requested=%s captured=%s" % [str(_state.get("requested_tick", "")), str(_state.get("captured_tick", ""))])
	lines.append("resolution=%s status=%s reason=%s" % [str(_state.get("resolution", "")), str(_state.get("root_status", "")), str(_state.get("reason_code", ""))])
	return "\n".join(lines)


func _rows_text() -> String:
	var bounded: Array = _state.get("rows", [])
	var lines: Array = []
	for row in bounded.slice(0, 5):
		if typeof(row) == TYPE_DICTIONARY:
			lines.append(str(row.get("row_id", row.get("native_id", ""))))
	if lines.is_empty():
		return "No bounded metadata rows."
	return "\n".join(lines)
