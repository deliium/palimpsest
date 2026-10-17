extends RefCounted

const Protocol := preload("res://scripts/protocol/models.gd")
const Reducer := preload("res://scripts/protocol/reducer.gd")
const Router := preload("res://scripts/protocol/event_router.gd")
const AgentLayer := preload("res://scripts/view/agent_layer.gd")
const LocationLayer := preload("res://scripts/view/location_layer.gd")


func run() -> Array:
	var failures: Array = []
	var payload: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://fixtures/protocol/reference_frame.json"))
	var agent: Dictionary = payload.world.agents[0]
	var body := str(agent.entity_id)
	var origin := str(agent.location_id)
	var destination := str(payload.world.locations[1].location_id)
	var journey := {
		"journey_id": "journey-test", "origin_location_id": origin,
		"destination_location_id": destination, "participant_body_ids": [body],
		"start_tick": 0, "due_tick": 2, "arrival_wait_deadline_tick": 4,
		"phase": "preparing",
	}
	agent["journey"] = journey
	payload.world.locations[0]["region_id"] = "west"
	payload.world.locations[0]["region_label"] = "West"
	var parsed := Protocol.parse_frame(payload)
	if not parsed.ok:
		return ["regional frame parse: %s" % parsed.reason_code]
	var world = parsed.value.world
	var reducer := Reducer.new()
	var layer := AgentLayer.new()
	var locations := LocationLayer.new()
	locations.show_world(world)
	layer.show_world(world)
	var origin_position: Vector2 = layer.token_position(body)
	if world.agents[0].journey.phase != "preparing":
		failures.append("preparation lost")
	for kind in ["JOURNEY_STARTED", "JOURNEY_ARRIVED", "JOURNEY_ENDED"]:
		var raw := {
			"protocol_version": Protocol.PROTOCOL_VERSION, "type": kind,
			"domain_kind": kind.to_lower(), "event_id": "event-" + kind,
			"tick": 2, "sequence": 0, "actor_id": body,
			"origin_location_id": origin, "destination_location_id": destination,
			"participant_body_ids": [body],
		}
		if kind == "JOURNEY_STARTED":
			raw["journey"] = journey
		var event = Protocol.parse_event(raw).value
		var logical := reducer.apply_event(world, event)
		var routed := Router.route(event, {}, logical)
		if routed.moves_location or routed.action == "move":
			failures.append("journey created mid-edge animation")
		if kind == "JOURNEY_STARTED" and world.agents[0].location_id != origin:
			failures.append("departure moved body")
		if kind == "JOURNEY_ARRIVED" and world.agents[0].location_id != destination:
			failures.append("arrival did not place body")
	# Waiting and backward seek replace rendered state; folded history is not applied twice.
	journey.phase = "capacity_wait"
	parsed = Protocol.parse_frame(payload)
	var adopted := reducer.adopt_frame(parsed.value)
	layer.show_world(adopted.world)
	if not adopted.animations.is_empty() or layer.token_position(body) != origin_position:
		failures.append("seek animated or lost origin anchor")
	if adopted.world.agents[0].journey.phase != "capacity_wait":
		failures.append("capacity wait lost")
	journey.phase = "preparing"
	parsed = Protocol.parse_frame(payload)
	layer.show_world(reducer.adopt_frame(parsed.value).world)
	if layer.active_motions() != 0 or layer.token_position(body) != origin_position:
		failures.append("backward seek created travel motion")
	layer.free()
	locations.free()
	return failures
