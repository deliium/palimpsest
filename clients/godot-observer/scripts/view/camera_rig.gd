extends Camera2D

const ObserverLog := preload("res://scripts/log.gd")

const MIN_ZOOM := 0.35
const MAX_ZOOM := 2.5

var _dragging := false


func _ready() -> void:
	enabled = true


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		if button.button_index == MOUSE_BUTTON_WHEEL_UP and button.pressed:
			_zoom_by(1.1)
			get_viewport().set_input_as_handled()
		elif button.button_index == MOUSE_BUTTON_WHEEL_DOWN and button.pressed:
			_zoom_by(0.9)
			get_viewport().set_input_as_handled()
		elif button.button_index == MOUSE_BUTTON_LEFT:
			_dragging = button.pressed
	elif event is InputEventMouseMotion and _dragging:
		var motion := event as InputEventMouseMotion
		position -= motion.relative / zoom
		_log("pan")


func zoom_step(factor: float) -> void:
	_zoom_by(factor)


func reset_to(target: Vector2) -> void:
	zoom = Vector2.ONE
	position = target
	_log("reset")


func focus_on(target: Vector2) -> void:
	position = target
	_log("focus")


func _zoom_by(factor: float) -> void:
	var next := clampf(zoom.x * factor, MIN_ZOOM, MAX_ZOOM)
	zoom = Vector2(next, next)
	_log("zoom")


func _log(reason: String) -> void:
	ObserverLog.debug("camera", "view_changed zoom=%s reason=%s" % [zoom.x, reason])
