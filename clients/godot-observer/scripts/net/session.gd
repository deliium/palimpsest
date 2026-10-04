extends Node

const ObserverLog := preload("res://scripts/log.gd")
const Protocol := preload("res://scripts/protocol/models.gd")
const Urls := preload("res://scripts/protocol/urls.gd")
const Cursor := preload("res://scripts/protocol/cursor.gd")
const TransportScript := preload("res://scripts/protocol/transport.gd")
const Playback := preload("res://scripts/protocol/playback.gd")
const Origin := preload("res://scripts/net/origin.gd")
const HttpClient := preload("res://scripts/net/http_client.gd")
const StreamClient := preload("res://scripts/net/stream_client.gd")

const PAGE_LIMIT := 100
const EVENT_WINDOW := 200
const BUFFER_LIMIT := 256
const CLOSE_REASONS := {
	"4400": "invalid_cursor",
	"4401": "unauthorized",
	"4404": "not_found",
	"4409": "cursor_ahead",
}

signal status_changed(code: String, detail: String)
signal run_id_applied(value: String)
signal world_replaced(world: Variant)
signal source_cleared
signal live_event(event: Variant)
signal frame_sought(frame: Variant, event: Variant, forward: bool)
signal overlay_payload(kind: String, payload: Variant)
signal overlay_unavailable(kind: String, reason_code: String)
signal events_loaded(events: Array, focus_tick: int, focus_sequence: int)
signal ticks_loaded(ticks: Array)
signal run_loaded(record: Dictionary)
signal branch_updated
signal nav_stack_changed(depth: int)
signal marker_enrichment_loaded(events: Array)
signal focus_changed
signal follow_changed(mode: String)

const NAV_STACK_LIMIT := 16
const BRANCH_PAGE_LIMIT := 50
const MARKER_TYPE_BUDGET := 3
const FOCUS_PROBE_LIMIT := 32

var run_id := ""
var origin := ""
var world: Variant = null
var cursor_after_tick: Variant = null
var cursor_after_sequence: Variant = null
var transport := TransportScript.new()
var lineage := {
	"parent_run_id": "",
	"fork_tick": -1,
	"intervention_summary": "",
	"branch_id": "",
}
var branch_children: Array = []
var branch_next_cursor: Variant = null
var branch_reason_code := ""
var focus_agent_id := ""
var focus_location_id := ""
var follow_mode := ""  # "", "agent", "location"
var follow_snap_location := false

var _token := ""
var _http: Node
var _stream: Node
var _pending := {}
var _seek_meta := {}
var _request_serial := 0
var _seek_serial := 0
var _http_epoch := 0
var _opened := false
var _failed := false
var _gap_events := 0
var _reconnect_pending := false
var _event_window: Array = []
var _live_buffer: Array = []
var _navigation := ""
var last_request := {}
var request_log: Array = []
var _playing := false
var _play_timer: Timer
var _pending_deeplink := {}
var _pending_switch_seek := {}
var _switching := false
var _nav_stack: Array = []
var _marker_serial := 0
var _marker_queue: Array = []
var _marker_events: Array = []
var _focus_probe_left := 0
var _focus_nav := ""
var _probe_tick := 0
var _probe_sequence: Variant = null


func _ready() -> void:
	_http = HttpClient.new()
	_http.name = "HttpClient"
	add_child(_http)
	_http.get_completed.connect(_on_http)
	_stream = StreamClient.new()
	_stream.name = "StreamClient"
	add_child(_stream)
	_stream.envelope_received.connect(_on_envelope)
	_stream.socket_closed.connect(_on_socket_closed)
	_play_timer = Timer.new()
	_play_timer.one_shot = true
	_play_timer.name = "PlayTimer"
	add_child(_play_timer)
	_play_timer.timeout.connect(_on_play_step)
	var head_timer := Timer.new()
	head_timer.wait_time = 2.0
	head_timer.autostart = true
	head_timer.name = "HeadTimer"
	add_child(head_timer)
	head_timer.timeout.connect(_poll_live_head)


func begin() -> void:
	if OS.has_feature("web"):
		if apply_web_query(Origin.web_search()):
			return
		status_changed.emit("idle", "Connect")
		return
	var configured := str(ProjectSettings.get_setting("palimpsest/run_id", "")).strip_edges()
	if run_id.is_empty():
		run_id = configured
	_start()


func apply_web_query(search: String) -> bool:
	var state: Dictionary = Origin.web_debugger_state(search)
	var reason := str(state.get("reason_code", ""))
	if reason != "":
		ObserverLog.warn(
			"session",
			"web_query_rejected reason_code=%s" % reason,
		)
		return false
	var parsed := str(state.get("run_id", "")).strip_edges()
	if parsed.is_empty():
		return false
	run_id = parsed
	_pending_deeplink = {
		"tick": state.get("tick", null),
		"sequence": state.get("sequence", null),
		"event_id": str(state.get("event_id", "")),
		"agent_id": str(state.get("agent_id", "")),
		"open_debugger": bool(state.get("open_debugger", false)),
	}
	ObserverLog.info("session", "web_run_id_applied run_id=%s" % run_id)
	ObserverLog.debug(
		"session",
		"web_deeplink_parsed tick=%s sequence=%s event_id=%s open_debugger=%s" % [
			str(_pending_deeplink.get("tick", null)),
			str(_pending_deeplink.get("sequence", null)),
			str(_pending_deeplink.get("event_id", "")),
			str(_pending_deeplink.get("open_debugger", false)),
		],
	)
	run_id_applied.emit(run_id)
	_start()
	return true


func start_with_run_id(requested: String) -> void:
	var trimmed := requested.strip_edges()
	if trimmed.is_empty():
		_fail("run_id_missing")
		return
	switch_run(trimmed, null, null, true)


func switch_run(
	next_run_id: String,
	seek_tick: Variant = null,
	seek_sequence: Variant = null,
	push_history: bool = true,
) -> void:
	## Replace ObserverSource cleanly: one run, one stream, no merged occupancy.
	var trimmed := next_run_id.strip_edges()
	if trimmed.is_empty():
		_fail("run_id_missing")
		return
	var from_run_id := run_id
	if push_history and not from_run_id.is_empty() and from_run_id != trimmed:
		_nav_stack_push(from_run_id, transport.tick, transport.sequence)
	_teardown_source()
	run_id = trimmed
	run_id_applied.emit(run_id)
	_pending_switch_seek = {}
	if seek_tick != null:
		_pending_switch_seek = {
			"tick": int(seek_tick),
			"sequence": null if seek_sequence == null else int(seek_sequence),
		}
	ObserverLog.info(
		"session",
		"run_switched from_run_id=%s to_run_id=%s" % [from_run_id, run_id],
	)
	_start()


func return_to_previous_run() -> Dictionary:
	if _nav_stack.is_empty():
		ObserverLog.debug("session", "nav_stack_pop depth=0 reason_code=nav_stack_empty")
		status_changed.emit("nav_stack_empty", "No previous run")
		return {"ok": false, "reason_code": "nav_stack_empty"}
	var entry: Dictionary = _nav_stack.pop_back()
	var prior_id := str(entry.get("run_id", ""))
	ObserverLog.debug(
		"session",
		"nav_stack_pop depth=%s run_id=%s" % [_nav_stack.size(), prior_id],
	)
	nav_stack_changed.emit(_nav_stack.size())
	switch_run(
		prior_id,
		entry.get("tick", null),
		entry.get("sequence", null),
		false,
	)
	ObserverLog.info("session", "nav_stack_return run_id=%s" % prior_id)
	return {"ok": true, "run_id": prior_id, "depth": _nav_stack.size()}


