extends Control

const ObserverLog := preload("res://scripts/log.gd")

@onready var _loading_label: Label = $LoadingLabel


func _ready() -> void:
	ObserverLog.start()
	ObserverLog.info("main", "client_boot renderer=gl_compatibility")
	if _loading_label != null:
		_loading_label.text = "Loading"
