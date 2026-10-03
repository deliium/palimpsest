extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
const MotionPath := preload("res://scripts/view/motion_path.gd")
const ItemTravel := preload("res://scripts/view/item_travel.gd")

const _SPEECH_CAP := 8
const _COALESCE_WINDOW := 0.12

var _marks: Array = []
var _bubbles: Array = []
var _objects: Node = null
var _strategy_by_event := {}
var _research_speech := false
var _coalesce_keys := {}
var effects_coalesced := 0
var speech_dropped := 0


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)


func active_count() -> int:
	return _marks.size() + _bubbles.size()


func set_strategy_audit(payload: Variant) -> void:
	_strategy_by_event = {}
	if typeof(payload) != TYPE_DICTIONARY:
		return
	for entry in payload.get("entries", []):
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		_strategy_by_event[str(entry.get("event_id", ""))] = str(entry.get("category", ""))


func set_research_speech_enabled(enabled: bool) -> void:
	## Research labels stay off the ordinary bubble path even when payload is loaded.
	_research_speech = enabled


func clear_motions() -> void:
	if _objects != null:
		for mark in _marks:
			if str(mark.get("action", "")) == "item":
				_objects.release_item(str(mark.get("item_id", "")))
	_marks.clear()
	_bubbles.clear()
	_coalesce_keys.clear()
	queue_redraw()


func play(command: Dictionary, agents: Node, locations: Node, connections: Node = null, objects: Node = null) -> void:
	if objects != null:
		_objects = objects
	var action := str(command.get("action", ""))
	var type_name := str(command.get("type", ""))
	var event_id := str(command.get("event_id", ""))
	var entity_id := str(command.get("entity_id", ""))
	var skip := bool(command.get("skip", false))
	if action == "unknown":
		ObserverLog.warn("effects", "unknown_event type=%s event_id=%s" % [type_name, event_id])
		return
	if action == "died":
		agents.set_dead(entity_id)
	if entity_id != "":
		agents.set_activity(entity_id, type_name)
	if action == "move":
		var destination: Vector2 = agents.slot_for(entity_id)
		var path := PackedVector2Array()
		if not skip:
			path = _move_path(command, agents.token_position(entity_id), destination, connections)
		agents.move_token(
			entity_id,
			destination,
			float(command.get("duration", 0.6)),
			skip,
			float(command.get("speed", 1.0)),
			str(command.get("origin", "")),
			str(command.get("destination", "")),
			path,
		)
	if skip and action != "died":
		if action == "item":
			ObserverLog.debug(
				"motion",
				"item_snapped type=%s item_id=%s reason_code=playback_speed" % [type_name, str(command.get("item_id", ""))],
			)
			if _objects != null:
				_objects.queue_redraw()
		ObserverLog.debug("effects", "effect_skipped type=%s reason_code=playback_speed" % type_name)
		return
	if action in ["harvest", "craft", "build", "repair", "store", "activity", "search"]:
		var coalesce_key := "%s|%s" % [entity_id, action]
		var now := Time.get_ticks_msec() / 1000.0
		if _coalesce_keys.has(coalesce_key) and now - float(_coalesce_keys[coalesce_key]) < _COALESCE_WINDOW:
			effects_coalesced += 1
			ObserverLog.debug("effects", "effects_coalesced count=%s" % effects_coalesced)
			return
		_coalesce_keys[coalesce_key] = now
	ObserverLog.debug("effects", "played type=%s event_id=%s" % [type_name, event_id])
	if action == "move":
		return
	if action == "speech":
		var band := str(command.get("declared_confidence_band", ""))
		var text := "%s %s" % [type_name, str(command.get("other_id", ""))]
		if band != "":
			text = "%s [%s]" % [text, band]
		# Ordinary bubbles never read research audit categories, even if loaded.
		_show_bubble(
			agents,
			entity_id,
			text,
			float(command.get("speech_duration", 2.0)),
			type_name,
			event_id,
		)
		return
	if action == "item":
		_show_item(command, agents)
		return
	var point := _point_for(action, command, agents, locations)
	_marks.append({
		"action": action,
		"point": point,
		"target": _target_point(command, agents),
		"life": maxf(float(command.get("duration", 0.35)), 0.25),
		"age": 0.0,
	})
	queue_redraw()


func _process(delta: float) -> void:
	if _marks.is_empty() and _bubbles.is_empty():
		return
	var kept: Array = []
	for mark in _marks:
		mark["age"] = float(mark["age"]) + delta
		if float(mark["age"]) < float(mark["life"]):
			kept.append(mark)
		elif str(mark.get("action", "")) == "item" and _objects != null:
			_objects.release_item(str(mark.get("item_id", "")))
	_marks = kept
	var bubbles: Array = []
	for bubble in _bubbles:
		bubble["age"] = float(bubble["age"]) + delta
		if float(bubble["age"]) < float(bubble["life"]):
			bubbles.append(bubble)
	_bubbles = bubbles
	queue_redraw()