func nav_stack_depth() -> int:
	return _nav_stack.size()


func _nav_stack_push(prior_run_id: String, tick: int, sequence: Variant) -> void:
	_nav_stack.append({
		"run_id": prior_run_id,
		"tick": tick,
		"sequence": sequence,
	})
	while _nav_stack.size() > NAV_STACK_LIMIT:
		_nav_stack.pop_front()
	ObserverLog.debug(
		"session",
		"nav_stack_push depth=%s run_id=%s" % [_nav_stack.size(), prior_run_id],
	)
	nav_stack_changed.emit(_nav_stack.size())


func fetch_branch_children(after_child_run_id: Variant = null) -> void:
	if run_id.is_empty():
		return
	var query := {"limit": BRANCH_PAGE_LIMIT}
	if after_child_run_id != null and str(after_child_run_id) != "":
		query["after_child_run_id"] = str(after_child_run_id)
	_request_path(
		"branch_children",
		"/v1/simulations/%s/branches" % run_id,
		{"append": after_child_run_id != null and str(after_child_run_id) != ""},
		query,
	)


func open_parent_at_fork() -> void:
	if run_id.is_empty():
		_fail("run_id_missing")
		return
	if str(lineage.get("parent_run_id", "")).is_empty():
		branch_reason_code = "branch_root"
		branch_updated.emit()
		status_changed.emit("branch_root", "No parent branch")
		return
	_request_path("branch_fork_point", "/v1/simulations/%s/branch/fork-point" % run_id)


func start_marker_enrichment(type_names: Array) -> void:
	## At most one refresh; ≤3 sequential type pages; cancelled on seek/switch.
	if not _opened or _switching:
		return
	_marker_serial += 1
	_marker_queue = []
	_marker_events = []
	var budget := 0
	for type_name in type_names:
		if budget >= MARKER_TYPE_BUDGET:
			break
		var trimmed := str(type_name).strip_edges()
		if trimmed.is_empty():
			continue
		_marker_queue.append(trimmed)
		budget += 1
	ObserverLog.debug(
		"session",
		"marker_refresh_started count=%s serial=%s" % [_marker_queue.size(), _marker_serial],
	)
	_pump_marker_enrichment(_marker_serial)


func cancel_marker_enrichment() -> void:
	_marker_serial += 1
	_marker_queue.clear()
	_marker_events.clear()
	ObserverLog.debug("session", "marker_refresh_cancelled serial=%s" % _marker_serial)


func _pump_marker_enrichment(serial: int) -> void:
	if serial != _marker_serial:
		return
	if _marker_queue.is_empty():
		marker_enrichment_loaded.emit(_marker_events)
		ObserverLog.debug(
			"session",
			"marker_refresh_done event_count=%s" % _marker_events.size(),
		)
		return
	var type_name := str(_marker_queue.pop_front())
	_request(
		"marker_events",
		{"limit": EVENT_WINDOW, "event_type": type_name},
		-1,
	)
	# Bind the in-flight type to the pending meta via a dedicated path request.
	# _request stores kind=marker_events; completion appends then pumps.


func open_child_branch(child_run_id: String, child_fork_tick: Variant = null) -> void:
	var trimmed := child_run_id.strip_edges()
	if trimmed.is_empty():
		return
	var fork_tick: Variant = child_fork_tick
	ObserverLog.info(
		"session",
		"branch_open_child child_run_id=%s fork_tick=%s" % [trimmed, str(fork_tick)],
	)
	switch_run(trimmed, fork_tick, null, true)


func set_agent_focus(entity_id: String) -> void:
	focus_agent_id = entity_id.strip_edges()
	ObserverLog.debug("session", "focus_agent id=%s" % focus_agent_id)
	focus_changed.emit()
	refresh_focused_events()


func set_location_focus(location_id: String) -> void:
	focus_location_id = location_id.strip_edges()
	ObserverLog.debug("session", "focus_location id=%s" % focus_location_id)
	focus_changed.emit()
	refresh_focused_events()


func clear_focus() -> void:
	focus_agent_id = ""
	focus_location_id = ""
	set_follow("", false)
	focus_changed.emit()


func set_follow(mode: String, enabled: bool) -> void:
	## Presentation-only camera/UI follow. Never calls simulation control.
	var next := ""
	if enabled:
		next = mode
		if next == "agent" and focus_agent_id.is_empty():
			next = ""
		if next == "location" and focus_location_id.is_empty():
			next = ""
	if next == "agent":
		ObserverLog.info("session", "follow_agent enabled=true")
	elif follow_mode == "agent" and next != "agent":
		ObserverLog.info("session", "follow_agent enabled=false")
	if next == "location":
		ObserverLog.info("session", "follow_location enabled=true")
	elif follow_mode == "location" and next != "location":
		ObserverLog.info("session", "follow_location enabled=false")
	follow_mode = next
	follow_changed.emit(follow_mode)


func toggle_follow_agent() -> void:
	if follow_mode == "agent":
		set_follow("agent", false)
	else:
		set_follow("agent", true)


func toggle_follow_location() -> void:
	if follow_mode == "location":
		set_follow("location", false)
	else:
		set_follow("location", true)


func refresh_focused_events() -> void:
	if not _opened or run_id.is_empty():
		return
	if focus_agent_id.is_empty() and focus_location_id.is_empty():
		return
	var query := {"limit": EVENT_WINDOW}
	if focus_agent_id != "":
		query["agent_id"] = focus_agent_id
	if focus_location_id != "":
		query["location_id"] = focus_location_id
	_request("focus_events", query, -1)


func next_focused_event() -> void:
	if focus_agent_id.is_empty() and focus_location_id.is_empty():
		status_changed.emit("no_focused_event", "No focus selected")
		return
	var neighbor := _focused_neighbor(true)
	if not neighbor.is_empty():
		_seek_focus_event(neighbor)
		return
	var query := {"limit": EVENT_WINDOW}
	if focus_agent_id != "":
		query["agent_id"] = focus_agent_id
	if focus_location_id != "":
		query["location_id"] = focus_location_id
	if Urls.resume_allowed(transport.tick, transport.sequence):
		query["after_tick"] = transport.tick
		query["after_sequence"] = transport.sequence
	_focus_nav = "next"
	_request("focus_seek", query, -1)


func previous_focused_event() -> void:
	if focus_agent_id.is_empty() and focus_location_id.is_empty():
		status_changed.emit("no_focused_event", "No focus selected")
		return
	var neighbor := _focused_neighbor(false)
	if not neighbor.is_empty():
		_seek_focus_event(neighbor)
		return
	_focus_probe_left = FOCUS_PROBE_LIMIT
	_probe_tick = transport.tick
	_probe_sequence = transport.sequence
	_focus_nav = "previous"
	ObserverLog.debug("session", "focus_probe count=%s" % _focus_probe_left)
	_probe_previous_focused()


func _focused_neighbor(forward: bool) -> Dictionary:
	var best: Dictionary = {}
	for event in _event_window:
		if not _event_matches_focus(event):
			continue
		var tick := int(event.tick)
		var sequence := int(event.sequence)
		if forward:
			if tick < transport.tick:
				continue
			if tick == transport.tick and (transport.sequence != null and sequence <= int(transport.sequence)):
				continue
			if best.is_empty() or tick < int(best["tick"]) or (
				tick == int(best["tick"]) and sequence < int(best["sequence"])
			):
				best = {"tick": tick, "sequence": sequence}
		else:
			if tick > transport.tick:
				continue
			if tick == transport.tick and (
				transport.sequence == null or sequence >= int(transport.sequence)
			):
				continue
			if best.is_empty() or tick > int(best["tick"]) or (
				tick == int(best["tick"]) and sequence > int(best["sequence"])
			):
				best = {"tick": tick, "sequence": sequence}
	return best


