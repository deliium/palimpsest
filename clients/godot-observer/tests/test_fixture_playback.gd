extends RefCounted

const Fixture := preload("res://scripts/net/fixture_player.gd")
const EventLog := preload("res://scripts/ui/event_log.gd")


func run() -> Array:
	var failures: Array = []
	var log = EventLog.new()
	var result: Dictionary = Fixture.playback_result(8.0, log)
	if not result["skip"]:
		failures.append("high speed fixture should skip motion")
	if str(result["location_id"]) != "loc-grove":
		failures.append("moved agent should finish at the destination")
	if not log.contains_type("RESOURCE_FOUND"):
		failures.append("unknown type missing from the log model")
	if not result["types"].has("RESOURCE_FOUND"):
		failures.append("unknown type missing from playback")
	if result["types"][0] != "AGENT_MOVED":
		failures.append("fixture should start with AGENT_MOVED")
	log.free()
	return failures
