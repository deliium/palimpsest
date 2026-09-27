extends RefCounted

const Urls := preload("res://scripts/protocol/urls.gd")

const ORIGIN := "https://observer.example"
const STREAM := "/v1/simulations/run-1/observer/stream"


func run() -> Array:
	var failures: Array = []
	var opened: Dictionary = Urls.build_websocket(ORIGIN, STREAM, null, null, 4)
	if not opened["connect"]:
		failures.append("null cursor should connect")
	if "after_tick" in str(opened["url"]) or "after_sequence" in str(opened["url"]):
		failures.append("null cursor included resume parameters")
	var negative: Dictionary = Urls.build_websocket(ORIGIN, STREAM, 2, -1, 4)
	if not negative["connect"] or "after_tick" in str(negative["url"]):
		failures.append("negative sequence should omit both resume parameters")
	var ahead: Dictionary = Urls.build_websocket(ORIGIN, STREAM, 4, 0, 4)
	if ahead["connect"] or ahead["reason_code"] != "cursor_ahead":
		failures.append("after_tick at world.tick must be rejected before connect")
	if str(ahead["url"]) != "":
		failures.append("rejected resume still built a url")
	var behind: Dictionary = Urls.build_websocket(ORIGIN, STREAM, 3, 0, 4)
	if not behind["connect"] or "after_tick=3" not in str(behind["url"]) or "after_sequence=0" not in str(behind["url"]):
		failures.append("cursor behind world.tick should send both resume parameters")
	return failures
