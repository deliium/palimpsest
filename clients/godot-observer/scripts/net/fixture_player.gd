extends RefCounted

const ObserverLog := preload("res://scripts/log.gd")
const Protocol := preload("res://scripts/protocol/models.gd")
const ReducerScript := preload("res://scripts/protocol/reducer.gd")
const Playback := preload("res://scripts/protocol/playback.gd")

const PATH := "res://fixtures/smoke/reference_session.json"
const V2_PATH := "res://fixtures/smoke/v2_mechanics.json"


static func load_document(path: String = PATH) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return parsed


static func _resolve_frame(document: Dictionary) -> Variant:
	var frame_value: Variant = document.get("frame", {})
	if typeof(frame_value) == TYPE_STRING:
		var nested: Variant = JSON.parse_string(FileAccess.get_file_as_string(str(frame_value)))
		if typeof(nested) != TYPE_DICTIONARY:
			return null
		return Protocol.parse_frame(nested)
	if typeof(frame_value) == TYPE_DICTIONARY:
		return Protocol.parse_frame(frame_value)
	return null


static func _resolve_events(document: Dictionary) -> Array:
	var raw_events: Variant = document.get("events", [])
	if typeof(raw_events) != TYPE_ARRAY:
		return []
	var events: Array = []
	for entry in raw_events:
		if typeof(entry) == TYPE_DICTIONARY:
			events.append(entry)
			continue
		if typeof(entry) != TYPE_STRING:
			continue
		var nested: Variant = JSON.parse_string(FileAccess.get_file_as_string(str(entry)))
		if typeof(nested) == TYPE_DICTIONARY:
			events.append(nested)
	return events


static func playback_result(speed: float, event_log: Node = null, path: String = PATH) -> Dictionary:
	var document := load_document(path)
	var frame = _resolve_frame(document)
	if frame == null or not frame.ok:
		return {
			"location_id": "",
			"types": [],
			"skip": bool(Playback.policy(speed, 4)["skip"]),
			"last_tick": 0,
			"last_sequence": 0,
			"event_count": 0,
			"pack": str(document.get("pack", "")),
		}
	var reducer = ReducerScript.new()
	var world = frame.value.world
	var types: Array[String] = []
	var last_tick := 0
	var last_sequence := 0
	var policy: Dictionary = Playback.policy(speed, 4)
	var events: Array = _resolve_events(document)
	for raw in events:
		var parsed = Protocol.parse_event(raw)
		if parsed == null or not parsed.ok:
			continue
		types.append(str(parsed.value.type))
		if event_log != null:
			event_log.append_event(parsed.value)
		if bool(parsed.value.known):
			reducer.apply_event(world, parsed.value)
		last_tick = int(parsed.value.tick)
		last_sequence = int(parsed.value.sequence)
	var location := ""
	if world.agents.size() > 0:
		location = str(world.agents[0].location_id)
	return {
		"location_id": location,
		"types": types,
		"skip": bool(policy["skip"]),
		"last_tick": last_tick,
		"last_sequence": last_sequence,
		"event_count": events.size(),
		"pack": str(document.get("pack", "")),
		"overlays": document.get("overlays", {}),
	}


static func play_into(world_view: Node, event_log: Node, path: String = PATH) -> void:
	var document := load_document(path)
	var pack := str(document.get("pack", "reference_session"))
	var events: Array = _resolve_events(document)
	ObserverLog.info(
		"fixture",
		"fixture_pack_applied pack=%s event_count=%s" % [pack, events.size()],
	)
	var frame = _resolve_frame(document)
	if frame == null or not frame.ok:
		ObserverLog.error("fixture", "playback_finished last_tick=0 last_sequence=0")
		return
	world_view.show_world(frame.value.world)
	var last_tick := 0
	var last_sequence := 0
	var type_counts := {}
	for raw in events:
		var parsed = Protocol.parse_event(raw)
		if parsed == null or not parsed.ok:
			continue
		var type_name := str(parsed.value.type)
		type_counts[type_name] = int(type_counts.get(type_name, 0)) + 1
		event_log.append_event(parsed.value)
		world_view.play_event(parsed.value)
		last_tick = int(parsed.value.tick)
		last_sequence = int(parsed.value.sequence)
	ObserverLog.debug("fixture", "event_counts pack=%s counts=%s" % [pack, str(type_counts)])
	ObserverLog.info(
		"fixture",
		"playback_finished last_tick=%s last_sequence=%s" % [last_tick, last_sequence],
	)


static func play_v2_into(world_view: Node, event_log: Node) -> void:
	play_into(world_view, event_log, V2_PATH)