func _event_matches_focus(event: Variant) -> bool:
	if focus_agent_id.is_empty() and focus_location_id.is_empty():
		return false
	if focus_agent_id != "":
		var actor := "" if event.actor_id == null else str(event.actor_id)
		var target := "" if event.target_id == null else str(event.target_id)
		if actor != focus_agent_id and target != focus_agent_id:
			return false
	if focus_location_id != "":
		var origin := "" if event.origin_location_id == null else str(event.origin_location_id)
		var destination := (
			"" if event.destination_location_id == null else str(event.destination_location_id)
		)
		if origin != focus_location_id and destination != focus_location_id:
			return false
	return true


func _seek_focus_event(target: Dictionary) -> void:
	ObserverLog.debug(
		"session",
		"focus_seek tick=%s sequence=%s" % [int(target["tick"]), int(target["sequence"])],
	)
	seek_event(int(target["tick"]), int(target["sequence"]), null)


func _probe_previous_focused() -> void:
	if _focus_probe_left <= 0:
		_focus_nav = ""
		status_changed.emit("no_previous_focused_event", "No previous focused event")
		ObserverLog.debug("session", "focus_probe count=0 reason_code=no_previous_focused_event")
		return
	_focus_probe_left -= 1
	ObserverLog.debug("session", "focus_probe count=%s" % (FOCUS_PROBE_LIMIT - _focus_probe_left))
	var query := {"limit": 16}
	if focus_agent_id != "":
		query["agent_id"] = focus_agent_id
	if focus_location_id != "":
		query["location_id"] = focus_location_id
	if _probe_sequence != null and int(_probe_sequence) > 0:
		var before := _events_before(_probe_tick, int(_probe_sequence))
		if Urls.resume_allowed(before.get("after_tick", null), before.get("after_sequence", null)):
			query["after_tick"] = before["after_tick"]
			query["after_sequence"] = before["after_sequence"]
		_request("focus_probe", query, -1)
		return
	if _probe_tick <= 0:
		_focus_nav = ""
		status_changed.emit("no_previous_focused_event", "No previous focused event")
		return
	fetch_ticks(maxi(_probe_tick - 1, 0), _probe_tick, _seek_serial)
	_navigation = "focus_previous_tick"


func _teardown_source() -> void:
	_switching = true
	status_changed.emit("switching_run", "Switching run")
	if _stream != null:
		_stream.close_stream(true)
	ObserverLog.debug("session", "stream_closed")
	_playing = false
	if _play_timer != null:
		_play_timer.stop()
	_seek_serial += 1
	_seek_meta.clear()
	_cancel_http("switch_run")
	_event_window.clear()
	_live_buffer.clear()
	_navigation = ""
	_gap_events = 0
	_reconnect_pending = false
	_pending_deeplink = {}
	_opened = false
	_failed = false
	world = null
	cursor_after_tick = null
	cursor_after_sequence = null
	transport = TransportScript.new()
	lineage = {
		"parent_run_id": "",
		"fork_tick": -1,
		"intervention_summary": "",
		"branch_id": "",
	}
	branch_children = []
	branch_next_cursor = null
	branch_reason_code = ""
	focus_agent_id = ""
	focus_location_id = ""
	follow_mode = ""
	_focus_nav = ""
	_focus_probe_left = 0
	ObserverLog.debug("session", "cursor_reset")
	source_cleared.emit()
	branch_updated.emit()
	focus_changed.emit()
	follow_changed.emit("")
	ObserverLog.debug("session", "world_cleared")
	_switching = false


func _start() -> void:
	origin = Origin.resolve()
	_token = str(ProjectSettings.get_setting("palimpsest/api_token", ""))
	if Origin.is_missing(origin):
		_fail("observer_origin_missing")
		return
	if run_id.is_empty():
		_fail("run_id_missing")
		return
	_failed = false
	_opened = false
	status_changed.emit("loading", "Loading")
	transport.run_id = run_id
	ObserverLog.info("session", "bootstrap_started run_id=%s" % run_id)
	_request("manifest")


func _fail(reason_code: String) -> void:
	_failed = true
	if _opened:
		ObserverLog.error("session", "session_failed reason_code=%s" % reason_code)
	else:
		ObserverLog.error("session", "bootstrap_failed reason_code=%s" % reason_code)
	status_changed.emit(reason_code, reason_code)


func seek_event(event_tick: int, event_sequence: int, event: Variant = null) -> void:
	_begin_seek(event_tick, event_sequence, event)
	_request(
		"state_cursor",
		{"tick": event_tick, "through_sequence": event_sequence},
		_seek_serial,
	)


func seek_tick(event_tick: int) -> void:
	_begin_seek(event_tick, 0, null)
	_request("state_tick", {"tick": event_tick}, _seek_serial)


func fetch_events(after_tick: Variant, after_sequence: Variant, seek_id: int) -> void:
	var query := {"limit": EVENT_WINDOW}
	if Urls.resume_allowed(after_tick, after_sequence):
		query["after_tick"] = after_tick
		query["after_sequence"] = after_sequence
	_request("events_window", query, seek_id)


func fetch_ticks(from_tick: int, to_tick: int, seek_id: int) -> void:
	_request(
		"ticks",
		{"from_tick": from_tick, "to_tick": to_tick},
		seek_id,
	)


func fetch_run(seek_id: int = -1) -> void:
	_request("run", {}, seek_id)


func _begin_seek(event_tick: int, event_sequence: int, event: Variant) -> void:
	var forward := _is_forward(event_tick, event_sequence)
	_enter_replay()
	_cancel_http("seek")
	_seek_serial += 1
	_seek_meta[_seek_serial] = {
		"event": event,
		"forward": forward,
		"focus_tick": event_tick,
		"focus_sequence": event_sequence,
	}
	ObserverLog.debug(
		"session",
		"seek_started tick=%s sequence=%s" % [event_tick, event_sequence],
	)
	status_changed.emit("seeking", "Seeking")
	var before := _events_before(event_tick, event_sequence)
	fetch_events(before.get("after_tick", null), before.get("after_sequence", null), _seek_serial)


func _cancel_http(reason: String) -> void:
	_http_epoch += 1
	_pending.clear()
	if _http != null and _http.has_method("clear_queue"):
		_http.clear_queue()
	cancel_marker_enrichment()
	ObserverLog.debug("session", "queue_cleared reason=%s epoch=%s" % [reason, _http_epoch])


func _events_before(event_tick: int, event_sequence: int) -> Dictionary:
	if event_sequence > 0:
		return {"after_tick": event_tick, "after_sequence": event_sequence - 1}
	if event_tick > 0:
		return {"after_tick": event_tick - 1, "after_sequence": 1000000}
	return {}


func _enter_replay() -> void:
	var entering := transport.mode != TransportScript.MODE_REPLAY
	transport.set_mode(TransportScript.MODE_REPLAY)
	if entering:
		_stream.close_stream(true)


func _is_forward(event_tick: int, event_sequence: int) -> bool:
	if transport.sequence == null:
		return true
	if event_tick > transport.tick:
		return true
	if event_tick == transport.tick and event_sequence > int(transport.sequence):
		return true
	return false


func request_claim_overlay(owner_id: String) -> void:
	var path := "/v1/simulations/%s/owners/%s/territorial-claims" % [run_id, owner_id]
	_request_path("territorial_claims", path)


