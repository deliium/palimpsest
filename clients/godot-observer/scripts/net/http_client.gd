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


func get_json(url: String, route: String, token: String, expected_root: String = "object") -> void:
	if expected_root not in ["object", "array"]:
		expected_root = "object"
	_queue.append({
		"url": url,
		"route": route,
		"token": token,
		"expected_root": expected_root,
	})
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
	var headers := build_headers(str(_active.get("token", "")))
	var err := _http.request(str(_active["url"]), headers, HTTPClient.METHOD_GET)
	if err != OK:
		var route := str(_active["route"])
		_active = {}
		ObserverLog.debug("http", "get_finished route=%s status=%s" % [route, 0])
		get_completed.emit(route, 0, null, "request_failed")
		_pump()


func _on_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var route := str(_active.get("route", ""))
	var expected_root := str(_active.get("expected_root", "object"))
	_active = {}
	ObserverLog.debug("http", "get_finished route=%s status=%s" % [route, response_code])
	var reason := ""
	var parsed: Variant = null
	if result != HTTPRequest.RESULT_SUCCESS:
		reason = "request_failed"
	elif response_code < 200 or response_code >= 300:
		reason = error_reason(response_code, body)
	else:
		var parsed_result := parse_success(body, expected_root)
		parsed = parsed_result["value"]
		reason = str(parsed_result["reason_code"])
	get_completed.emit(route, response_code, parsed, reason)
	_pump()


static func build_headers(token: String) -> PackedStringArray:
	var headers := PackedStringArray(["Accept: application/json"])
	if not token.is_empty():
		headers.append("x-palimpsest-token: %s" % token)
	return headers


static func parse_success(body: PackedByteArray, expected_root: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	var expected := TYPE_ARRAY if expected_root == "array" else TYPE_DICTIONARY
	if typeof(parsed) != expected:
		return {"value": null, "reason_code": "invalid_json"}
	return {"value": parsed, "reason_code": ""}


static func error_reason(status: int, body: PackedByteArray) -> String:
	## Never leak the raw error body; only a bounded stable code is forwarded.
	if status == 401:
		return "unauthorized"
	if status == 403:
		return "forbidden"
	if status == 404:
		return "not_found"
	if status == 409:
		return "cursor_ahead"
	if status == 410:
		return "gone"
	var code := safe_error_code(body)
	if not code.is_empty():
		return code
	return "http_%s" % status


static func safe_error_code(body: PackedByteArray) -> String:
	var text := body.get_string_from_utf8()
	if text.is_empty() or text.length() > 4096:
		return ""
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return ""
	var raw: Variant = parsed.get("code")
	if typeof(raw) != TYPE_STRING:
		return ""
	var code := str(raw)
	if code.is_empty() or code.length() > 128:
		return ""
	for index in code.length():
		var character := code[index]
		var allowed := (
			(character >= "a" and character <= "z")
			or (character >= "0" and character <= "9")
			or character == "_"
		)
		if not allowed:
			return ""
	return code
