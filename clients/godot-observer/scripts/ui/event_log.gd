extends PanelContainer

const ObserverLog := preload("res://scripts/log.gd")

const MAX_LINES := 200
const BODY_SUBJECTS: Array[String] = ["AGENT_DIED", "NEEDS_APPLIED", "EXPOSURE_APPLIED"]

signal seek_requested(tick: int, sequence: int)

var lines: Array = []
var visible_lines: Array = []

var _world: Variant = null
var _filter_agent := ""
var _filter_type := ""
var _filter_location := ""
var _items: ItemList


func _ready() -> void:
	_items = $Column/Items
	_items.item_clicked.connect(_on_item_clicked)
	$Column/Filters/Agent.text_changed.connect(func(value: String) -> void: _set_filter("agent", value))
	$Column/Filters/Type.text_changed.connect(func(value: String) -> void: _set_filter("type", value))
	$Column/Filters/Location.text_changed.connect(func(value: String) -> void: _set_filter("location", value))


func set_world(world: Variant) -> void:
	_world = world
	var refreshed: Array = []
	for line in lines:
		refreshed.append(_record_from_line(line))
	lines = refreshed
	_render()


func replace_window(events: Array, focus_tick: int, focus_sequence: int) -> void:
	lines = []
	var kept := 0
	for event in events:
		if kept >= MAX_LINES:
			break
		lines.append(_record(event))
		kept += 1
	_sort_lines()
	_render()
	_focus(focus_tick, focus_sequence)
	ObserverLog.debug(
		"log_view",
		"window_replaced count=%s tick=%s sequence=%s" % [lines.size(), focus_tick, focus_sequence],
	)


func append_event(event: Variant) -> void:
	lines.append(_record(event))
	if lines.size() > MAX_LINES:
		lines = lines.slice(lines.size() - MAX_LINES, lines.size())
	ObserverLog.debug(
		"log_view",
		"line_appended tick=%s sequence=%s type=%s" % [int(event.tick), int(event.sequence), str(event.type)],
	)
	_sort_lines()
	_render()


func set_filters(agent: String, type_name: String, location: String) -> void:
	_filter_agent = agent.strip_edges()
	_filter_type = type_name.strip_edges()
	_filter_location = location.strip_edges()
	_render()
	ObserverLog.debug(
		"log_view",
		"filter_set agent=%s type=%s location=%s shown=%s" % [
			_filter_agent, _filter_type, _filter_location, visible_lines.size(),
		],
	)


func click_line(index: int) -> void:
	if index < 0 or index >= visible_lines.size():
		return
	var line: Dictionary = visible_lines[index]
	ObserverLog.debug(
		"log_view",
		"seek_clicked tick=%s sequence=%s" % [int(line["tick"]), int(line["sequence"])],
	)
	seek_requested.emit(int(line["tick"]), int(line["sequence"]))


func contains_type(type_name: String) -> bool:
	for line in lines:
		if str(line["type"]) == type_name:
			return true
	return false


func line_text(index: int) -> String:
	if index < 0 or index >= visible_lines.size():
		return ""
	return _format(visible_lines[index])


func _set_filter(kind: String, value: String) -> void:
	if kind == "agent":
		_filter_agent = value.strip_edges()
	elif kind == "type":
		_filter_type = value.strip_edges()
	else:
		_filter_location = value.strip_edges()
	_render()
	ObserverLog.debug(
		"log_view",
		"filter_set agent=%s type=%s location=%s shown=%s" % [
			_filter_agent, _filter_type, _filter_location, visible_lines.size(),
		],
	)


func _on_item_clicked(index: int, _at_position: Vector2, _mouse_button_index: int) -> void:
	click_line(index)


func _record(event: Variant) -> Dictionary:
	var type_name := str(event.type)
	var actor_id := "" if event.actor_id == null else str(event.actor_id)
	var target_id := "" if event.target_id == null else str(event.target_id)
	var origin_id := "" if event.origin_location_id == null else str(event.origin_location_id)
	var destination_id := "" if event.destination_location_id == null else str(event.destination_location_id)
	var actor := _agent_label(actor_id)
	var target := _agent_label(target_id)
	var origin := _location_name(origin_id)
	var destination := _location_name(destination_id)
	var subject := target if type_name in BODY_SUBJECTS else actor
	return {
		"tick": int(event.tick),
		"sequence": int(event.sequence),
		"type": type_name,
		"actor": actor,
		"target": target,
		"actor_id": actor_id,
		"target_id": target_id,
		"origin": origin,
		"destination": destination,
		"origin_id": origin_id,
		"destination_id": destination_id,
		"description": _describe(type_name, subject, actor, target, origin, destination),
	}