func request_label_overlay(agent_id: String) -> void:
	var path := "/v1/simulations/%s/observer/agents/%s/labels" % [run_id, agent_id]
	_request_path("subjective_labels", path)


func request_relationship_overlay(agent_id: String) -> void:
	var path := "/v1/simulations/%s/observer/agents/%s/relationships" % [run_id, agent_id]
	_request_path("relationships", path)


func request_narrative_hop_overlay(agent_id: String) -> void:
	var path := "/v1/simulations/%s/observer/agents/%s/narrative-hops" % [run_id, agent_id]
	_request_path("narrative_hops", path)


func request_causal_trace(
	event_id: String = "",
	tick: Variant = null,
	sequence: Variant = null,
) -> void:
	## GET-only causal debugger payload. Capability token stays in header.
	if run_id.is_empty():
		_emit_overlay_unavailable("causal_debugger", "run_id_missing")
		return
	var path := ""
	if event_id != "":
		path = "/v1/simulations/%s/debugger/events/%s/causal-trace" % [run_id, event_id]
		ObserverLog.debug(
			"observer.debugger",
			"causal_trace_request event_id=%s" % event_id,
		)
		_request_path("causal_debugger", path)
		return
	if tick == null or sequence == null:
		_emit_overlay_unavailable("causal_debugger", "incomplete_event_cursor")
		return
	path = "/v1/simulations/%s/debugger/causal-trace" % run_id
	ObserverLog.debug(
		"observer.debugger",
		"causal_trace_request tick=%s sequence=%s" % [int(tick), int(sequence)],
	)
	_request_path(
		"causal_debugger",
		path,
		{},
		{"tick": int(tick), "sequence": int(sequence)},
	)


func request_debugger_lineage(kind: String, subject_id: String, owner_id: String) -> void:
	## GET lineage/{kind}/{subject_id}?owner_id=… — token stays in header only.
	if run_id.is_empty():
		_emit_overlay_unavailable("causal_debugger_lineage", "run_id_missing")
		return
	var trimmed_kind := kind.strip_edges()
	var trimmed_subject := subject_id.strip_edges()
	var trimmed_owner := owner_id.strip_edges()
	if trimmed_kind.is_empty() or trimmed_subject.is_empty():
		ObserverLog.warn(
			"observer.debugger",
			"lineage_skipped reason_code=invalid_kind kind=%s" % trimmed_kind,
		)
		_emit_overlay_unavailable("causal_debugger_lineage", "invalid_kind")
		return
	if trimmed_owner.is_empty():
		ObserverLog.warn(
			"observer.debugger",
			"owner_id_missing reason_code=owner_id_missing",
		)
		_emit_overlay_unavailable("causal_debugger_lineage", "owner_id_missing")
		return
	var path := "/v1/simulations/%s/debugger/lineage/%s/%s" % [
		run_id, trimmed_kind, trimmed_subject,
	]
	ObserverLog.debug(
		"observer.debugger",
		"lineage_request run_id=%s kind=%s subject_id=%s owner_id=%s" % [
			run_id, trimmed_kind, trimmed_subject, trimmed_owner,
		],
	)
	_request_path(
		"causal_debugger_lineage",
		path,
		{},
		{"owner_id": trimmed_owner},
	)


func request_analytics_overlay(_metric_set_id: String = "") -> void:
	## Catalog discovery resolves metric_set_id; caller-supplied ids are ignored.
	request_metric_family_overlay("spatial_control", "spatial_control")


func request_strategy_audit_overlay() -> void:
	## Research/debug ANALYTICAL payload. Ordinary speech must not read this.
	var path := "/v1/simulations/%s/observer/communication-strategy-audit" % run_id
	_request_path("communication_strategy_audit", path)


func request_metric_family_overlay(family: String, overlay_kind: String = "") -> void:
	var kind := overlay_kind if overlay_kind != "" else family
	if run_id.is_empty():
		_emit_overlay_unavailable(kind, "run_id_missing")
		return
	var path := "/v1/simulations/%s/metrics" % run_id
	_request_path(
		"metric_catalog",
		path,
		{"family": family, "overlay_kind": kind, "seek_id": -1},
	)


static func resolve_metric_set_id(catalog: Dictionary, family: String) -> String:
	## Deterministic: prefer the newest matching catalog entry (last in list).
	var items: Variant = catalog.get("items", [])
	if not items is Array:
		return ""
	var chosen := ""
	for item in items:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		if str(item.get("metric_family", "")) != family:
			continue
		var set_id := str(item.get("metric_set_id", ""))
		if set_id != "":
			chosen = set_id
	return chosen


func _emit_overlay_unavailable(kind: String, reason_code: String) -> void:
	ObserverLog.warn(
		"session",
		"overlay_unavailable kind=%s reason_code=%s" % [kind, reason_code],
	)
	overlay_unavailable.emit(kind, reason_code)
	overlay_payload.emit(kind, null)


func _apply_pending_switch_seek() -> void:
	if _pending_switch_seek.is_empty():
		return
	var pending: Dictionary = _pending_switch_seek.duplicate(true)
	_pending_switch_seek = {}
	var tick = pending.get("tick", null)
	if tick == null:
		return
	var sequence = pending.get("sequence", null)
	if sequence == null:
		ObserverLog.info("session", "switch_seek tick=%s" % int(tick))
		seek_tick(int(tick))
		return
	ObserverLog.info(
		"session",
		"switch_seek tick=%s sequence=%s" % [int(tick), int(sequence)],
	)
	seek_event(int(tick), int(sequence), null)


func _apply_pending_deeplink() -> void:
	if _pending_deeplink.is_empty():
		return
	var pending: Dictionary = _pending_deeplink.duplicate(true)
	_pending_deeplink = {}
	var tick = pending.get("tick", null)
	var sequence = pending.get("sequence", null)
	var event_id := str(pending.get("event_id", ""))
	if tick != null and sequence != null:
		ObserverLog.info(
			"session",
			"deeplink_seek tick=%s sequence=%s" % [int(tick), int(sequence)],
		)
		seek_event(int(tick), int(sequence), null)
	if bool(pending.get("open_debugger", false)):
		request_causal_trace(event_id, tick, sequence)


func _decode_metric_document(body: Dictionary) -> Variant:
	var encoded := str(body.get("payload_b64", ""))
	if encoded.is_empty():
		if str(body.get("layer", "")) != "":
			return body
		return null
	var raw: PackedByteArray = Marshalls.base64_to_raw(encoded)
	if raw.is_empty():
		return null
	var text := raw.get_string_from_utf8()
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return null
	return parsed


func _request_path(
	kind: String,
	path: String,
	meta: Dictionary = {},
	query: Dictionary = {},
) -> void:
	## Shared GET helper. Capability tokens stay in the HTTP header — never query.
	var request_query := query.duplicate()
	last_request = {"kind": kind, "path": path, "query": request_query.duplicate()}
	request_log.append(last_request)
	var query_keys: Array = request_query.keys()
	ObserverLog.debug(
		"session",
		"get_built route=%s query_keys=%s" % [path, ",".join(query_keys)],
	)
	if _http == null:
		return
	var built: Dictionary = Urls.build_get(origin, path, request_query)
	if not bool(built.get("ok", false)):
		var reason := str(built.get("reason_code", "read_only"))
		ObserverLog.warn(
			"session",
			"read_only reason_code=%s kind=%s" % [reason, kind],
		)
		if kind == "metric_catalog" or kind == "metric_document":
			_emit_overlay_unavailable(str(meta.get("overlay_kind", kind)), reason)
		elif kind == "causal_debugger" or kind == "causal_debugger_lineage":
			_emit_overlay_unavailable(kind, reason)
		elif kind == "branch_children" or kind == "branch_fork_point":
			branch_reason_code = reason
			branch_updated.emit()
		else:
			overlay_payload.emit(kind, null)
		return
	_request_serial += 1
	var request_id := str(_request_serial)
	var pending := {
		"kind": kind,
		"seek_id": int(meta.get("seek_id", -1)),
		"epoch": _http_epoch,
	}
	for key in meta.keys():
		pending[key] = meta[key]
	_pending[request_id] = pending
	_http.get_json(str(built["url"]), request_id, _token)


