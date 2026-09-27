extends Node

const ObserverLog := preload("res://scripts/log.gd")
const Protocol := preload("res://scripts/protocol/models.gd")
const Urls := preload("res://scripts/protocol/urls.gd")
const Cursor := preload("res://scripts/protocol/cursor.gd")
const Origin := preload("res://scripts/net/origin.gd")
const HttpClient := preload("res://scripts/net/http_client.gd")
const StreamClient := preload("res://scripts/net/stream_client.gd")

const PAGE_LIMIT := 50
const CLOSE_REASONS := {
	"4400": "invalid_cursor",
	"4401": "unauthorized",
	"4404": "not_found",
	"4409": "cursor_ahead",
}

signal status_changed(code: String, detail: String)
signal world_replaced(world: Variant)
signal live_event(event: Variant)

var run_id := ""
var origin := ""
var world: Variant = null
var cursor_after_tick: Variant = null
var cursor_after_sequence: Variant = null

var _token := ""
var _http: Node
var _stream: Node
var _inflight := {}
var _opened := false
var _failed := false
var _gap_events := 0
var _reconnect_pending := false


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


func begin() -> void:
	var configured := str(ProjectSettings.get_setting("palimpsest/run_id", "")).strip_edges()
	if run_id.is_empty():
		run_id = configured
	_start()


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
	ObserverLog.info("session", "bootstrap_started run_id=%s" % run_id)
	_request("manifest")


func _fail(reason_code: String) -> void:
	_failed = true
	if _opened:
		ObserverLog.error("session", "session_failed reason_code=%s" % reason_code)
	else:
		ObserverLog.error("session", "bootstrap_failed reason_code=%s" % reason_code)
	status_changed.emit(reason_code, reason_code)


func _request(kind: String) -> void:
	var route_name := "events" if kind == "gap" else ("state" if kind.begins_with("state") else kind)
	var path := "/v1/simulations/%s/observer/%s" % [run_id, route_name]
	var query := {}
	if kind == "gap":
		query = {
			"limit": PAGE_LIMIT,
			"after_tick": cursor_after_tick,
			"after_sequence": cursor_after_sequence,
		}
	var built: Dictionary = Urls.build_get(origin, path, query)
	_inflight[path] = kind
	_http.get_json(str(built["url"]), path, _token)


func _on_http(route: String, _status: int, body: Variant, reason_code: String) -> void:
	var kind := str(_inflight.get(route, ""))
	_inflight.erase(route)
	if kind.is_empty():
		return
	if reason_code != "":
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
	world_replaced.emit(world)


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
			_apply_live_event(parsed_event.value)
		"tick":
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


func _schedule_gap_fill() -> void:
	if _reconnect_pending:
		return
	_reconnect_pending = true
	await get_tree().create_timer(0.5).timeout
	_reconnect_pending = false
	if _failed:
		return
	if not Urls.resume_allowed(cursor_after_tick, cursor_after_sequence):
		_open_socket()
		return
	if world != null and int(cursor_after_tick) >= int(world.tick):
		_open_socket()
		return
	_gap_events = 0
	_request("gap")
