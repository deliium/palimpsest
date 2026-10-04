extends RefCounted

const SessionScript := preload("res://scripts/net/session.gd")
const Log := preload("res://scripts/log.gd")


class Event:
	var type: String
	var tick: int
	var sequence: int
	var actor_id: Variant
	var target_id: Variant
	var origin_location_id: Variant
	var destination_location_id: Variant


func run() -> Array:
	var failures: Array = []
	var session: SessionScript = SessionScript.new()
	session._opened = true
	session._http = null
	session.focus_agent_id = "body-alice"
	session._event_window = [
		_event("AGENT_ATTACKED", 1, 0, "body-alice", "body-bob", "loc-a", null),
		_event("AGENT_DIED", 2, 0, null, "body-alice", "loc-a", null),
		_event("AGENT_WAITED", 3, 0, "body-bob", null, "loc-b", null),
		_event("AGENT_HELPED", 4, 0, "body-bob", "body-alice", "loc-a", null),
	]
	session.transport.set_cursor(session.transport.MODE_REPLAY, 1, 0, 1.0, false)
	var nxt: Dictionary = session._focused_neighbor(true)
	if int(nxt.get("tick", -1)) != 2 or int(nxt.get("sequence", -1)) != 0:
		failures.append("next focused should prefer loaded Alice death target event")
	session.transport.set_cursor(session.transport.MODE_REPLAY, 4, 0, 1.0, false)
	var prev: Dictionary = session._focused_neighbor(false)
	if int(prev.get("tick", -1)) != 2:
		failures.append("previous focused should find earlier Alice-related event")
	session.focus_location_id = "loc-a"
	session.focus_agent_id = ""
	session.transport.set_cursor(session.transport.MODE_REPLAY, 1, 0, 1.0, false)
	var loc_next: Dictionary = session._focused_neighbor(true)
	if int(loc_next.get("tick", -1)) != 2:
		failures.append("location focus should match origin/destination")
	session.focus_agent_id = "body-alice"
	session.set_follow("agent", true)
	if session.follow_mode != "agent":
		failures.append("follow agent should enable")
	session.set_follow("location", true)
	if session.follow_mode != "location":
		failures.append("follow location should replace agent follow")
	session.set_follow("location", false)
	if session.follow_mode != "":
		failures.append("disabling follow should clear mode")
	# Prove no control routes were queued by follow toggles.
	for item in session.request_log:
		var kind := str(item.get("kind", ""))
		if kind.begins_with("control") or kind == "pause" or kind == "fork":
			failures.append("follow must not enqueue control routes")
			break
	var logged := "\n".join(Log.recent)
	if "follow_agent" not in logged or "follow_location" not in logged:
		failures.append("follow toggles should log INFO tokens")
	return failures


func _event(
	type_name: String,
	tick: int,
	sequence: int,
	actor: Variant,
	target: Variant,
	origin: Variant,
	destination: Variant,
) -> Event:
	var event := Event.new()
	event.type = type_name
	event.tick = tick
	event.sequence = sequence
	event.actor_id = actor
	event.target_id = target
	event.origin_location_id = origin
	event.destination_location_id = destination
	return event
