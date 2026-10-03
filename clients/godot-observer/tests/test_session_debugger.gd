extends RefCounted

const SessionScript := preload("res://scripts/net/session.gd")
const Log := preload("res://scripts/log.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _causal_cursor_uses_shared_helper(), "causal cursor query")
	return failures


func _causal_cursor_uses_shared_helper() -> String:
	var session: SessionScript = SessionScript.new()
	session.run_id = "run-debug"
	session.origin = "https://observer.example"
	session.request_causal_trace("", 10, 3)
	var query: Dictionary = session.last_request.get("query", {})
	if int(query.get("tick", -1)) != 10 or int(query.get("sequence", -1)) != 3:
		return "cursor query missing tick/sequence"
	if str(session.last_request.get("kind", "")) != "causal_debugger":
		return "causal kind mismatch"
	var logged := "\n".join(Log.recent)
	if "get_built" not in logged or "query_keys=" not in logged:
		return "get_built query_keys log missing"
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
