extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
const Slots := preload("res://scripts/protocol/slots.gd")
const Scale := preload("res://scripts/presentation/scale.gd")
const Identity := preload("res://scripts/presentation/identity.gd")
const TokenScene := preload("res://scenes/layers/agent_token.tscn")
const MotionPath := preload("res://scripts/view/motion_path.gd")

signal agent_selected(entity_id: String)
signal selection_cleared

var selected_entity_id := ""
var _tokens := {}
var _motions := 0
var _world: Variant = null
var _centers := {}


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)


func show_world(world: Variant, zone_centers: Dictionary = {}, activity: Dictionary = {}) -> void:
	_world = world
	_centers = zone_centers
	for child in get_children():
		child.queue_free()
	_tokens = {}
	_motions = 0
	var grouped := {}
	for agent in world.agents:
		var bucket: Array = grouped.get(agent.location_id, [])
		bucket.append(agent)
		grouped[agent.location_id] = bucket
	for location_id in grouped.keys():
		var agents: Array = grouped[location_id]
		agents.sort_custom(func(left, right) -> bool: return str(left.entity_id) < str(right.entity_id))
		var location = _location(location_id)
		var bounds = null if location == null or location.presentation == null else location.presentation.visual_bounds
		for index in agents.size():
			var agent = agents[index]
			var placed: Dictionary = Slots.display_position(agent.presentation_slot, bounds, index)
			if bool(placed["fallback"]):
				ObserverLog.debug(
					"agents",
					"slot_fallback entity_id=%s slot_index=%s" % [agent.entity_id, index],
				)
			var token = TokenScene.instantiate()
			token.position = Scale.to_pixels(float(placed["x"]), float(placed["y"]))
			token.setup(agent, Identity.label_for(agent))
			token.set_activity(str(activity.get(str(agent.entity_id), "")))
			add_child(token)
			_tokens[str(agent.entity_id)] = token
	ObserverLog.debug("agents", "tokens_built agent_count=%s" % _tokens.size())


func active_motions() -> int:
	return _motions


func clear_motions() -> void:
	for entity_id in _tokens.keys():
		var token = _tokens[entity_id]
		if token.has_meta("motion"):
			var motion: Tween = token.get_meta("motion")
			if motion != null and motion.is_valid():
				motion.kill()
	_motions = 0


func clear_tokens() -> void:
	clear_motions()
	for child in get_children():
		child.queue_free()
	_tokens = {}
	_world = null
	_centers = {}
	if selected_entity_id != "":
		selected_entity_id = ""
		selection_cleared.emit()
	ObserverLog.debug("agents", "tokens_cleared")


func capture_positions() -> Dictionary:
	var positions := {}
	for entity_id in _tokens.keys():
		positions[str(entity_id)] = _tokens[entity_id].position
	return positions


func restore_position(entity_id: String, point: Vector2) -> void:
	if _tokens.has(entity_id):
		_tokens[entity_id].position = point


static func selection_for(selected_id: String, agents: Array) -> Dictionary:
	for agent in agents:
		if str(agent.entity_id) == selected_id:
			return {"keep": true, "dead": str(agent.life_status) == "dead"}
	return {"keep": false, "dead": false}


func token_position(entity_id: String) -> Variant:
	if entity_id.is_empty() or not _tokens.has(entity_id):
		return null
	return _tokens[entity_id].position


func highlight(entity_id: String) -> bool:
	selected_entity_id = entity_id
	var found := false
	for token_id in _tokens.keys():
		var selected := str(token_id) == entity_id
		_tokens[token_id].set_selected(selected)
		if selected:
			found = true
	if not found:
		selected_entity_id = ""
	return found


func selected_position() -> Variant:
	if selected_entity_id == "" or not _tokens.has(selected_entity_id):
		return null
	return _tokens[selected_entity_id].position


func set_activity(entity_id: String, text: String) -> void:
	if _tokens.has(entity_id):
		_tokens[entity_id].set_activity(text)


func set_dead(entity_id: String) -> void:
	if _tokens.has(entity_id):
		_tokens[entity_id].set_dead(true)


func move_token(entity_id: String, destination: Vector2, duration: float, skip: bool, speed: float, origin: String, dest_id: String, path: PackedVector2Array = PackedVector2Array()) -> void:
	if not _tokens.has(entity_id):
		return
	var token = _tokens[entity_id]
	if token.has_meta("motion"):
		var previous: Tween = token.get_meta("motion")
		if previous != null and previous.is_valid():
			previous.kill()
		_motions = maxi(_motions - 1, 0)
	if skip:
		token.position = destination
		ObserverLog.debug(
			"motion",
			"move_snapped entity_id=%s reason_code=playback_speed" % entity_id,
		)
		return
	var points: PackedVector2Array = path
	if points.size() < 2:
		points = MotionPath.straight(token.position, destination)
	var path_kind := "direct"
	if points.size() > 2:
		path_kind = "connection"
	_motions += 1
	ObserverLog.debug(
		"motion",
		"move_started entity_id=%s origin=%s destination=%s speed=%s" % [entity_id, origin, dest_id, speed],
	)
	ObserverLog.debug("motion", "move_path entity_id=%s path_kind=%s" % [entity_id, path_kind])
	token.set_meta("path", points)
	var tween := create_tween()
	token.set_meta("motion", tween)
	tween.tween_method(
		func(weight: float) -> void:
			var captured: PackedVector2Array = token.get_meta("path")
			token.position = MotionPath.sample(captured, weight),
		0.0,
		1.0,
		duration,
	)
	tween.finished.connect(func() -> void:
		_motions = maxi(_motions - 1, 0)
	)


func slot_for(entity_id: String) -> Vector2:
	if _world == null:
		return Vector2.ZERO
	var agent = null
	for candidate in _world.agents:
		if str(candidate.entity_id) == entity_id:
			agent = candidate
			break
	if agent == null:
		return token_position(entity_id)
	var occupants: Array = []
	for candidate in _world.agents:
		if str(candidate.location_id) == str(agent.location_id):
			occupants.append(candidate)
	occupants.sort_custom(func(left, right) -> bool: return str(left.entity_id) < str(right.entity_id))
	var index := 0
	for offset in occupants.size():
		if str(occupants[offset].entity_id) == entity_id:
			index = offset
			break
	var location = _location(str(agent.location_id))
	var bounds = null if location == null or location.presentation == null else location.presentation.visual_bounds
	var placed: Dictionary = Slots.display_position(agent.presentation_slot, bounds, index)
	return Scale.to_pixels(float(placed["x"]), float(placed["y"]))


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	var mouse := event as InputEventMouseButton
	if not mouse.pressed or mouse.button_index != MOUSE_BUTTON_LEFT:
		return
	var world_position := get_global_mouse_position()
	for entity_id in _tokens.keys():
		var token = _tokens[entity_id]
		if token.global_position.distance_to(world_position) <= 16.0:
			selected_entity_id = str(entity_id)
			ObserverLog.debug("agents", "selected entity_id=%s" % selected_entity_id)
			agent_selected.emit(selected_entity_id)
			get_viewport().set_input_as_handled()
			return
	if selected_entity_id != "":
		selected_entity_id = ""
		selection_cleared.emit()


func _location(location_id: String) -> Variant:
	if _world == null:
		return null
	for location in _world.locations:
		if str(location.location_id) == location_id:
			return location
	return null