func _draw() -> void:
	for mark in _marks:
		var point: Vector2 = mark["point"]
		var action := str(mark["action"])
		var alpha := 1.0 - float(mark["age"]) / float(mark["life"])
		var color := Color(0.95, 0.9, 0.7, alpha)
		match action:
			"search", "weather", "resource", "artifact", "harvest":
				draw_arc(point, 18.0 + float(mark["age"]) * 24.0, 0, TAU, 24, color, 2.0)
			"craft":
				draw_arc(point, 12.0 + float(mark["age"]) * 18.0, 0, TAU, 20, Color(0.85, 0.7, 0.35, alpha), 2.0)
				draw_circle(point, 3.0, Color(0.95, 0.85, 0.45, alpha))
			"build", "repair":
				draw_rect(
					Rect2(point - Vector2(8, 8), Vector2(16, 16)),
					Color(0.7, 0.58, 0.4, alpha),
					false,
					2.0,
				)
			"store":
				draw_circle(point, 5.0 + float(mark["age"]) * 8.0, Color(0.75, 0.7, 0.45, alpha * 0.7))
			"consume", "drink", "rest":
				draw_circle(point + Vector2(0, -18), 6.0, color)
			"strike":
				draw_line(point, mark["target"], Color(0.9, 0.35, 0.3, alpha), 2.0)
			"link":
				draw_line(point, mark["target"], Color(0.45, 0.8, 0.55, alpha), 2.0)
			"item":
				var origin_point: Vector2 = mark["from"]
				var dest_point: Vector2 = mark["to"]
				var traveled: Vector2 = origin_point.lerp(dest_point, clampf(float(mark["age"]) / float(mark["life"]), 0.0, 1.0))
				draw_rect(Rect2(traveled - Vector2(5, 5), Vector2(10, 10)), Color(0.86, 0.72, 0.38, alpha), true)
			_:
				draw_circle(point, 4.0, color)
	var font := ThemeDB.fallback_font
	for bubble in _bubbles:
		var origin: Vector2 = bubble["point"]
		var fill := _speech_color(str(bubble.get("speech_type", "")))
		draw_rect(Rect2(origin + Vector2(-8, -36), Vector2(168, 22)), fill, true)
		draw_string(font, origin + Vector2(-4, -20), str(bubble["text"]), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.95, 0.95, 0.9))
		if _research_speech:
			var category := str(bubble.get("research_category", ""))
			if category != "":
				ObserverLog.debug(
					"speech",
					"strategy_meta event_id=%s category=%s" % [
						str(bubble.get("event_id", "")),
						category,
					],
				)
				draw_string(
					font,
					origin + Vector2(-4, -48),
					"ANALYTICAL %s" % category,
					HORIZONTAL_ALIGNMENT_LEFT,
					-1,
					11,
					Color(0.7, 0.72, 0.9),
				)


func _speech_color(speech_type: String) -> Color:
	match speech_type:
		"AGENT_ASKED":
			return Color(0.12, 0.18, 0.28, 0.88)
		"AGENT_TOLD":
			return Color(0.22, 0.14, 0.18, 0.88)
		_:
			return Color(0.1, 0.12, 0.14, 0.85)


func _show_bubble(
	agents: Node,
	entity_id: String,
	text: String,
	life: float,
	speech_type: String = "",
	event_id: String = "",
) -> void:
	ObserverLog.debug("speech", "speech_shown type=%s actor_id=%s" % [speech_type, entity_id])
	while _bubbles.size() >= _SPEECH_CAP:
		_bubbles.pop_front()
		speech_dropped += 1
		ObserverLog.debug("effects", "speech_dropped count=%s" % speech_dropped)
	var research_category := ""
	if _research_speech and event_id != "" and _strategy_by_event.has(event_id):
		research_category = str(_strategy_by_event[event_id])
	_bubbles.append({
		"point": agents.token_position(entity_id),
		"text": text,
		"life": life,
		"age": 0.0,
		"speech_type": speech_type,
		"event_id": event_id,
		"research_category": research_category,
	})
	queue_redraw()


func _move_path(command: Dictionary, start: Vector2, finish: Vector2, connections: Node) -> PackedVector2Array:
	if connections != null and connections.has_method("segment"):
		var linked: Dictionary = connections.segment(str(command.get("origin", "")), str(command.get("destination", "")))
		if bool(linked.get("drawn", false)):
			return MotionPath.along_connection(start, linked["from"], linked["to"], finish)
	return MotionPath.straight(start, finish)


func _show_item(command: Dictionary, agents: Node) -> void:
	var type_name := str(command.get("type", ""))
	var item_id := str(command.get("item_id", ""))
	var actor: Vector2 = agents.token_position(str(command.get("entity_id", "")))
	var target: Vector2 = _target_point(command, agents)
	var ground: Vector2 = command.get("ground", Vector2.ZERO)
	var travel: Dictionary = ItemTravel.endpoints(type_name, actor, target, ground)
	if _objects != null:
		_objects.hold_item(item_id)
	ObserverLog.debug("motion", "item_started type=%s item_id=%s" % [type_name, item_id])
	_marks.append({
		"action": "item",
		"from": travel["from"],
		"to": travel["to"],
		"item_id": item_id,
		"point": travel["from"],
		"target": travel["to"],
		"life": maxf(float(command.get("duration", 0.6)), 0.05),
		"age": 0.0,
	})
	queue_redraw()


func _point_for(action: String, command: Dictionary, agents: Node, locations: Node) -> Vector2:
	if action in ["search", "weather"]:
		return locations.zone_center(str(command.get("location_id", command.get("origin", ""))))
	if action in ["resource", "artifact", "harvest", "build", "repair", "store"]:
		var location_id := str(command.get("location_id", command.get("origin", "")))
		if location_id != "":
			return locations.zone_center(location_id)
	if action == "craft":
		return agents.token_position(str(command.get("entity_id", "")))
	return agents.token_position(str(command.get("entity_id", "")))


func _target_point(command: Dictionary, agents: Node) -> Vector2:
	var other := str(command.get("other_id", ""))
	if other == "":
		return agents.token_position(str(command.get("entity_id", "")))
	return agents.token_position(other)
