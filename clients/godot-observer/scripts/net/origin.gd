extends RefCounted
class_name ObserverOrigin


static func resolve() -> String:
	if OS.has_feature("web"):
		return page_origin()
	var configured: Variant = ProjectSettings.get_setting("palimpsest/observer_origin", "")
	if configured == null:
		return ""
	return str(configured).strip_edges()


static func page_origin() -> String:
	if not OS.has_feature("web"):
		return ""
	var raw: Variant = JavaScriptBridge.eval("window.location.origin", true)
	if raw == null:
		return ""
	return str(raw).strip_edges()


static func web_search() -> String:
	if not OS.has_feature("web"):
		return ""
	var raw: Variant = JavaScriptBridge.eval("window.location.search", true)
	if raw == null:
		return ""
	return str(raw)


static func web_run_id(search: String) -> String:
	var state := web_debugger_state(search)
	return str(state.get("run_id", ""))


static func web_debugger_state(search: String) -> Dictionary:
	## Parse credential-free deep-link params. UI event N = sequence.
	var text := search.strip_edges()
	if text.begins_with("?"):
		text = text.substr(1)
	var out := {
		"run_id": "",
		"tick": null,
		"sequence": null,
		"event_id": "",
		"agent_id": "",
		"open_debugger": false,
		"reason_code": "",
	}
	if text.is_empty():
		return out
	var secret_keys := {
		"token": true,
		"credential": true,
		"credentials": true,
		"secret": true,
		"api_key": true,
		"apikey": true,
		"authorization": true,
		"password": true,
		"access_token": true,
	}
	for part in text.split("&", false):
		var pair := part.split("=", true, 1)
		if pair.is_empty():
			continue
		var key := str(pair[0]).uri_decode()
		if secret_keys.has(key):
			out["reason_code"] = "query_string_secret"
			return out
		var value := ""
		if pair.size() >= 2:
			value = str(pair[1]).uri_decode().strip_edges()
		match key:
			"run_id":
				out["run_id"] = value
			"tick":
				if value.is_valid_int():
					out["tick"] = int(value)
			"sequence":
				if value.is_valid_int():
					out["sequence"] = int(value)
			"event_id", "event":
				out["event_id"] = value
			"agent_id", "agent":
				out["agent_id"] = value
			"debugger":
				var lowered := value.to_lower()
				out["open_debugger"] = lowered in ["1", "true", "causal", "yes"]
	if out["tick"] == null and out["sequence"] != null:
		out["reason_code"] = "incomplete_event_cursor"
	return out


static func is_missing(origin: String) -> bool:
	return origin.strip_edges().is_empty()
