extends Node

const ObserverLog := preload("res://scripts/log.gd")

@onready var _world: Node2D = $WorldView
@onready var _ui: CanvasLayer = $UILayer
@onready var _session: Node = $Session


func _ready() -> void:
	ObserverLog.start()
	ObserverLog.info("main", "client_boot renderer=gl_compatibility")
	_session.status_changed.connect(_ui.show_status)
	_session.world_replaced.connect(_world.show_world)
	_ui.connect_requested.connect(_session.start_with_run_id)
	_session.begin()