func _record_from_line(line: Dictionary) -> Dictionary:
	var actor := _agent_label(str(line.get("actor_id", "")))
	var target := _agent_label(str(line.get("target_id", "")))
	var origin := _location_name(str(line.get("origin_id", "")))
	var destination := _location_name(str(line.get("destination_id", "")))
	var type_name := str(line.get("type", ""))
	var subject := target if type_name in BODY_SUBJECTS else actor
	line["actor"] = actor
	line["target"] = target
	line["origin"] = origin
	line["destination"] = destination
	line["description"] = _describe(type_name, subject, actor, target, origin, destination)
	return line


func _describe(
	type_name: String,
	subject: String,
	actor: String,
	target: String,
	origin: String,
	destination: String,
) -> String:
	match type_name:
		"AGENT_MOVED":
			return "%s moved %s -> %s" % [subject, origin, destination]
		"AGENT_SEARCHED":
			return "%s searched %s" % [subject, origin]
		"AGENT_TOOK_ITEM":
			return "%s took" % subject
		"AGENT_DROPPED_ITEM":
			return "%s dropped" % subject
		"AGENT_GAVE_ITEM":
			return "%s gave" % subject
		"AGENT_ATE_ITEM":
			return "%s ate" % subject
		"AGENT_DRANK":
			return "%s drank" % subject
		"AGENT_SLEPT":
			return "%s slept" % subject
		"AGENT_TALKED":
			return "%s talked" % subject
		"AGENT_ASKED":
			return "%s asked" % subject
		"AGENT_TOLD":
			return "%s told" % subject
		"AGENT_HELPED":
			return "%s helped %s" % [actor, target]
		"AGENT_ATTACKED":
			return "%s attacked %s" % [actor, target]
		"AGENT_FLED":
			return "%s fled" % subject
		"AGENT_WAITED":
			return "%s waited" % subject
		"WEATHER_CHANGED":
			return "weather"
		"RESOURCE_REGENERATED":
			return "resource regenerated"
		"NEEDS_APPLIED":
			return "%s needs" % subject
		"EXPOSURE_APPLIED":
			return "%s exposure" % subject
		"AGENT_DIED":
			return "%s died" % subject
		_:
			return type_name


func _agent_label(entity_id: String) -> String:
	if entity_id == "":
		return ""
	if _world != null:
		for agent in _world.agents:
			if str(agent.entity_id) == entity_id and agent.agent_id != null and str(agent.agent_id) != "":
				return str(agent.agent_id)
	return entity_id


func _location_name(location_id: String) -> String:
	if location_id == "" or _world == null:
		return location_id
	for location in _world.locations:
		if str(location.location_id) != location_id:
			continue
		if str(location.display_name) != "":
			return str(location.display_name)
		return str(location.name)
	return location_id


func _matches(line: Dictionary) -> bool:
	if _filter_type != "" and str(line["type"]) != _filter_type:
		return false
	if _filter_agent != "":
		var needle := _filter_agent.to_lower()
		var hay := "%s %s %s %s" % [line["actor"], line["target"], line["actor_id"], line["target_id"]]
		if needle not in hay.to_lower():
			return false
	if _filter_location != "":
		var place := _filter_location.to_lower()
		var where := "%s %s %s %s" % [
			line["origin"], line["destination"], line["origin_id"], line["destination_id"],
		]
		if place not in where.to_lower():
			return false
	return true


func _sort_lines() -> void:
	lines.sort_custom(func(left: Dictionary, right: Dictionary) -> bool:
		if int(left["tick"]) == int(right["tick"]):
			return int(left["sequence"]) < int(right["sequence"])
		return int(left["tick"]) < int(right["tick"])
	)


func _render() -> void:
	visible_lines = []
	for line in lines:
		if _matches(line):
			visible_lines.append(line)
	if _items == null:
		return
	_items.clear()
	for line in visible_lines:
		_items.add_item(_format(line))


func _focus(event_tick: int, event_sequence: int) -> void:
	if _items == null:
		return
	for index in visible_lines.size():
		var line: Dictionary = visible_lines[index]
		if int(line["tick"]) == event_tick and int(line["sequence"]) == event_sequence:
			_items.select(index)
			_items.ensure_current_is_visible()
			return


func _format(line: Dictionary) -> String:
	return "%s:%s %s %s %s %s" % [
		line["tick"], line["sequence"], line["type"], line["actor"], line["target"], line["description"],
	]
