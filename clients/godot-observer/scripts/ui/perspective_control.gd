extends HBoxContainer

signal perspective_requested(agent_id: String)
signal labels_cleared

const ObserverLog := preload("res://scripts/log.gd")

@onready var _agent_id: LineEdit = $AgentId
@onready var _apply: Button = $Apply
@onready var _clear: Button = $Clear


func _ready() -> void:
	_apply.pressed.connect(_on_apply)
	_clear.pressed.connect(_on_clear)


func set_agent_id(value: String) -> void:
	_agent_id.text = value


func agent_id() -> String:
	return _agent_id.text.strip_edges()


func _on_apply() -> void:
	var selected := agent_id()
	if selected.is_empty():
		return
	ObserverLog.debug("ui", "perspective_requested agent_id=%s" % selected)
	perspective_requested.emit(selected)


func _on_clear() -> void:
	ObserverLog.debug("ui", "perspective_cleared")
	labels_cleared.emit()
