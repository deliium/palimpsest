extends RefCounted

const Urls := preload("res://scripts/protocol/urls.gd")
const SessionScript := preload("res://scripts/net/session.gd")
const HttpClient := preload("res://scripts/net/http_client.gd")
const Log := preload("res://scripts/log.gd")

const ORIGIN := "https://observer.example"


func run() -> Array:
	var failures: Array = []
	_assert_allowlist(failures)
	_assert_queue_epoch(failures)
	_assert_switch_clears_window(failures)
	return failures


func _assert_allowlist(failures: Array) -> void:
	var built: Dictionary = Urls.build_get(ORIGIN, "/v1/simulations/r1/observer/events", {
		"agent_id": "body-alice",
		"event_type": "AGENT_DIED",
		"location_id": "loc-camp",
		"after_child_run_id": "child-9",
		"sequence": 17,
		"limit": 10,
		"token": "secret",
	})
	var url := str(built.get("url", ""))
	for key in ["agent_id=body-alice", "event_type=AGENT_DIED", "location_id=loc-camp", "after_child_run_id=child-9", "sequence=17", "limit=10"]:
		if key not in url:
			failures.append("allowlist dropped %s" % key)
	if "secret" in url:
		failures.append("token leaked into allowlisted url")
	var posted: Dictionary = Urls.build(ORIGIN, "/v1/x", {"agent_id": "a"}, "POST")
	if posted["ok"] or posted["reason_code"] != "read_only":
		failures.append("non-GET still rejected after allowlist expansion")


func _assert_queue_epoch(failures: Array) -> void:
	var http := HttpClient.new()
	http._queue = [
		{"url": "https://a", "route": "1", "token": ""},
		{"url": "https://b", "route": "2", "token": ""},
	]
	http.clear_queue()
	if not http._queue.is_empty():
		failures.append("clear_queue should drop pending entries")
	var session: SessionScript = SessionScript.new()
	session.origin = ORIGIN
	session.run_id = "run-a"
	session._http_epoch = 3
	session._pending["9"] = {"kind": "events_window", "seek_id": -1, "epoch": 3}
	session._on_http("9", 200, {"events": [], "count": 0, "limit": 10}, "")
	# After bump, same route id with old epoch must be ignored even if re-queued.
	session._http_epoch = 4
	session._pending["10"] = {"kind": "events_window", "seek_id": -1, "epoch": 3}
	var before := session._event_window.size()
	session._on_http("10", 200, {
		"events": [{"type": "NOTE", "tick": 1, "sequence": 0}],
		"count": 1,
		"limit": 10,
	}, "")
	if session._event_window.size() != before:
		failures.append("stale epoch response must not adopt into event window")
	if "stale_epoch" not in "\n".join(Log.recent):
		failures.append("stale epoch should log http_ignored reason_code=stale_epoch")


func _assert_switch_clears_window(failures: Array) -> void:
	var session: SessionScript = SessionScript.new()
	session.origin = ORIGIN
	session.run_id = "run-old"
	session._opened = true
	session.world = {"tick": 9, "marker": "old"}
	session._event_window = [{"type": "NOTE", "tick": 1, "sequence": 0}]
	session._live_buffer = [{"type": "NOTE", "tick": 2, "sequence": 0}]
	session.cursor_after_tick = 9
	session.cursor_after_sequence = 3
	session.transport.set_cursor(session.transport.MODE_REPLAY, 9, 3, 1.0, false)
	var cleared := false
	session.source_cleared.connect(func() -> void:
		cleared = true
	)
	# Avoid real HTTP/origin during unit teardown+bootstrap attempt.
	session._http = null
	session.switch_run("run-new", 4, null, true)
	if not cleared:
		failures.append("switch_run should emit source_cleared")
	if session.run_id != "run-new":
		failures.append("switch_run should set run_id")
	if session.world != null:
		failures.append("switch_run must drop prior world before bootstrap")
	if not session._event_window.is_empty() or not session._live_buffer.is_empty():
		failures.append("switch_run must clear event window and live buffer")
	if session.cursor_after_tick != null or session.cursor_after_sequence != null:
		failures.append("switch_run must reset cursor")
	if session._opened:
		failures.append("switch_run must reset _opened")
	if int(session._pending_switch_seek.get("tick", -1)) != 4:
		failures.append("switch_run should stash optional seek_tick")
	var logged := "\n".join(Log.recent)
	if "run_switched" not in logged or "from_run_id=run-old" not in logged or "to_run_id=run-new" not in logged:
		failures.append("switch_run should log run_switched")
	if "stream_closed" not in logged or "world_cleared" not in logged or "cursor_reset" not in logged:
		failures.append("switch_run should log teardown steps")