func _request(kind: String, query: Dictionary = {}, seek_id: int = -1) -> void:
	var route_name := kind
	if (
		kind == "gap"
		or kind == "events_window"
		or kind == "catch_up"
		or kind == "marker_events"
		or kind == "focus_events"
		or kind == "focus_seek"
		or kind == "focus_probe"
	):
		route_name = "events"
	if kind.begins_with("state"):
		route_name = "state"
	var path := "/v1/simulations/%s/observer/%s" % [run_id, route_name]
	var request_query := query
	if kind == "gap":
		request_query = {
			"limit": PAGE_LIMIT,
			"after_tick": cursor_after_tick,
			"after_sequence": cursor_after_sequence,
		}
	last_request = {"kind": kind, "query": request_query.duplicate()}
	request_log.append(last_request)
	if _http == null:
		return
	var built: Dictionary = Urls.build_get(origin, path, request_query)
	if not bool(built.get("ok", false)):
		if seek_id >= 0:
			ObserverLog.error(
				"session",
				"seek_failed reason_code=%s" % str(built.get("reason_code", "read_only")),
			)
		else:
			_fail(str(built.get("reason_code", "read_only")))
		return
	_request_serial += 1
	var request_id := str(_request_serial)
	_pending[request_id] = {"kind": kind, "seek_id": seek_id, "epoch": _http_epoch}
	_http.get_json(str(built["url"]), request_id, _token)


