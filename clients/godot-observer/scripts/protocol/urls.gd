extends RefCounted
class_name ObserverUrls

const ObserverLog := preload("res://scripts/log.gd")

## GET-only origin joining. Resume parameters are a pair, or neither.


static func build_get(origin: String, path: String, query: Dictionary = {}) -> Dictionary:
	return _build(origin, path, query, "GET")


static func build(origin: String, path: String, query: Dictionary = {}, method: String = "GET") -> Dictionary:
	return _build(origin, path, query, method)


static func build_websocket(
	origin: String,
	path: String,
	after_tick: Variant,
	after_sequence: Variant,
	world_tick: int,
) -> Dictionary:
	var query := {}
	if resume_allowed(after_tick, after_sequence):
		if int(after_tick) >= world_tick:
			ObserverLog.debug("net", "url_built route=%s" % path)
			return {
				"ok": false,
				"connect": false,
				"method": "GET",
				"route": path,
				"reason_code": "cursor_ahead",
				"url": "",
			}
		query["after_tick"] = int(after_tick)
		query["after_sequence"] = int(after_sequence)
	var built := _build(origin, path, query, "GET")
	built["connect"] = bool(built.get("ok", false))
	built["url"] = _websocket_scheme(str(built.get("url", "")))
	return built


static func next_page_cursor(page: Dictionary) -> Dictionary:
	var events: Array = page.get("events", [])
	var limit := int(page.get("limit", 0))
	if events.size() < limit:
		return {"done": true}
	var last: Variant = events[events.size() - 1]
	var tick: Variant = _field(last, "tick")
	var sequence: Variant = _field(last, "sequence")
	return {"done": false, "after_tick": tick, "after_sequence": sequence}


static func walk_pages(pages: Array) -> Dictionary:
	var cursors: Array = []
	var event_count := 0
	var done := false
	for page in pages:
		var events: Array = page.get("events", [])
		event_count += events.size()
		var nxt := next_page_cursor(page)
		if bool(nxt.get("done", false)):
			done = true
			break
		cursors.append(nxt)
	return {"done": done, "cursors": cursors, "event_count": event_count}


static func _build(origin: String, path: String, query: Dictionary, method: String) -> Dictionary:
	var route := path
	ObserverLog.debug("net", "url_built route=%s" % route)
	if method != "GET":
		return {
			"ok": false,
			"method": method,
			"route": route,
			"url": "",
			"reason_code": "read_only",
		}
	var params := {}
	var allowed := [
		"limit",
		"tick",
		"layout_id",
		"through_sequence",
		"from_tick",
		"to_tick",
		"agent_id",
		"event_type",
		"location_id",
		"after_child_run_id",
		"sequence",
	]
	for key in query.keys():
		var name := str(key)
		if name not in allowed:
			continue
		if query[key] == null:
			continue
		params[name] = query[key]
	if resume_allowed(query.get("after_tick", null), query.get("after_sequence", null)):
		params["after_tick"] = int(query["after_tick"])
		params["after_sequence"] = int(query["after_sequence"])
	var url := _join(origin, path)
	if not params.is_empty():
		url += "?" + _encode(params)
	return {"ok": true, "method": "GET", "route": route, "url": url, "reason_code": ""}


static func resume_allowed(after_tick: Variant, after_sequence: Variant) -> bool:
	if after_tick == null or after_sequence == null:
		return false
	if int(after_sequence) < 0 or int(after_tick) < 0:
		return false
	return true


static func _join(origin: String, path: String) -> String:
	var base := origin.strip_edges().trim_suffix("/")
	var suffix := path if path.begins_with("/") else "/" + path
	return base + suffix


static func _websocket_scheme(url: String) -> String:
	if url.begins_with("https://"):
		return "wss://" + url.substr(8)
	if url.begins_with("http://"):
		return "ws://" + url.substr(7)
	return url


static func _encode(params: Dictionary) -> String:
	var parts: PackedStringArray = []
	for key in params.keys():
		parts.append("%s=%s" % [str(key), str(params[key]).uri_encode()])
	return "&".join(parts)


static func _field(value: Variant, key: String) -> Variant:
	if value is Dictionary:
		return value.get(key, null)
	return value.get(key)
