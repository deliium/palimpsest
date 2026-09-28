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
	_session.frame_sought.connect(_world.replace_sought_frame)
	_session.events_loaded.connect(_on_events_loaded)
	_session.run_loaded.connect(_on_run_loaded)
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
	_ui.speed_selected.connect(_session.set_speed)
	_ui.control_pressed.connect(_on_control)
	_ui.event_seek_requested.connect(_on_event_seek)
	_ui.timeline_seek_requested.connect(_on_event_seek)
	_ui.play_fixture_requested.connect(_play_fixture)
	_world.inspect_requested.connect(func(snapshot: Dictionary) -> void:
		_ui.note_selection(str(snapshot.get("entity_id", "")))
	)
	_world.inspect_cleared.connect(func() -> void: _ui.note_selection(""))
	_session.begin()


func _on_events_loaded(events: Array, focus_tick: int, focus_sequence: int) -> void:
	_ui.replace_events(events, focus_tick, focus_sequence, _session.world)


func _on_run_loaded(record: Dictionary) -> void:
	_ui.note_live_tick(int(record.get("tick", 0)))


func _on_event_seek(tick: int, sequence: int) -> void:
	_session.seek_event(tick, sequence, null)


func _on_control(action: String) -> void:
	match action:
		"play":
			_session.play()
		"pause":
			_session.pause()
		"previous_event":
			_session.previous_event()
		"next_event":
			_session.next_event()
		"previous_tick":
			_session.previous_tick()
		"next_tick":
			_session.next_tick()
		"jump_tick":
			_session.jump_to_tick(_ui.jump_tick_value())
		"jump_event":
			_session.jump_to_event(_ui.jump_tick_value(), _ui.jump_sequence_value())
		"return_live":
			_session.return_to_live()


func _play_fixture() -> void:
	FixturePlayer.play_into(_world, _ui.get_node("EventLog"))
