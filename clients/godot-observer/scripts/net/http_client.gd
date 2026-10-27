extends Node

const ObserverLog := preload("res://scripts/log.gd")

## Closed allowlist of API problem codes safe to surface in presentation state.
const SAFE_ERROR_CODES := [
	"cursor_ahead_of_high_water",
	"demographics_unknown_section",
	"incomplete_demographic_cursor",
	"incomplete_event_cursor",
	"invalid_lineage_cursor",
	"invalid_lineage_query",
	"invalid_lineage_scope",
	"invalid_marker_tick",
	"invalid_native_filter",
	"invalid_native_kind",
	"invalid_observer_query",
	"invalid_page_limit",
	"invalid_participant_role",
	"invalid_tick_range",
	"labels_unavailable_at_tick",
	"limit_exceeds_maximum",
	"lineage_digest_mismatch",
	"lineage_disabled",
	"lineage_publication_conflict",
	"lineage_record_oversize",
	"lineage_response_too_large",
	"lineage_root_not_found",
	"lineage_scope_mismatch",
	"lineage_snapshot_corrupt",
	"lineage_source_budget",
	"lineage_storage_unavailable",
	"lineage_writer_busy",
	"observer_demographics_response_too_large",
	"observer_event_not_found",
	"observer_relationships_unavailable",
	"run_not_found",
	"snapshot_unavailable",
	"symbolic_unavailable_at_tick",
	"tick_range_exceeds_maximum",
]

const MAX_QUEUED_REQUESTS := 32

signal get_completed(route: String, status: int, body: Variant, reason_code: String)

var _http: HTTPRequest
var _queue: Array = []
var _active: Dictionary = {}
var _request_count := 0
var _response_count := 0
var _response_bytes := 0
var _response_peak_bytes := 0


func _ready() -> void:
	_http = HTTPRequest.new()
	_http.timeout = 20.0
	add_child(_http)
	_http.request_completed.connect(_on_completed)


func get_json(url: String, route: String, token: String, expected_root: String = "object") -> void:
	if expected_root not in ["object", "array"]:
		expected_root = "object"
	if _queue.size() >= MAX_QUEUED_REQUESTS:
		var dropped: Dictionary = _queue.pop_front()
		ObserverLog.warn(
			"http",
			"queue_saturated dropped=1 limit=%s" % MAX_QUEUED_REQUESTS,
		)
		get_completed.emit(str(dropped.get("route", "")), 0, null, "queue_saturated")
	_queue.append({
		"url": url,
		"route": route,
		"token": token,
		"expected_root": expected_root,
	})
	_request_count += 1
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
	_response_count += 1
	_response_bytes += body.size()
	_response_peak_bytes = maxi(_response_peak_bytes, body.size())
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


func resource_snapshot() -> Dictionary:
	## Bounded diagnostics only: counts and response bytes, never payload bodies.
	return {
		"active": 0 if _active.is_empty() else 1,
		"queued": _queue.size(),
		"queued_limit": MAX_QUEUED_REQUESTS,
		"requests": _request_count,
		"responses": _response_count,
		"response_bytes": _response_bytes,
		"response_peak_bytes": _response_peak_bytes,
	}


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
	if code not in SAFE_ERROR_CODES:
		return ""
	return code
