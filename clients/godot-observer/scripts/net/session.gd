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

const PAGE_LIMIT := 50
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
signal live_event(event: Variant)
signal frame_sought(frame: Variant, event: Variant, forward: bool)
signal events_loaded(events: Array, focus_tick: int, focus_sequence: int)
signal ticks_loaded(ticks: Array)
signal run_loaded(record: Dictionary)

var run_id := ""
var origin := ""
var world: Variant = null
var cursor_after_tick: Variant = null
var cursor_after_sequence: Variant = null
var transport = TransportScript.new()

var _token := ""
var _http: Node
var _stream: Node
var _pending := {}
var _seek_meta := {}
var _request_serial := 0
var _seek_serial := 0
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
	var parsed := Origin.web_run_id(search)
	if parsed.is_empty():
		return false
	run_id = parsed
	ObserverLog.info("session", "web_run_id_applied run_id=%s" % run_id)
	run_id_applied.emit(run_id)
	_start()
	return true


func start_with_run_id(requested: String) -> void:
	var trimmed := requested.strip_edges()
	if not trimmed.is_empty():
		run_id = trimmed
	_failed = false
	_opened = false
	_start()


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
	var before := _events_before(event_tick, event_sequence)
	fetch_events(before.get("after_tick", null), before.get("after_sequence", null), _seek_serial)


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


func _request(kind: String, query: Dictionary = {}, seek_id: int = -1) -> void:
	var route_name := kind
	if kind == "gap" or kind == "events_window" or kind == "catch_up":
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
	_pending[request_id] = {"kind": kind, "seek_id": seek_id}
	_http.get_json(str(built["url"]), request_id, _token)


func _on_http(route: String, _status: int, body: Variant, reason_code: String) -> void:
	var meta: Dictionary = _pending.get(route, {})
	_pending.erase(route)
	if meta.is_empty():
		return
	var kind := str(meta.get("kind", ""))
	var seek_id := int(meta.get("seek_id", -1))
	if seek_id >= 0 and seek_id < _seek_serial:
		ObserverLog.debug("session", "seek_ignored reason_code=stale_response")
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
		for event in caught.value.events:
			_apply_live_event(event)
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
	var query := {"limit": EVENT_WINDOW}
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
