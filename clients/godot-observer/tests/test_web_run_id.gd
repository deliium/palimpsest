extends RefCounted

const Origin := preload("res://scripts/net/origin.gd")
const SessionScript := preload("res://scripts/net/session.gd")
const Log := preload("res://scripts/log.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _parser(), "query parser")
	_expect(failures, _debugger_state(), "debugger state")
	_expect(failures, _session_cases(), "session query")
	return failures


func _parser() -> String:
	if Origin.web_run_id("?run_id=run-9") != "run-9":
		return "present id"
	if Origin.web_run_id("?run_id=") != "":
		return "empty id"
	if Origin.web_run_id("") != "":
		return "no query"
	if Origin.web_run_id("?token=secret-token&run_id=run-9") != "":
		return "secret query must not yield run_id"
	return ""


func _debugger_state() -> String:
	var state: Dictionary = Origin.web_debugger_state(
		"?run_id=run-1&tick=1832&sequence=17&event_id=evt-1&agent=alice&debugger=causal"
	)
	if str(state.get("run_id", "")) != "run-1":
		return "run_id"
	if int(state.get("tick", -1)) != 1832 or int(state.get("sequence", -1)) != 17:
		return "tick/sequence (UI event N = sequence)"
	if str(state.get("event_id", "")) != "evt-1":
		return "event_id"
	if str(state.get("agent_id", "")) != "alice":
		return "agent alias"
	if not bool(state.get("open_debugger", false)):
		return "debugger open flag"
	var secret: Dictionary = Origin.web_debugger_state("?run_id=run-1&token=x")
	if str(secret.get("reason_code", "")) != "query_string_secret":
		return "secret rejection"
	var incomplete: Dictionary = Origin.web_debugger_state("?run_id=run-1&sequence=3")
	if str(incomplete.get("reason_code", "")) != "incomplete_event_cursor":
		return "incomplete cursor"
	return ""


func _session_cases() -> String:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	var previous: Variant = ProjectSettings.get_setting("palimpsest/observer_origin", "")
	ProjectSettings.set_setting("palimpsest/observer_origin", "https://observer.example")
	var session: Node = SessionScript.new()
	tree.root.add_child(session)
	var field: Array[String] = []
	session.run_id_applied.connect(func(value: String) -> void:
		field.append(value)
	)
	var search := "?run_id=run-9&tick=4&sequence=1&debugger=1"
	if not session.apply_web_query(search):
		_restore(previous, session)
		return "present id did not start"
	if session.run_id != "run-9" or field.is_empty() or field[0] != "run-9":
		_restore(previous, session)
		return "run field was not set from the query"
	var pending: Dictionary = session._pending_deeplink
	if not bool(pending.get("open_debugger", false)):
		_restore(previous, session)
		return "deeplink open_debugger missing"
	if int(pending.get("tick", -1)) != 4 or int(pending.get("sequence", -1)) != 1:
		_restore(previous, session)
		return "deeplink cursor missing"
	var logged := "\n".join(Log.recent)
	if "web_run_id_applied run_id=run-9" not in logged:
		_restore(previous, session)
		return "apply log missing"
	if "bootstrap_started run_id=run-9" not in logged:
		_restore(previous, session)
		return "bootstrap missing"
	if "web_deeplink_parsed" not in logged:
		_restore(previous, session)
		return "deeplink parse log missing"
	session.queue_free()
	var secret_session: Node = SessionScript.new()
	tree.root.add_child(secret_session)
	if secret_session.apply_web_query("?run_id=run-9&token=secret-token"):
		_restore(previous, secret_session)
		return "secret query should reject"
	secret_session.queue_free()
	var empty_id: Node = SessionScript.new()
	tree.root.add_child(empty_id)
	if empty_id.apply_web_query("?run_id=") or not empty_id.run_id.is_empty():
		_restore(previous, empty_id)
		return "empty id connected"
	empty_id.queue_free()
	var no_query: Node = SessionScript.new()
	tree.root.add_child(no_query)
	if no_query.apply_web_query("") or not no_query.run_id.is_empty():
		_restore(previous, no_query)
		return "missing query connected"
	_restore(previous, no_query)
	return ""


func _restore(previous: Variant, session: Node) -> void:
	ProjectSettings.set_setting("palimpsest/observer_origin", previous)
	if is_instance_valid(session):
		session.queue_free()


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
