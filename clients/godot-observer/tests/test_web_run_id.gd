extends RefCounted

const Origin := preload("res://scripts/net/origin.gd")
const SessionScript := preload("res://scripts/net/session.gd")
const Log := preload("res://scripts/log.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _parser(), "query parser")
	_expect(failures, _session_cases(), "session query")
	return failures


func _parser() -> String:
	if Origin.web_run_id("?run_id=run-9") != "run-9":
		return "present id"
	if Origin.web_run_id("?run_id=") != "":
		return "empty id"
	if Origin.web_run_id("") != "":
		return "no query"
	if Origin.web_run_id("?token=secret-token&run_id=run-9") != "run-9":
		return "token was read as the run id"
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
	var search := "?run_id=run-9&token=secret-token"
	if not session.apply_web_query(search):
		_restore(previous, session)
		return "present id did not start"
	if session.run_id != "run-9" or field.is_empty() or field[0] != "run-9":
		_restore(previous, session)
		return "run field was not set from the query"
	var logged := "\n".join(Log.recent)
	if "web_run_id_applied run_id=run-9" not in logged:
		_restore(previous, session)
		return "apply log missing"
	if "bootstrap_started run_id=run-9" not in logged:
		_restore(previous, session)
		return "bootstrap missing"
	if "secret-token" in logged or "window.location" in logged:
		_restore(previous, session)
		return "query leaked into the log"
	session.queue_free()
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
