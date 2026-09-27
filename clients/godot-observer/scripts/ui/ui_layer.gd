extends CanvasLayer

const ObserverLog := preload("res://scripts/log.gd")

signal connect_requested(run_id: String)


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)
	$StatusBar.connect_requested.connect(func(run_id: String) -> void:
		connect_requested.emit(run_id)
	)


func show_status(code: String, detail: String) -> void:
	$StatusBar.show_state(code, detail)
