extends RefCounted

const Urls := preload("res://scripts/protocol/urls.gd")
const SessionScript := preload("res://scripts/net/session.gd")
const AgentLayer := preload("res://scripts/view/agent_layer.gd")
const Identity := preload("res://scripts/presentation/identity.gd")
const Protocol := preload("res://scripts/protocol/models.gd")
const Log := preload("res://scripts/log.gd")

const ORIGIN := "https://observer.example"
const STREAM := "/v1/simulations/run-1/observer/stream"


func run() -> Array:
	var failures: Array = []
	var opened: Dictionary = Urls.build_websocket(ORIGIN, STREAM, null, null, 4)
	if not opened["connect"]:
		failures.append("null cursor should connect")
	if "after_tick" in str(opened["url"]) or "after_sequence" in str(opened["url"]):
		failures.append("null cursor included resume parameters")
	var negative: Dictionary = Urls.build_websocket(ORIGIN, STREAM, 2, -1, 4)
	if not negative["connect"] or "after_tick" in str(negative["url"]):
		failures.append("negative sequence should omit both resume parameters")
	var ahead: Dictionary = Urls.build_websocket(ORIGIN, STREAM, 4, 0, 4)
	if ahead["connect"] or ahead["reason_code"] != "cursor_ahead":
		failures.append("after_tick at world.tick must be rejected before connect")
	if str(ahead["url"]) != "":
		failures.append("rejected resume still built a url")
	var behind: Dictionary = Urls.build_websocket(ORIGIN, STREAM, 3, 0, 4)
	if not behind["connect"] or "after_tick=3" not in str(behind["url"]) or "after_sequence=0" not in str(behind["url"]):
		failures.append("cursor behind world.tick should send both resume parameters")
	var session: SessionScript = SessionScript.new()
	var viewed := Mark.new()
	viewed.tick = 3
	viewed.marker = "paused-world"
	session.world = viewed
	session.transport.set_cursor(session.transport.MODE_LIVE, 3, 1, 1.0, true)
	var applied: Array = []
	session.live_event.connect(func(_event: Variant) -> void:
		applied.append(true)
	)
	for index in 257:
		session._on_envelope({
			"kind": "event",
			"event": {"type": "NOTE", "tick": 4, "sequence": index},
		})
	if session.world != viewed or not applied.is_empty():
		failures.append("paused live envelopes should leave the viewed world unchanged")
	if session._live_buffer.size() != 0 or not session.transport.behind_live:
		failures.append("the 257th paused event should discard the buffer and fall behind")
	var logged := "\n".join(Log.recent)
	if "live_buffer_discarded" not in logged or "reason_code=buffer_limit" not in logged:
		failures.append("pause discard should log live_buffer_discarded")
	session.return_to_live()
	if session.transport.mode != session.transport.MODE_LIVE or session.transport.behind_live:
		failures.append("return to live should clear behind_live and set LIVE")
	var saw_state := false
	for item in session.request_log:
		if str(item.get("kind", "")) == "state_live" and not item.get("query", {}).has("tick"):
			saw_state = true
	if not saw_state:
		failures.append("return to live should request unscoped state")
	session.transport.set_mode(session.transport.MODE_REPLAY)
	session.transport.set_paused(false)
	var replay_requests := session.request_log.size()
	session._on_socket_closed("dropped")
	if session.request_log.size() != replay_requests:
		failures.append("a socket loss during replay should not request the gap")
	if "gap_ignored" not in "\n".join(Log.recent) or "reason_code=replay_cursor" not in "\n".join(Log.recent):
		failures.append("replay socket loss should log gap_ignored")
	session.transport.set_mode(session.transport.MODE_LIVE)
	session.transport.set_paused(false)
	session.cursor_after_tick = 1
	session.cursor_after_sequence = 0
	viewed.tick = 9
	session.request_log.clear()
	session._on_socket_closed("dropped")
	if str(session.last_request.get("kind", "")) != "gap":
		failures.append("a socket loss during unpaused live should request the gap")
	var gap_query: Dictionary = session.last_request.get("query", {})
	if int(gap_query.get("after_tick", -1)) != 1 or int(gap_query.get("after_sequence", -1)) != 0:
		failures.append("the live gap should resume from the last applied cursor")
	_assert_steps(session, failures)
	_assert_environment_frame(session, failures)
	var kept_agent := _agent("body-bob", "dead")
	var kept: Dictionary = AgentLayer.selection_for("body-bob", [kept_agent])
	if not kept["keep"] or not kept["dead"] or not Identity.is_dead(kept_agent):
		failures.append("a dead agent still in the frame should stay selected")
	var dropped: Dictionary = AgentLayer.selection_for("body-bob", [_agent("body-alice", "alive")])
	if dropped["keep"]:
		failures.append("a missing entity should clear selection")
	return failures