func _on_http(route: String, _status: int, body: Variant, reason_code: String) -> void:
	var meta: Dictionary = _pending.get(route, {})
	_pending.erase(route)
	if meta.is_empty():
		ObserverLog.debug("session", "http_ignored reason_code=unknown_route")
		return
	if int(meta.get("epoch", -1)) != _http_epoch:
		ObserverLog.debug("session", "http_ignored reason_code=stale_epoch")
		return
	var kind := str(meta.get("kind", ""))
	var seek_id := int(meta.get("seek_id", -1))
	if seek_id >= 0 and seek_id < _seek_serial:
		ObserverLog.debug("session", "seek_ignored reason_code=stale_response")
		return
	if (
		kind == "territorial_claims"
		or kind == "subjective_labels"
		or kind == "communication_strategy_audit"
		or kind == "relationships"
		or kind == "narrative_hops"
		or kind == "causal_debugger"
		or kind == "causal_debugger_lineage"
	):
		var overlay: Variant = null
		if reason_code == "" and typeof(body) == TYPE_DICTIONARY:
			overlay = body
			if kind == "causal_debugger":
				ObserverLog.debug(
					"observer.debugger",
					"causal_trace_response status=200 node_count=%s" % [
						(body.get("nodes", []) as Array).size(),
					],
				)
			elif kind == "causal_debugger_lineage":
				ObserverLog.debug(
					"observer.debugger",
					"lineage_response status=200 entry_count=%s" % [
						(body.get("entries", []) as Array).size(),
					],
				)
		elif reason_code != "":
			ObserverLog.warn(
				"session",
				"overlay_unavailable kind=%s reason_code=%s" % [kind, reason_code],
			)
			if kind == "causal_debugger" or kind == "causal_debugger_lineage":
				_emit_overlay_unavailable(
					kind,
					reason_code if reason_code != "" else "overlay_unavailable",
				)
				return
		overlay_payload.emit(kind, overlay)
		return
	if kind == "metric_catalog":
		var overlay_kind := str(meta.get("overlay_kind", ""))
		var family := str(meta.get("family", ""))
		if reason_code != "" or typeof(body) != TYPE_DICTIONARY:
			_emit_overlay_unavailable(overlay_kind, reason_code if reason_code != "" else "overlay_unavailable")
			return
		var metric_set_id := resolve_metric_set_id(body, family)
		if metric_set_id == "":
			_emit_overlay_unavailable(overlay_kind, "metric_family_missing")
			return
		ObserverLog.info(
			"session",
			"metric_catalog_resolved family=%s metric_set_id=%s" % [family, metric_set_id],
		)
		var doc_path := "/v1/simulations/%s/metrics/%s/%s" % [run_id, metric_set_id, family]
		_request_path(
			"metric_document",
			doc_path,
			{
				"family": family,
				"overlay_kind": overlay_kind,
				"metric_set_id": metric_set_id,
				"seek_id": -1,
			},
		)
		return
	if kind == "metric_document":
		var overlay_kind := str(meta.get("overlay_kind", ""))
		if reason_code != "" or typeof(body) != TYPE_DICTIONARY:
			_emit_overlay_unavailable(overlay_kind, reason_code if reason_code != "" else "overlay_unavailable")
			return
		var decoded: Variant = _decode_metric_document(body)
		if decoded == null:
			_emit_overlay_unavailable(overlay_kind, "metric_payload_invalid")
			return
		ObserverLog.debug(
			"session",
			"metric_document_loaded family=%s metric_set_id=%s overlay_kind=%s" % [
				str(meta.get("family", "")),
				str(meta.get("metric_set_id", "")),
				overlay_kind,
			],
		)
		overlay_payload.emit(overlay_kind, decoded)
		return
	if kind == "branch_children":
		if reason_code != "":
			branch_reason_code = reason_code
			if not bool(meta.get("append", false)):
				branch_children = []
				branch_next_cursor = null
			ObserverLog.warn(
				"session",
				"branch_children_failed reason_code=%s" % reason_code,
			)
			branch_updated.emit()
			return
		var parsed_children: Dictionary = Protocol.parse_branch_list(body)
		if not bool(parsed_children.get("ok", false)):
			branch_reason_code = str(parsed_children.get("reason_code", "invalid_json"))
			branch_updated.emit()
			return
		branch_reason_code = ""
		var items: Array = parsed_children.get("items", [])
		if bool(meta.get("append", false)):
			branch_children.append_array(items)
		else:
			branch_children = items
		branch_next_cursor = parsed_children.get("next_cursor", null)
		ObserverLog.debug(
			"session",
			"branch_children_loaded count=%s" % branch_children.size(),
		)
		branch_updated.emit()
		return
	if kind == "branch_fork_point":
		if reason_code != "":
			branch_reason_code = reason_code
			ObserverLog.warn(
				"session",
				"branch_fork_point_failed reason_code=%s" % reason_code,
			)
			branch_updated.emit()
			if reason_code == "not_found":
				status_changed.emit("branch_root", "No parent branch")
			return
		var fork: Dictionary = Protocol.parse_branch_fork_point(body)
		if not bool(fork.get("ok", false)):
			branch_reason_code = str(fork.get("reason_code", "invalid_json"))
			branch_updated.emit()
			return
		var parent_id := str(fork.get("parent_run_id", ""))
		var parent_tick := int(fork.get("parent_observer_tick", fork.get("fork_tick", 0)))
		ObserverLog.info(
			"session",
			"branch_open_parent parent_run_id=%s fork_tick=%s" % [
				parent_id, parent_tick,
			],
		)
		switch_run(parent_id, parent_tick, null, true)
		return
	if kind == "marker_events":
		if reason_code != "":
			ObserverLog.debug(
				"session",
				"marker_page_failed reason_code=%s" % reason_code,
			)
			_pump_marker_enrichment(_marker_serial)
			return
		var marker_page = Protocol.parse_event_page(body)
		if marker_page.ok:
			for event in marker_page.value.events:
				_marker_events.append(event)
		else:
			ObserverLog.debug(
				"session",
				"marker_page_failed reason_code=%s" % marker_page.reason_code,
			)
		_pump_marker_enrichment(_marker_serial)
		return
	if kind == "focus_events" or kind == "focus_seek" or kind == "focus_probe":
		if reason_code != "":
			if kind == "focus_seek" or kind == "focus_probe":
				status_changed.emit("no_focused_event", reason_code)
			_focus_nav = ""
			return
		var focus_page = Protocol.parse_event_page(body)
		if not focus_page.ok:
			_focus_nav = ""
			status_changed.emit("no_focused_event", focus_page.reason_code)
			return
		if kind == "focus_events":
			_event_window = focus_page.value.events
			events_loaded.emit(focus_page.value.events, transport.tick, int(transport.sequence) if transport.sequence != null else 0)
			return
		if kind == "focus_seek":
			var first: Variant = null
			for event in focus_page.value.events:
				if _event_matches_focus(event):
					first = event
					break
			_focus_nav = ""
			if first == null:
				status_changed.emit("no_focused_event", "No next focused event")
				return
			_seek_focus_event({"tick": int(first.tick), "sequence": int(first.sequence)})
			return
		# focus_probe: accept matching event strictly before the view cursor.
		var match: Variant = null
		var view_tick := transport.tick
		var view_sequence: Variant = transport.sequence
		for event in focus_page.value.events:
			if not _event_matches_focus(event):
				continue
			var tick := int(event.tick)
			var sequence := int(event.sequence)
			if tick > view_tick:
				continue
			if tick == view_tick and view_sequence != null and sequence >= int(view_sequence):
				continue
			if match == null or tick > int(match.tick) or (
				tick == int(match.tick) and sequence > int(match.sequence)
			):
				match = event
		if match != null:
			_focus_nav = ""
			_probe_sequence = null
			_seek_focus_event({"tick": int(match.tick), "sequence": int(match.sequence)})
			return
		if _probe_sequence != null and int(_probe_sequence) > 0:
			_probe_sequence = int(_probe_sequence) - 1
		elif _probe_tick > 0:
			_probe_tick -= 1
			_probe_sequence = 0
		else:
			_focus_nav = ""
			status_changed.emit("no_previous_focused_event", "No previous focused event")
			return
		_probe_previous_focused()
		return
	if reason_code != "":
		if seek_id >= 0:
			ObserverLog.error("session", "seek_failed reason_code=%s" % reason_code)
			return
		_fail(reason_code)
		return
	if kind == "manifest":
		var manifest = Protocol.parse_manifest(body)
		if not manifest.ok:
			_fail(manifest.reason_code)
			return
		var model = manifest.value
		if model != null and not str(model.run_id).is_empty():
			lineage = {
				"parent_run_id": str(model.parent_run_id),
				"fork_tick": int(model.fork_tick),
				"intervention_summary": str(model.intervention_summary),
				"branch_id": str(model.branch_id),
			}
			ObserverLog.debug(
				"session",
				"branch_lineage run_id=%s parent_run_id=%s fork_tick=%s" % [
					str(model.run_id),
					str(model.parent_run_id),
					str(model.fork_tick),
				],
			)
			branch_updated.emit()
			if not str(model.parent_run_id).is_empty():
				status_changed.emit(
					"loading",
					"branch of %s @%s" % [str(model.parent_run_id), str(model.fork_tick)],
				)
		_request("state")
		return
	if kind == "state" or kind == "state_refresh":
		var parsed = Protocol.parse_frame(body)
		if not parsed.ok:
			_fail(parsed.reason_code)
			return
		_adopt_frame(parsed.value, kind == "state")
		if kind == "state" and not _opened:
			_opened = true
			ObserverLog.info("session", "bootstrap_ready tick=%s" % str(world.tick))
			status_changed.emit("ready", "tick %s" % str(world.tick))
			if not _failed:
				_open_socket()
			fetch_branch_children()
			_apply_pending_switch_seek()
			_apply_pending_deeplink()
		return
	if kind == "state_cursor" or kind == "state_tick":
		var sought = Protocol.parse_frame(body)
		if not sought.ok:
			ObserverLog.error("session", "seek_failed reason_code=%s" % sought.reason_code)
			return
		_apply_sought_frame(sought.value, seek_id)
		return
	if kind == "catch_up":
		var caught = Protocol.parse_event_page(body)
		if not caught.ok:
			ObserverLog.error("session", "seek_failed reason_code=%s" % caught.reason_code)
			return
		var catch_count := 0
		for event in caught.value.events:
			_apply_live_event(event)
			catch_count += 1
		ObserverLog.info(
			"session",
			"reconnect_catchup events=%s" % catch_count,
		)
		transport.buffer_dropped = false
		transport.sync_behind()
		_request("state_refresh")
		if not transport.behind_live:
			status_changed.emit("ready", "tick %s" % str(world.tick if world != null else transport.tick))
		return
	if kind == "events_window":
		var window = Protocol.parse_event_page(body)
		if not window.ok:
			ObserverLog.error("session", "seek_failed reason_code=%s" % window.reason_code)
			return
		_event_window = window.value.events
		var meta_events: Dictionary = _seek_meta.get(seek_id, {})
		events_loaded.emit(
			window.value.events,
			int(meta_events.get("focus_tick", 0)),
			int(meta_events.get("focus_sequence", 0)),
		)
		return
	if kind == "ticks":
		if typeof(body) != TYPE_DICTIONARY:
			ObserverLog.error("session", "seek_failed reason_code=invalid_json")
			return
		var records: Array = body.get("ticks", [])
		ticks_loaded.emit(records)
		_finish_navigation(records)
		return
	if kind == "state_live":
		var live = Protocol.parse_frame(body)
		if not live.ok:
			ObserverLog.error("session", "seek_failed reason_code=%s" % live.reason_code)
			return
		transport.set_mode(TransportScript.MODE_LIVE)
		transport.set_paused(false)
		_adopt_frame(live.value, true)
		frame_sought.emit(live.value, null, false)
		_open_socket()
		return
	if kind == "run":
		if typeof(body) != TYPE_DICTIONARY:
			ObserverLog.error("session", "seek_failed reason_code=invalid_json")
			return
		var head_tick := int(body.get("tick", 0))
		transport.note_run_head(head_tick, body.get("latest_tick", null), body.get("latest_sequence", null))
		ObserverLog.debug("session", "live_head_polled tick=%s" % head_tick)
		if transport.behind_live:
			status_changed.emit("behind_live", "behind live")
		run_loaded.emit(body)
		return
	if kind == "gap":
		var page = Protocol.parse_event_page(body)
		if not page.ok:
			_fail(page.reason_code)
			return
		var previous_tick: Variant = cursor_after_tick
		var previous_sequence: Variant = cursor_after_sequence
		for event in page.value.events:
			_apply_live_event(event)
			_gap_events += 1
		var advanced: bool = cursor_after_tick != previous_tick or cursor_after_sequence != previous_sequence
		if page.value.events.size() < page.value.limit or not advanced:
			ObserverLog.info("stream", "gap_filled event_count=%s" % _gap_events)
			_gap_events = 0
			_request("state_refresh")
			_open_socket()
		else:
			_request("gap")


