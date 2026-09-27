extends Node

const ObserverLog := preload("res://scripts/log.gd")

signal envelope_received(payload: Dictionary)
signal socket_closed(reason_code: String)

var _peer: WebSocketPeer
var _connected := false
var _announced := false
var _run_id := ""
var _after_tick: Variant = null
var _after_sequence: Variant = null


func open_stream(url: String, token: String, run_id: String, after_tick: Variant, after_sequence: Variant) -> void:
	close_stream(false)
	_run_id = run_id
	_after_tick = after_tick
	_after_sequence = after_sequence
	_peer = WebSocketPeer.new()
	var protocols := PackedStringArray(["palimpsest.v1"])
	if not token.is_empty():
		protocols.append("palimpsest.token.%s" % token)
	_peer.supported_protocols = protocols
	var err := _peer.connect_to_url(url)
	if err != OK:
		_peer = null
		ObserverLog.warn("stream", "socket_closed reason_code=request_failed")
		socket_closed.emit("request_failed")
		return
	_announced = false


func close_stream(log_close: bool = true) -> void:
	_connected = false
	if _peer != null:
		_peer.close()
		_peer = null
	if log_close:
		ObserverLog.warn("stream", "socket_closed reason_code=client_stop")


func _process(_delta: float) -> void:
	if _peer == null:
		return
	_peer.poll()
	var state := _peer.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		if not _announced:
			_announced = true
			ObserverLog.info(
				"stream",
				"socket_opened run_id=%s after_tick=%s after_sequence=%s" % [
					_run_id, _fmt(_after_tick), _fmt(_after_sequence),
				],
			)
		_connected = true
		while _peer.get_available_packet_count() > 0:
			var text := _peer.get_packet().get_string_from_utf8()
			var parsed: Variant = JSON.parse_string(text)
			if typeof(parsed) != TYPE_DICTIONARY:
				ObserverLog.warn("stream", "envelope kind=invalid tick=- sequence=-")
				continue
			var kind := str(parsed.get("kind", ""))
			ObserverLog.debug(
				"stream",
				"envelope kind=%s tick=%s sequence=%s" % [
					kind, _fmt(parsed.get("tick", null)), _fmt(_sequence_of(parsed)),
				],
			)
			envelope_received.emit(parsed)
	elif state == WebSocketPeer.STATE_CLOSED:
		var code := _peer.get_close_code()
		_peer = null
		_connected = false
		var reason := str(code)
		if code == -1:
			reason = "socket_lost"
		ObserverLog.warn("stream", "socket_closed reason_code=%s" % reason)
		socket_closed.emit(reason)


func _sequence_of(payload: Dictionary) -> Variant:
	if payload.has("sequence"):
		return payload.get("sequence")
	var event = payload.get("event", null)
	if event is Dictionary:
		return event.get("sequence", null)
	return payload.get("after_sequence", null)


func _fmt(value: Variant) -> String:
	if value == null:
		return "null"
	return str(value)
