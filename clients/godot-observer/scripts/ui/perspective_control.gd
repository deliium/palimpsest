extends HBoxContainer

signal perspective_requested(agent_id: String)
signal labels_cleared
signal location_focus_requested(location_id: String)
signal follow_agent_requested(enabled: bool)
signal follow_location_requested(enabled: bool)
signal focused_prev_requested
signal focused_next_requested

const ObserverLog := preload("res://scripts/log.gd")

@onready var _agent_id: LineEdit = $AgentId
@onready var _apply: Button = $Apply
@onready var _clear: Button = $Clear
@onready var _location_id: LineEdit = get_node_or_null("LocationId")
@onready var _follow_agent: Button = get_node_or_null("FollowAgent")
@onready var _follow_location: Button = get_node_or_null("FollowLocation")
@onready var _focus_prev: Button = get_node_or_null("FocusPrev")
@onready var _focus_next: Button = get_node_or_null("FocusNext")


func _ready() -> void:
	_apply.pressed.connect(_on_apply)
	_clear.pressed.connect(_on_clear)
	if _location_id != null:
		_location_id.text_submitted.connect(func(value: String) -> void:
			location_focus_requested.emit(value.strip_edges())
		)
	if _follow_agent != null:
		_follow_agent.toggled.connect(func(pressed: bool) -> void: follow_agent_requested.emit(pressed))
		if not _follow_agent.toggle_mode:
			_follow_agent.toggle_mode = true
	if _follow_location != null:
		_follow_location.toggled.connect(func(pressed: bool) -> void: follow_location_requested.emit(pressed))
		if not _follow_location.toggle_mode:
			_follow_location.toggle_mode = true
	if _focus_prev != null:
		_focus_prev.pressed.connect(func() -> void: focused_prev_requested.emit())
	if _focus_next != null:
		_focus_next.pressed.connect(func() -> void: focused_next_requested.emit())


func set_agent_id(value: String) -> void:
	_agent_id.text = value


func agent_id() -> String:
	return _agent_id.text.strip_edges()


func set_location_id(value: String) -> void:
	if _location_id != null:
		_location_id.text = value


func set_follow_agent(enabled: bool) -> void:
	if _follow_agent != null:
		_follow_agent.button_pressed = enabled
	if enabled and _follow_location != null:
		_follow_location.button_pressed = false


func set_follow_location(enabled: bool) -> void:
	if _follow_location != null:
		_follow_location.button_pressed = enabled
	if enabled and _follow_agent != null:
		_follow_agent.button_pressed = false


func _on_apply() -> void:
	var selected := agent_id()
	if selected.is_empty():
		return
	ObserverLog.debug("ui", "perspective_requested agent_id=%s" % selected)
	perspective_requested.emit(selected)


func _on_clear() -> void:
	ObserverLog.debug("ui", "perspective_cleared")
	labels_cleared.emit()
