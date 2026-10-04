extends Node

const ObserverLog := preload("res://scripts/log.gd")

signal get_completed(route: String, status: int, body: Variant, reason_code: String)

var _http: HTTPRequest
var _queue: Array = []
var _active: Dictionary = {}


func _ready() -> void:
	_http = HTTPRequest.new()
	_http.timeout = 20.0
	add_child(_http)
	_http.request_completed.connect(_on_completed)


func get_json(url: String, route: String, token: String) -> void:
	_queue.append({"url": url, "route": route, "token": token})
	ObserverLog.debug("http", "queued route=%s depth=%s" % [route, _queue.size()])
	_pump()


func clear_queue() -> void:
	## Drop pending GETs. In-flight completion is ignored by the session epoch.
	var dropped := _queue.size()
	_queue.clear()
	ObserverLog.debug("http", "queue_cleared dropped=%s in_flight=%s" % [
		dropped,
		0 if _active.is_empty() else 1,
	])


func _pump() -> void:
	if not _active.is_empty() or _queue.is_empty():
		return
	_active = _queue.pop_front()
	var headers := PackedStringArray(["Accept: application/json"])
	var token := str(_active.get("token", ""))
	if not token.is_empty():
		headers.append("x-palimpsest-token: %s" % token)
	var err := _http.request(str(_active["url"]), headers, HTTPClient.METHOD_GET)
	if err != OK:
		var route := str(_active["route"])
		_active = {}
		ObserverLog.debug("http", "get_finished route=%s status=%s" % [route, 0])
		get_completed.emit(route, 0, null, "request_failed")
		_pump()


func _on_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var route := str(_active.get("route", ""))
	_active = {}
	ObserverLog.debug("http", "get_finished route=%s status=%s" % [route, response_code])
	var reason := ""
	var parsed: Variant = null
	if result != HTTPRequest.RESULT_SUCCESS:
		reason = "request_failed"
	elif response_code == 401 or response_code == 403:
		reason = "unauthorized"
	elif response_code == 404:
		reason = "not_found"
	elif response_code == 409:
		reason = "cursor_ahead"
	elif response_code < 200 or response_code >= 300:
		reason = "http_%s" % response_code
	else:
		parsed = JSON.parse_string(body.get_string_from_utf8())
		if typeof(parsed) != TYPE_DICTIONARY:
			reason = "invalid_json"
			parsed = null
	get_completed.emit(route, response_code, parsed, reason)
	_pump()
