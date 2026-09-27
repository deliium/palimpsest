extends Node2D

const ObserverLog := preload("res://scripts/log.gd")

var _marks: Array = []
var _bubbles: Array = []


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)


func active_count() -> int:
	return _marks.size() + _bubbles.size()


func play(command: Dictionary, agents: Node, locations: Node) -> void:
	var action := str(command.get("action", ""))
	var type_name := str(command.get("type", ""))
	var event_id := str(command.get("event_id", ""))
	var entity_id := str(command.get("entity_id", ""))
	if action == "unknown":
		ObserverLog.warn("effects", "unknown_event type=%s event_id=%s" % [type_name, event_id])
		return
	if action == "died":
		agents.set_dead(entity_id)
	if entity_id != "":
		agents.set_activity(entity_id, type_name)
	if action == "move":
		var destination: Vector2 = agents.slot_for(entity_id)
		agents.move_token(
			entity_id,
			destination,
			float(command.get("duration", 0.6)),
			bool(command.get("skip", false)),
			float(command.get("speed", 1.0)),
			str(command.get("origin", "")),
			str(command.get("destination", "")),
		)
	if bool(command.get("skip", false)) and action != "died":
		ObserverLog.debug("effects", "effect_skipped type=%s reason_code=playback_speed" % type_name)
		return
	ObserverLog.debug("effects", "played type=%s event_id=%s" % [type_name, event_id])
	if action == "move":
		return
	if action == "speech":
		_show_bubble(agents, entity_id, "%s %s" % [type_name, str(command.get("other_id", ""))], float(command.get("speech_duration", 2.0)))
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
			"search", "weather", "resource":
				draw_arc(point, 18.0 + float(mark["age"]) * 24.0, 0, TAU, 24, color, 2.0)
			"consume", "drink", "rest":
				draw_circle(point + Vector2(0, -18), 6.0, color)
			"strike":
				draw_line(point, mark["target"], Color(0.9, 0.35, 0.3, alpha), 2.0)
			"link":
				draw_line(point, mark["target"], Color(0.45, 0.8, 0.55, alpha), 2.0)
			"item":
				draw_rect(Rect2(point - Vector2(4, 4), Vector2(8, 8)), color, true)
			_:
				draw_circle(point, 4.0, color)
	var font := ThemeDB.fallback_font
	for bubble in _bubbles:
		var origin: Vector2 = bubble["point"]
		draw_rect(Rect2(origin + Vector2(-8, -36), Vector2(160, 22)), Color(0.1, 0.12, 0.14, 0.85), true)
		draw_string(font, origin + Vector2(-4, -20), str(bubble["text"]), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.95, 0.95, 0.9))


func _show_bubble(agents: Node, entity_id: String, text: String, life: float) -> void:
	ObserverLog.debug("speech", "bubble_shown type=%s actor_id=%s" % [text.get_slice(" ", 0), entity_id])
	_bubbles.append({
		"point": agents.token_position(entity_id),
		"text": text,
		"life": life,
		"age": 0.0,
	})
	queue_redraw()


func _point_for(action: String, command: Dictionary, agents: Node, locations: Node) -> Vector2:
	if action in ["search", "weather"]:
		return locations.zone_center(str(command.get("location_id", command.get("origin", ""))))
	if action == "resource":
		return locations.zone_center(str(command.get("location_id", "")))
	return agents.token_position(str(command.get("entity_id", "")))


func _target_point(command: Dictionary, agents: Node) -> Vector2:
	var other := str(command.get("other_id", ""))
	if other == "":
		return agents.token_position(str(command.get("entity_id", "")))
	return agents.token_position(other)
