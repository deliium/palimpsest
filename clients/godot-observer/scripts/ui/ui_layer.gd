extends CanvasLayer

const ObserverLog := preload("res://scripts/log.gd")

signal connect_requested(run_id: String)
signal zoom_in_requested
signal zoom_out_requested
signal reset_requested
signal focus_requested
signal speed_changed(speed: float)


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)
	$StatusBar.connect_requested.connect(func(run_id: String) -> void:
		connect_requested.emit(run_id)
	)
	$Controls/ZoomIn.pressed.connect(func() -> void: zoom_in_requested.emit())
	$Controls/ZoomOut.pressed.connect(func() -> void: zoom_out_requested.emit())
	$Controls/Reset.pressed.connect(func() -> void: reset_requested.emit())
	$Controls/Focus.pressed.connect(func() -> void: focus_requested.emit())
	$Controls/Speed1.pressed.connect(func() -> void: speed_changed.emit(1.0))
	$Controls/Speed2.pressed.connect(func() -> void: speed_changed.emit(2.0))
	$Controls/Speed4.pressed.connect(func() -> void: speed_changed.emit(4.0))
	$Controls/Speed8.pressed.connect(func() -> void: speed_changed.emit(8.0))


func show_status(code: String, detail: String) -> void:
	$StatusBar.show_state(code, detail)
