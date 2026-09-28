extends RefCounted

const Urls := preload("res://scripts/protocol/urls.gd")
const SessionScript := preload("res://scripts/net/session.gd")
const AgentLayer := preload("res://scripts/view/agent_layer.gd")
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
	var session: Node = SessionScript.new()
	session.transport.set_cursor(session.transport.MODE_LIVE, 3, 1, 1.0, true)
	for _index in 257:
		session._buffer_live_event({"tick": 3, "sequence": 2})
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
	if session.transport.mode == session.transport.MODE_REPLAY and session.accepts_gap():
		failures.append("replay should not apply a gap")
	session.transport.set_mode(session.transport.MODE_REPLAY)
	session.transport.set_paused(false)
	if session.accepts_gap():
		failures.append("a socket loss during replay should not request the gap")
	session.transport.set_mode(session.transport.MODE_LIVE)
	session.transport.set_paused(false)
	if not session.accepts_gap():
		failures.append("a socket loss during unpaused live should still request the gap")
	var kept: Dictionary = AgentLayer.selection_for("body-bob", [_agent("body-bob", "dead")])
	if not kept["keep"] or not kept["dead"]:
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
