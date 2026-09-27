extends RefCounted

const Protocol := preload("res://scripts/protocol/models.gd")
const ReducerScript := preload("res://scripts/protocol/reducer.gd")
const Playback := preload("res://scripts/protocol/playback.gd")


func run() -> Array:
	var failures: Array = []
	var parsed = Protocol.parse_text("frame", FileAccess.get_file_as_string("res://fixtures/protocol/reference_frame.json"))
	if not parsed.ok:
		return ["frame did not parse"]
	var world = parsed.value.world
	var agent = world.agents[0]
	agent.location_id = "loc-camp"
	var reducer = ReducerScript.new()
	var folded = reducer.adopt_frame(parsed.value)
	if folded["animations"].size() != 0:
		failures.append("folded frame events were queued")
	if str(agent.location_id) != "loc-camp":
		failures.append("folded move was replayed")
	var speed: Dictionary = Playback.policy(8.0, 2)
	if not speed["skip"]:
		failures.append("high speed should skip without waiting")
	reducer.apply_event(world, _move("evt-a", 3, 0, "loc-grove"))
	reducer.apply_event(world, _move("evt-b", 3, 1, "loc-ridge"))
	if str(agent.location_id) != "loc-ridge":
		failures.append("two fast moves should end at the second location")
	var unchanged := str(agent.location_id)
	var again = reducer.adopt_frame(parsed.value)
	if again["animations"].size() != 0 or str(agent.location_id) != unchanged:
		failures.append("frame events moved the token a second time")
	return failures


func _move(event_id: String, tick: int, sequence: int, destination: String) -> Variant:
	return Protocol.parse_event({
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"type": "AGENT_MOVED",
		"domain_kind": "move",
		"event_id": event_id,
		"tick": tick,
		"sequence": sequence,
		"actor_id": "body-ada",
		"origin_location_id": "loc-camp",
		"destination_location_id": destination,
	}).value