func _adopt_frame(frame: Variant, adopt_cursor: bool) -> void:
	world = frame.world
	if adopt_cursor:
		cursor_after_tick = frame.cursor.after_tick
		cursor_after_sequence = frame.cursor.after_sequence
		_view_transport(frame)
	world_replaced.emit(world)


func _apply_sought_frame(frame: Variant, seek_id: int) -> void:
	var meta: Dictionary = _seek_meta.get(seek_id, {})
	world = frame.world
	cursor_after_tick = frame.cursor.after_tick
	cursor_after_sequence = frame.cursor.after_sequence
	_view_transport(frame)
	var sequence_text := "null" if transport.sequence == null else str(int(transport.sequence))
	ObserverLog.info(
		"session",
		"seek_applied mode=%s tick=%s sequence=%s" % [transport.mode, transport.tick, sequence_text],
	)
	frame_sought.emit(frame, meta.get("event", null), bool(meta.get("forward", false)))
	if _playing:
		_schedule_step()


func _view_transport(frame: Variant) -> void:
	if frame.cursor.after_tick == null:
		transport.tick = int(frame.world.tick)
		transport.view_event(null, null)
	else:
		transport.view_event(frame.cursor.after_tick, frame.cursor.after_sequence)


func _open_socket() -> void:
	if _failed or world == null:
		return
	var path := "/v1/simulations/%s/observer/stream" % run_id
	var after_tick: Variant = cursor_after_tick
	var after_sequence: Variant = cursor_after_sequence
	if Urls.resume_allowed(after_tick, after_sequence) and int(after_tick) >= int(world.tick):
		# Sending this pair closes the socket with 4409. Omit it so the server keeps its own cursor.
		after_tick = null
		after_sequence = null
	var built: Dictionary = Urls.build_websocket(origin, path, after_tick, after_sequence, int(world.tick))
	if not bool(built.get("connect", false)):
		status_changed.emit(str(built.get("reason_code", "cursor_ahead")), str(built.get("reason_code", "")))
		return
	_stream.open_stream(str(built["url"]), _token, run_id, after_tick, after_sequence)


func _on_envelope(payload: Dictionary) -> void:
	if transport.mode == TransportScript.MODE_REPLAY:
		return
	var kind := str(payload.get("kind", ""))
	match kind:
		"hello":
			var parsed = Protocol.parse_frame(payload.get("frame", null))
			if not parsed.ok:
				_fail(parsed.reason_code)
				return
			if _hello_is_newer(parsed.value.cursor):
				_adopt_frame(parsed.value, true)
		"event":
			var parsed_event = Protocol.parse_event(payload.get("event", null))
			if not parsed_event.ok:
				status_changed.emit(parsed_event.reason_code, parsed_event.reason_code)
				return
			if transport.mode == TransportScript.MODE_LIVE and transport.paused:
				_buffer_live_event(parsed_event.value)
				return
			_apply_live_event(parsed_event.value)
		"tick":
			if transport.paused or transport.mode == TransportScript.MODE_REPLAY:
				return
			_request("state_refresh")
		"heartbeat":
			pass
		"rejected":
			status_changed.emit("client_mutation_rejected", "client_mutation_rejected")
		"completion":
			status_changed.emit("completion", "completion")
			_stream.close_stream(false)
		_:
			ObserverLog.warn("stream", "envelope kind=%s tick=- sequence=-" % kind)


func _buffer_live_event(event: Variant) -> void:
	if _live_buffer.size() >= BUFFER_LIMIT:
		var count := _live_buffer.size()
		_live_buffer.clear()
		transport.mark_buffer_dropped()
		ObserverLog.warn(
			"session",
			"live_buffer_discarded count=%s reason_code=buffer_limit" % count,
		)
		status_changed.emit("behind_live", "behind live")
		return
	_live_buffer.append(event)


func _catch_up_live() -> void:
	_live_buffer.clear()
	var query := {"limit": PAGE_LIMIT, "catch_up": true}
	if Urls.resume_allowed(cursor_after_tick, cursor_after_sequence):
		query["after_tick"] = cursor_after_tick
		query["after_sequence"] = cursor_after_sequence
	_request("catch_up", query, -1)


func _apply_live_event(event: Variant) -> void:
	var decision: Dictionary = Cursor.consider(
		int(event.tick),
		int(event.sequence),
		cursor_after_tick,
		cursor_after_sequence,
	)
	if not bool(decision["applied"]):
		return
	cursor_after_tick = decision["after_tick"]
	cursor_after_sequence = decision["after_sequence"]
	if transport.mode == TransportScript.MODE_LIVE:
		transport.view_event(int(event.tick), int(event.sequence))
	live_event.emit(event)


func _hello_is_newer(cursor: Variant) -> bool:
	if world == null or cursor == null:
		return true
	var current_sequence := -1
	if cursor_after_sequence != null:
		current_sequence = int(cursor_after_sequence)
	var incoming_sequence := -1
	if cursor.sequence != null:
		incoming_sequence = int(cursor.sequence)
	return Cursor.is_strictly_after(int(cursor.tick), incoming_sequence, int(world.tick), current_sequence)


func _on_socket_closed(reason_code: String) -> void:
	if _failed:
		return
	if CLOSE_REASONS.has(reason_code):
		var mapped := str(CLOSE_REASONS[reason_code])
		status_changed.emit(mapped, mapped)
		return
	if reason_code == "client_stop":
		return
	_schedule_gap_fill()


func play() -> void:
	transport.set_paused(false)
	if transport.mode == TransportScript.MODE_LIVE:
		_playing = false
		if transport.buffer_dropped:
			_catch_up_live()
			return
		for event in _live_buffer:
			_apply_live_event(event)
		_live_buffer.clear()
		return
	_playing = true
	_schedule_step()


func pause() -> void:
	_playing = false
	transport.set_paused(true)
	if _play_timer != null:
		_play_timer.stop()
	if transport.mode == TransportScript.MODE_LIVE:
		var sequence_text := "null" if transport.sequence == null else str(int(transport.sequence))
		ObserverLog.info(
			"session",
			"live_paused tick=%s sequence=%s" % [transport.tick, sequence_text],
		)


func next_event() -> void:
	if transport.speed >= TransportScript.WHOLE_TICK_SPEED:
		next_tick()
		return
	var neighbor := _next_tick_record(transport.tick)
	var target: Dictionary = TransportScript.next_event(
		transport.tick,
		transport.sequence,
		_last_sequence(transport.tick),
		neighbor.get("tick", null),
		neighbor.get("first", null),
	)
	if target["found"]:
		_seek_target(target)
		return
	_navigation = "next_event"
	fetch_ticks(transport.tick, transport.tick + 1, _seek_serial)


func previous_event() -> void:
	if transport.sequence != null and int(transport.sequence) > 0:
		var target := TransportScript.previous_event(transport.tick, transport.sequence, null, null)
		_seek_target(target)
		return
	if transport.tick <= 0:
		return
	_navigation = "previous_event"
	fetch_ticks(maxi(transport.tick - 1, 0), transport.tick, _seek_serial)


func next_tick() -> void:
	var neighbor := _next_tick_record(transport.tick)
	var target: Dictionary = TransportScript.next_tick(neighbor.get("tick", null), neighbor.get("last", null))
	if target["found"]:
		_seek_target(target)
		return
	_navigation = "next_tick"
	fetch_ticks(transport.tick, transport.tick + 1, _seek_serial)