class Agent:
	var entity_id: String
	var life_status: String


func _agent(entity_id: String, life_status: String) -> Agent:
	var agent := Agent.new()
	agent.entity_id = entity_id
	agent.life_status = life_status
	return agent


class Mark:
	var tick: int
	var marker: String


class FrameCursor:
	var after_tick: int
	var after_sequence: int


class Frame:
	var world: Mark
	var cursor: FrameCursor


func _assert_steps(session: SessionScript, failures: Array) -> void:
	session._event_window = [_note(4, 0), _note(4, 1), _note(5, 0), _note(5, 2)]
	session.transport.set_cursor(session.transport.MODE_REPLAY, 4, 0, 1.0, false)
	session.request_log.clear()
	session.next_event()
	var forward := _state_query(session)
	if int(forward.get("tick", -1)) != 4 or int(forward.get("through_sequence", -1)) != 1:
		failures.append("speed below 8 should request the next event through_sequence")
	session.transport.set_speed(8.0)
	session.request_log.clear()
	session.next_event()
	var whole := _state_query(session)
	if int(whole.get("tick", -1)) != 5 or int(whole.get("through_sequence", -1)) != 2:
		failures.append("speed 8 should request the last event of the next tick")
	session.transport.set_speed(1.0)
	session.transport.set_cursor(session.transport.MODE_REPLAY, 5, 0, 1.0, false)
	session.request_log.clear()
	session.previous_tick()
	var prior_tick := _state_query(session)
	if int(prior_tick.get("tick", -1)) != 4 or int(prior_tick.get("through_sequence", -1)) != 1:
		failures.append("previous tick should request the last event of the previous tick")
	session.transport.set_cursor(session.transport.MODE_REPLAY, 4, 1, 1.0, false)
	session.request_log.clear()
	var folded: Array = []
	session.live_event.connect(func(_event: Variant) -> void:
		folded.append(true)
	)
	session.previous_event()
	var backward := _state_query(session)
	if int(backward.get("tick", -1)) != 4 or int(backward.get("through_sequence", -1)) != 0:
		failures.append("previous event should request the previous pair")
	var restored := Mark.new()
	restored.tick = 4
	restored.marker = "restored"
	var cursor := FrameCursor.new()
	cursor.after_tick = 4
	cursor.after_sequence = 0
	var frame := Frame.new()
	frame.world = restored
	frame.cursor = cursor
	session._apply_sought_frame(frame, session._seek_serial)
	if session.world != restored or not folded.is_empty():
		failures.append("a backward step should replace state from the frame")
	if session.transport.tick != 4 or int(session.transport.sequence) != 0:
		failures.append("the replaced frame should view the sought event")


func _assert_environment_frame(session: SessionScript, failures: Array) -> void:
	var parsed: Protocol.ParseResult = Protocol.parse_frame({
		"protocol_version": "observer-protocol-v1",
		"cursor": {
			"run_id": "run-1",
			"mode": "replay",
			"tick": 12,
			"protocol_version": "observer-protocol-v1",
			"after_tick": 12,
			"after_sequence": 0,
		},
		"world": {
			"tick": 12,
			"revision": 1,
			"season": "winter",
			"temperature_bands": [{"location_id": "loc-1", "band": "cold"}],
			"hazards": [{
				"location_id": "loc-1",
				"hazard_kind": "cold_snap",
				"remaining_ticks": 4,
			}],
			"locations": [],
			"agents": [],
			"items": [],
			"resources": [],
			"weather": [],
		},
		"events": [],
	})
	if not parsed.ok:
		failures.append("environment frame should parse")
		return
	var replaced: Array = []
	session.world_replaced.connect(func(world: Variant) -> void:
		replaced.append(world)
	)
	session._apply_sought_frame(parsed.value, session._seek_serial)
	if session.world != parsed.value.world or replaced.is_empty() or replaced[-1] != parsed.value.world:
		failures.append("sought environment frame should be the world world_replaced emits")
	if str(session.world.season) != "winter" or session.world.hazards.size() != 1:
		failures.append("sought frame should keep the season and hazard tokens")
	if str(session.world.temperature_bands[0].band) != "cold":
		failures.append("sought frame should keep the temperature band token")


func _state_query(session: SessionScript) -> Dictionary:
	var found := {}
	for item in session.request_log:
		if str(item.get("kind", "")) == "state_cursor":
			found = item.get("query", {})
	return found


func _note(tick: int, sequence: int) -> Variant:
	return Protocol.parse_event({"type": "NOTE", "tick": tick, "sequence": sequence}).value
