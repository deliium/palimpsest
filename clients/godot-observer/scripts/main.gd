extends Node

const ObserverLog := preload("res://scripts/log.gd")
const FixturePlayer := preload("res://scripts/net/fixture_player.gd")

@onready var _world: Node2D = $WorldView
@onready var _ui: CanvasLayer = $UILayer
@onready var _session: Node = $Session


func _ready() -> void:
	ObserverLog.start()
	ObserverLog.info("main", "client_boot renderer=gl_compatibility")
	_session.status_changed.connect(_ui.show_status)
	_session.world_replaced.connect(_world.show_world)
	_session.live_event.connect(_world.play_event)
	_session.live_event.connect(_ui.append_event)
	_world.inspect_requested.connect(_ui.show_inspector)
	_world.inspect_cleared.connect(_ui.clear_inspector)
	_ui.connect_requested.connect(_session.start_with_run_id)
	_ui.zoom_in_requested.connect(_world.zoom_in)
	_ui.zoom_out_requested.connect(_world.zoom_out)
	_ui.reset_requested.connect(_world.reset_view)
	_ui.focus_requested.connect(_world.focus_selected)
	_ui.speed_changed.connect(_world.set_playback_speed)
	_ui.play_fixture_requested.connect(_play_fixture)
	_session.begin()


func _play_fixture() -> void:
	FixturePlayer.play_into(_world, _ui.get_node("EventLog"))
