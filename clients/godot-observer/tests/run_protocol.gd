extends SceneTree

const SUITES: Array[String] = [
	"res://tests/test_models.gd",
	"res://tests/test_cursor.gd",
	"res://tests/test_urls.gd",
	"res://tests/test_playback.gd",
	"res://tests/test_slots.gd",
	"res://tests/test_session_cursor.gd",
	"res://tests/test_reducer.gd",
	"res://tests/test_event_router.gd",
]


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var failed := 0
	for path in SUITES:
		var script: Script = load(path)
		if script == null:
			print("FAIL %s load" % path)
			failed += 1
			continue
		var suite: RefCounted = script.new()
		var result: Variant = suite.call("run")
		if typeof(result) != TYPE_ARRAY:
			print("FAIL %s suite returned no failures array" % path)
			failed += 1
			continue
		var failures: Array = result
		if failures.is_empty():
			print("PASS %s" % path)
		else:
			failed += failures.size()
			for item in failures:
				print("FAIL %s %s" % [path, item])
	print("godot_protocol_tests failed=%s" % failed)
	quit(1 if failed > 0 else 0)
