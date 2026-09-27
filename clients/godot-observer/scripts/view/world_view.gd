extends Node2D

const Playback := preload("res://scripts/protocol/playback.gd")
const ReducerScript := preload("res://scripts/protocol/reducer.gd")
const Router := preload("res://scripts/protocol/event_router.gd")

var playback_speed := 1.0

var _world_state: Variant = null
var _centers := {}
var _reducer = ReducerScript.new()

@onready var _locations: Node2D = $LocationLayer
@onready var _connections: Node2D = $ConnectionLayer
@onready var _objects: Node2D = $ObjectLayer
@onready var _agents: Node2D = $AgentLayer
@onready var _effects: Node2D = $EffectsLayer
@onready var _camera: Camera2D = $Camera2D


func show_world(world: Variant) -> void:
	_world_state = world
	_locations.show_world(world)
	_centers = {}
	for location in world.locations:
		_centers[location.location_id] = _locations.zone_center(location.location_id)
	_connections.show_world(world, _centers)
	_objects.show_world(world, _centers)
	_agents.show_world(world, _centers, _reducer.activity)


func play_event(event: Variant) -> void:
	if _world_state == null or not bool(event.known):
		if event != null and not bool(event.known):
			_effects.play({"action": "unknown", "type": str(event.type), "event_id": str(event.event_id)}, _agents, _locations)
		return
	var pending: int = _agents.active_motions() + _effects.active_count()
	var policy: Dictionary = Playback.policy(playback_speed, pending)
	var logical: Dictionary = _reducer.apply_event(_world_state, event)
	var command: Dictionary = Router.route(event, policy, logical)
	_effects.play(command, _agents, _locations)


func set_playback_speed(speed: float) -> void:
	playback_speed = speed


func zoom_in() -> void:
	_camera.zoom_step(1.1)


func zoom_out() -> void:
	_camera.zoom_step(0.9)


func reset_view() -> void:
	var selected: Variant = _agents.selected_position()
	var target: Vector2 = _centroid() if selected == null else selected
	_camera.reset_to(target)


func focus_selected() -> void:
	var selected: Variant = _agents.selected_position()
	if selected == null:
		return
	_camera.focus_on(selected)


func _centroid() -> Vector2:
	if _centers.is_empty():
		return Vector2.ZERO
	var total := Vector2.ZERO
	for location_id in _centers.keys():
		total += _centers[location_id]
	return total / float(_centers.size())