func previous_tick() -> void:
	if transport.tick <= 0:
		return
	var neighbor := _previous_tick_record(transport.tick)
	var target: Dictionary = TransportScript.previous_tick(neighbor.get("tick", null), neighbor.get("last", null))
	if target["found"]:
		_seek_target(target)
		return
	_navigation = "previous_tick"
	fetch_ticks(maxi(transport.tick - 1, 0), transport.tick, _seek_serial)


func jump_to_tick(event_tick: int) -> void:
	seek_tick(event_tick)


func jump_to_event(event_tick: int, event_sequence: int) -> void:
	seek_event(event_tick, event_sequence, _known_event(event_tick, event_sequence))


func return_to_live() -> void:
	_playing = false
	if _play_timer != null:
		_play_timer.stop()
	_live_buffer.clear()
	transport.clear_behind()
	var sequence_text := "null" if transport.sequence == null else str(int(transport.sequence))
	ObserverLog.info(
		"session",
		"return_to_live tick=%s sequence=%s" % [transport.tick, sequence_text],
	)
	transport.set_paused(false)
	transport.set_mode(TransportScript.MODE_LIVE)
	_seek_serial += 1
	_request("state_live", {}, _seek_serial)
	fetch_run(_seek_serial)


func set_speed(next_speed: float) -> void:
	transport.set_speed(next_speed)


func _poll_live_head() -> void:
	if transport.mode != TransportScript.MODE_REPLAY or run_id == "":
		return
	fetch_run(-1)


func _schedule_step() -> void:
	if not _playing or transport.paused or transport.mode != TransportScript.MODE_REPLAY:
		return
	if _play_timer == null:
		return
	var policy: Dictionary = Playback.policy(transport.speed, 0)
	var delay := 0.05 if bool(policy.get("skip", false)) else maxf(float(policy.get("duration", 0.6)), 0.05)
	_play_timer.start(delay)


func _on_play_step() -> void:
	if not _playing or transport.paused or transport.mode != TransportScript.MODE_REPLAY:
		return
	next_event()


func _seek_target(target: Dictionary) -> void:
	if not bool(target.get("found", false)):
		_playing = false
		return
	seek_event(int(target["tick"]), int(target["sequence"]), _known_event(int(target["tick"]), int(target["sequence"])))


func _finish_navigation(records: Array) -> void:
	var action := _navigation
	_navigation = ""
	if action == "":
		return
	var current := transport.tick
	var target: Dictionary = {}
	if action == "next_event":
		var nxt := _record_after(records, current)
		target = TransportScript.next_event(
			current,
			transport.sequence,
			_record_last(records, current),
			nxt.get("tick", null),
			nxt.get("first", null),
		)
	elif action == "next_tick":
		var nxt := _record_after(records, current)
		target = TransportScript.next_tick(nxt.get("tick", null), nxt.get("last", null))
	elif action == "previous_event":
		var prev := _record_before(records, current)
		target = TransportScript.previous_event(
			current,
			transport.sequence,
			prev.get("tick", null),
			prev.get("last", null),
		)
	elif action == "previous_tick":
		var prev := _record_before(records, current)
		target = TransportScript.previous_tick(prev.get("tick", null), prev.get("last", null))
	elif action == "focus_previous_tick":
		var prev := _record_before(records, _probe_tick)
		target = TransportScript.previous_event(
			_probe_tick,
			_probe_sequence,
			prev.get("tick", null),
			prev.get("last", null),
		)
		if target.is_empty() or not bool(target.get("found", false)):
			_focus_nav = ""
			status_changed.emit("no_previous_focused_event", "No previous focused event")
			return
		_probe_tick = int(target["tick"])
		_probe_sequence = int(target["sequence"])
		_probe_previous_focused()
		return
	if target.is_empty() or not bool(target.get("found", false)):
		_playing = false
		return
	_seek_target(target)


func _known_event(event_tick: int, event_sequence: int) -> Variant:
	for event in _event_window:
		if int(event.tick) == event_tick and int(event.sequence) == event_sequence:
			return event
	return null


func _last_sequence(event_tick: int) -> Variant:
	var last: Variant = null
	for event in _event_window:
		if int(event.tick) == event_tick:
			last = int(event.sequence)
	return last


func _next_tick_record(event_tick: int) -> Dictionary:
	var found: Variant = null
	var first: Variant = null
	var last: Variant = null
	for event in _event_window:
		var item_tick := int(event.tick)
		if item_tick <= event_tick:
			continue
		if found == null or item_tick < int(found):
			found = item_tick
			first = int(event.sequence)
			last = int(event.sequence)
		elif item_tick == int(found):
			first = mini(int(first), int(event.sequence))
			last = maxi(int(last), int(event.sequence))
	if found == null:
		return {}
	return {"tick": found, "first": first, "last": last}


func _previous_tick_record(event_tick: int) -> Dictionary:
	var found: Variant = null
	var last: Variant = null
	for event in _event_window:
		var item_tick := int(event.tick)
		if item_tick >= event_tick:
			continue
		if found == null or item_tick > int(found):
			found = item_tick
			last = int(event.sequence)
		elif item_tick == int(found):
			last = maxi(int(last), int(event.sequence))
	if found == null:
		return {}
	return {"tick": found, "last": last}


func _record_after(records: Array, event_tick: int) -> Dictionary:
	var found: Variant = null
	var row: Dictionary = {}
	for record in records:
		if typeof(record) != TYPE_DICTIONARY:
			continue
		var item_tick := int(record.get("tick", -1))
		if item_tick <= event_tick:
			continue
		if found == null or item_tick < int(found):
			found = item_tick
			row = record
	if found == null:
		return {}
	return {
		"tick": int(row.get("tick", 0)),
		"first": int(row.get("first_sequence", 0)),
		"last": int(row.get("last_sequence", 0)),
	}


func _record_before(records: Array, event_tick: int) -> Dictionary:
	var found: Variant = null
	var row: Dictionary = {}
	for record in records:
		if typeof(record) != TYPE_DICTIONARY:
			continue
		var item_tick := int(record.get("tick", -1))
		if item_tick >= event_tick:
			continue
		if found == null or item_tick > int(found):
			found = item_tick
			row = record
	if found == null:
		return {}
	return {
		"tick": int(row.get("tick", 0)),
		"first": int(row.get("first_sequence", 0)),
		"last": int(row.get("last_sequence", 0)),
	}


func _record_last(records: Array, event_tick: int) -> Variant:
	for record in records:
		if typeof(record) != TYPE_DICTIONARY:
			continue
		if int(record.get("tick", -1)) == event_tick:
			return int(record.get("last_sequence", 0))
	return _last_sequence(event_tick)


func accepts_gap() -> bool:
	return transport.mode == TransportScript.MODE_LIVE and not transport.paused


func _schedule_gap_fill() -> void:
	if not accepts_gap():
		ObserverLog.debug("stream", "gap_ignored reason_code=replay_cursor")
		return
	# Headless doubles are not in the tree, so they cannot wait on a scene timer.
	if not is_inside_tree():
		_open_gap()
		return
	if _reconnect_pending:
		return
	_reconnect_pending = true
	await get_tree().create_timer(0.5).timeout
	_reconnect_pending = false
	_open_gap()


func _open_gap() -> void:
	if _failed or not accepts_gap():
		return
	if not Urls.resume_allowed(cursor_after_tick, cursor_after_sequence):
		_open_socket()
		return
	if world != null and int(cursor_after_tick) >= int(world.tick):
		_open_socket()
		return
	_gap_events = 0
	_request("gap")
