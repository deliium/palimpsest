extends RefCounted

const SessionScript := preload("res://scripts/net/session.gd")
const Log := preload("res://scripts/log.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _lineage_query_includes_owner(), "lineage owner_id query")
	_expect(failures, _causal_cursor_uses_shared_helper(), "causal cursor query")
	_expect(failures, _owner_id_missing_skips(), "owner_id missing")
	return failures


func _lineage_query_includes_owner() -> String:
	var session: SessionScript = SessionScript.new()
	session.run_id = "run-debug"
	session.origin = "https://observer.example"
	session.request_debugger_lineage("goal_ancestry", "goal-1", "alice")
	if session.last_request.is_empty():
		return "last_request empty"
	if str(session.last_request.get("kind", "")) != "causal_debugger_lineage":
		return "kind mismatch"
	var path := str(session.last_request.get("path", ""))
	if "/debugger/lineage/goal_ancestry/goal-1" not in path:
		return "lineage path missing"
	var query: Dictionary = session.last_request.get("query", {})
	if str(query.get("owner_id", "")) != "alice":
		return "owner_id must be in query"
	if query.has("token") or query.has("api_token") or query.has("api_key"):
		return "credentials must not appear in query"
	var logged := "\n".join(Log.recent)
	if "lineage_request" not in logged or "owner_id=alice" not in logged:
		return "lineage_request log missing"
	if "get_built" not in logged or "query_keys=owner_id" not in logged:
		return "get_built query_keys log missing"
	return ""


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
	return ""


func _owner_id_missing_skips() -> String:
	var session: SessionScript = SessionScript.new()
	session.run_id = "run-debug"
	session.origin = "https://observer.example"
	var unavailable: Array = []
	session.overlay_unavailable.connect(func(kind: String, reason_code: String) -> void:
		unavailable.append({"kind": kind, "reason_code": reason_code})
	)
	session.request_debugger_lineage("memory_derivation", "mem-1", "")
	if unavailable.is_empty():
		return "missing owner_id should emit unavailable"
	if str(unavailable[0].get("kind", "")) != "causal_debugger_lineage":
		return "lineage unavailable kind"
	if str(unavailable[0].get("reason_code", "")) != "owner_id_missing":
		return "owner_id_missing reason"
	var logged := "\n".join(Log.recent)
	if "owner_id_missing" not in logged:
		return "owner_id_missing log missing"
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
