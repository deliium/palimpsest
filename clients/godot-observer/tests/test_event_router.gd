extends RefCounted

const Protocol := preload("res://scripts/protocol/models.gd")
const ReducerScript := preload("res://scripts/protocol/reducer.gd")
const Router := preload("res://scripts/protocol/event_router.gd")
const Playback := preload("res://scripts/protocol/playback.gd")

const _ENVIRONMENT_TYPES: Array[String] = [
	"SEASON_CHANGED",
	"TEMPERATURE_BAND_CHANGED",
	"RESOURCE_NODE_DEPLETED",
	"RESOURCE_NODE_RECOVERED",
	"ENVIRONMENTAL_HAZARD_STARTED",
	"ENVIRONMENTAL_HAZARD_ENDED",
]

const _ARTIFACT_TYPES: Array[String] = [
	"ARTIFACT_CREATED",
	"ARTIFACT_MODIFIED",
	"ARTIFACT_MOVED",
	"ARTIFACT_DESTROYED",
]


func run() -> Array:
	var failures: Array = []
	var frame = Protocol.parse_text("frame", FileAccess.get_file_as_string("res://fixtures/protocol/reference_frame.json"))
	if not frame.ok:
		return ["frame did not parse"]
	var world = frame.value.world
	var reducer = ReducerScript.new()
	var play: Dictionary = Playback.policy(1.0, 0)
	var last_location := str(world.agents[0].location_id)
	for type_name in Protocol.KNOWN_TYPES:
		if type_name in _ENVIRONMENT_TYPES or type_name in _ARTIFACT_TYPES:
			continue
		var text := FileAccess.get_file_as_string("res://fixtures/protocol/events/%s.json" % type_name)
		var parsed = Protocol.parse_text("event", text)
		if not parsed.ok or not parsed.value.known:
			failures.append("fixture not known %s" % type_name)
			continue
		var logical: Dictionary = reducer.apply_event(world, parsed.value)
		var command: Dictionary = Router.route(parsed.value, play, logical)
		if command["action"] == "unknown":
			failures.append("closed type treated as unknown %s" % type_name)
		if logical["moved"]:
			last_location = str(world.agents[0].location_id)
	for type_name in _ENVIRONMENT_TYPES:
		var parsed_environment = Protocol.parse_event({
			"protocol_version": Protocol.PROTOCOL_VERSION,
			"type": type_name,
			"event_id": "evt-%s" % type_name,
			"tick": 9,
			"sequence": 0,
		})
		if not parsed_environment.ok or not parsed_environment.value.known:
			failures.append("environment type should be known %s" % type_name)
			continue
		var environment_logical: Dictionary = reducer.apply_event(world, parsed_environment.value)
		var environment_command: Dictionary = Router.route(parsed_environment.value, play, environment_logical)
		if environment_command["action"] == "unknown":
			failures.append("environment type treated as unknown %s" % type_name)
	for type_name in _ARTIFACT_TYPES:
		var parsed_artifact = Protocol.parse_event({
			"protocol_version": Protocol.PROTOCOL_VERSION,
			"type": type_name,
			"event_id": "evt-%s" % type_name,
			"tick": 9,
			"sequence": 0,
			"artifact_id": "art-1",
		})
		if not parsed_artifact.ok or not parsed_artifact.value.known:
			failures.append("artifact type should be known %s" % type_name)
			continue
		var artifact_logical: Dictionary = reducer.apply_event(world, parsed_artifact.value)
		var artifact_command: Dictionary = Router.route(parsed_artifact.value, play, artifact_logical)
		if artifact_command["action"] != "artifact":
			failures.append("artifact type should route as artifact %s" % type_name)
	var unknown = Protocol.parse_event({"type": "RESOURCE_FOUND", "event_id": "evt-unknown", "tick": 9, "sequence": 0})
	var before := str(world.agents[0].location_id)
	var unknown_logical: Dictionary = reducer.apply_event(world, unknown.value)
	var unknown_command: Dictionary = Router.route(unknown.value, play, unknown_logical)
	if unknown_command["action"] != "unknown" or unknown_command["moves_location"]:
		failures.append("unknown event changed motion")
	if str(world.agents[0].location_id) != before or before != last_location:
		failures.append("unknown event changed the last location")
	var died = Protocol.parse_event({
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"type": "AGENT_DIED",
		"domain_kind": "died",
		"event_id": "evt-died-route",
		"tick": 9,
		"sequence": 1,
		"target_id": "body-ada",
	})
	var died_logical: Dictionary = reducer.apply_event(world, died.value)
	if died_logical["entity_id"] != "body-ada" or str(world.agents[0].life_status) != "dead":
		failures.append("death should use target_id")
	var skip: Dictionary = Playback.policy(8.0, 1)
	var moved = Protocol.parse_event({
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"type": "AGENT_MOVED",
		"domain_kind": "move",
		"event_id": "evt-skip",
		"tick": 10,
		"sequence": 0,
		"actor_id": "body-ada",
		"destination_location_id": "loc-grove",
	})
	var skipped: Dictionary = Router.route(moved.value, skip, reducer.apply_event(world, moved.value))
	if not skipped["skip"]:
		failures.append("high speed route should skip the visual")
	var adopted = reducer.adopt_frame(frame.value)
	if adopted["animations"].size() != 0:
		failures.append("frame events were animated again")
	return failures
