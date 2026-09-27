extends RefCounted

const ObserverLog := preload("res://scripts/log.gd")
const Protocol := preload("res://scripts/protocol/models.gd")
const ReducerScript := preload("res://scripts/protocol/reducer.gd")
const Playback := preload("res://scripts/protocol/playback.gd")

const PATH := "res://fixtures/smoke/reference_session.json"


static func load_document() -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(PATH))
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return parsed


static func playback_result(speed: float, event_log: Node = null) -> Dictionary:
	var document := load_document()
	var frame = Protocol.parse_frame(document.get("frame", {}))
	var reducer = ReducerScript.new()
	var world = frame.value.world
	var types: Array[String] = []
	var last_tick := 0
	var last_sequence := 0
	var policy: Dictionary = Playback.policy(speed, 4)
	var events: Array = document.get("events", [])
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
	}


static func play_into(world_view: Node, event_log: Node) -> void:
	var document := load_document()
	var events: Array = document.get("events", [])
	ObserverLog.info("fixture", "playback_started event_count=%s" % events.size())
	var frame = Protocol.parse_frame(document.get("frame", {}))
	if not frame.ok:
		ObserverLog.error("fixture", "playback_finished last_tick=0 last_sequence=0")
		return
	world_view.show_world(frame.value.world)
	var last_tick := 0
	var last_sequence := 0
	for raw in events:
		var parsed = Protocol.parse_event(raw)
		if parsed == null or not parsed.ok:
			continue
		event_log.append_event(parsed.value)
		world_view.play_event(parsed.value)
		last_tick = int(parsed.value.tick)
		last_sequence = int(parsed.value.sequence)
	ObserverLog.info(
		"fixture",
		"playback_finished last_tick=%s last_sequence=%s" % [last_tick, last_sequence],
	)
