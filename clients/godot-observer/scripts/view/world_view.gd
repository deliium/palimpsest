extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
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

signal inspect_requested(snapshot: Dictionary)
signal inspect_cleared


func _ready() -> void:
	_agents.agent_selected.connect(_on_agent_selected)
	_agents.selection_cleared.connect(func() -> void: inspect_cleared.emit())


func replace_sought_frame(frame: Variant, event: Variant, forward: bool) -> void:
	var prior: Dictionary = _agents.capture_positions()
	var selected := _agents.selected_entity_id
	_agents.clear_motions()
	_effects.clear_motions()
	ObserverLog.debug("view", "motions_cleared")
	show_world(frame.world)
	if selected == "":
		_maybe_tween(event, forward, prior)
		return
	var choice: Dictionary = _agents.selection_for(selected, frame.world.agents)
	if not bool(choice.get("keep", false)) or not _agents.highlight(selected):
		inspect_cleared.emit()
		_maybe_tween(event, forward, prior)
		return
	_on_agent_selected(selected)
	_maybe_tween(event, forward, prior)


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
	var ground: Vector2 = _item_ground(event)
	var logical: Dictionary = _reducer.apply_event(_world_state, event)
	var command: Dictionary = Router.route(event, policy, logical)
	command["ground"] = ground
	_effects.play(command, _agents, _locations, _connections, _objects)


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


func _maybe_tween(event: Variant, forward: bool, prior: Dictionary) -> void:
	if event == null or not forward or not bool(event.known):
		return
	var pending: int = _agents.active_motions() + _effects.active_count()
	var policy: Dictionary = Playback.policy(playback_speed, pending)
	if bool(policy.get("skip", false)):
		return
	var body := ""
	if event.has_method("affected_entity_id"):
		var affected: Variant = event.affected_entity_id()
		body = "" if affected == null else str(affected)
	var logical := {
		"entity_id": body,
		"origin": "" if event.origin_location_id == null else str(event.origin_location_id),
		"destination": "" if event.destination_location_id == null else str(event.destination_location_id),
		"moved": str(event.type) == "AGENT_MOVED" or str(event.type) == "AGENT_FLED",
	}
	var command: Dictionary = Router.route(event, policy, logical)
	command["ground"] = _item_ground(event)
	if str(command.get("action", "")) == "move" and body != "" and prior.has(body):
		_agents.restore_position(body, prior[body])
	_effects.play(command, _agents, _locations, _connections, _objects)


func _on_agent_selected(entity_id: String) -> void:
	if _world_state == null:
		return
	var agent = null
	for candidate in _world_state.agents:
		if str(candidate.entity_id) == entity_id:
			agent = candidate
			break
	if agent == null:
		return
	var location_name := entity_id
	for location in _world_state.locations:
		if str(location.location_id) == str(agent.location_id):
			location_name = str(location.display_name) if str(location.display_name) != "" else str(location.name)
			break
	var inventory: Array[String] = []
	for item_id in agent.inventory_ids:
		var summary := str(item_id)
		for item in _world_state.items:
			if str(item.item_id) == str(item_id):
				summary = "%s (%s)" % [item.name, item.kind]
				break
		inventory.append(summary)
	inspect_requested.emit({
		"entity_id": str(agent.entity_id),
		"agent_id": "" if agent.agent_id == null else str(agent.agent_id),
		"location_name": location_name,
		"life_status": str(agent.life_status),
		"inventory": inventory,
		"latest_event": _reducer.activity_for(entity_id),
		"measures": agent.measures,
	})


func _item_ground(event: Variant) -> Vector2:
	var type_name := str(event.type)
	if type_name != "AGENT_TOOK_ITEM" and type_name != "AGENT_DROPPED_ITEM":
		return Vector2.ZERO
	var location_id := ""
	if type_name == "AGENT_TOOK_ITEM":
		location_id = _item_location(event.item_id)
		if location_id == "" and event.origin_location_id != null:
			location_id = str(event.origin_location_id)
	elif event.destination_location_id != null:
		location_id = str(event.destination_location_id)
	elif event.origin_location_id != null:
		location_id = str(event.origin_location_id)
	if location_id == "":
		return Vector2.ZERO
	var item_id := "" if event.item_id == null else str(event.item_id)
	return _objects.ground_point(location_id, item_id)


func _item_location(item_id: Variant) -> String:
	if item_id == null or _world_state == null:
		return ""
	for item in _world_state.items:
		if str(item.item_id) == str(item_id) and item.location_id != null:
			return str(item.location_id)
	return ""


func _centroid() -> Vector2:
	if _centers.is_empty():
		return Vector2.ZERO
	var total := Vector2.ZERO
	for location_id in _centers.keys():
		total += _centers[location_id]
	return total / float(_centers.size())
