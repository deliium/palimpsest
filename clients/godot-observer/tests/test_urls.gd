extends RefCounted

const Urls := preload("res://scripts/protocol/urls.gd")

const ORIGIN := "https://observer.example"
const EVENTS := "/v1/simulations/run-1/observer/events"
const STREAM := "/v1/simulations/run-1/observer/stream"


func run() -> Array:
	var failures: Array = []
	var missing: Dictionary = Urls.build_get(ORIGIN, EVENTS, {
		"after_tick": null,
		"after_sequence": null,
		"world_tick": 9,
	})
	if "after_tick" in missing["url"] or "after_sequence" in missing["url"]:
		failures.append("null cursor kept resume parameters")
	if missing["url"].contains("9"):
		failures.append("world tick was substituted for after_tick")
	var negative: Dictionary = Urls.build_get(ORIGIN, EVENTS, {
		"after_tick": 3,
		"after_sequence": -1,
	})
	if "after_tick" in negative["url"] or "after_sequence" in negative["url"]:
		failures.append("negative sequence kept resume parameters")
	var pair: Dictionary = Urls.build_get(ORIGIN, EVENTS, {
		"after_tick": 2,
		"after_sequence": 4,
	})
	if not pair["url"].contains("after_tick=2") or not pair["url"].contains("after_sequence=4"):
		failures.append("complete resume pair was dropped")
	if pair["method"] != "GET":
		failures.append("url builder is not GET-only")
	var posted: Dictionary = Urls.build(ORIGIN, EVENTS, {}, "POST")
	if posted["ok"] or posted["reason_code"] != "read_only":
		failures.append("non-GET was accepted")
	var secret: Dictionary = Urls.build_get(ORIGIN, EVENTS, {"token": "secret-token"})
	if secret["url"].contains("secret-token") or secret["route"].contains("secret"):
		failures.append("token entered the url")
	var userinfo: Dictionary = Urls.build_get(
		"https://user:secret@observer.example",
		EVENTS,
		{},
	)
	if userinfo["route"] != EVENTS or userinfo["route"].contains("secret"):
		failures.append("route included origin userinfo")
	var open_stream: Dictionary = Urls.build_websocket(ORIGIN, STREAM, null, null, 5)
	if not open_stream["connect"] or not str(open_stream["url"]).begins_with("wss://"):
		failures.append("null cursor websocket")
	if "after_tick" in str(open_stream["url"]):
		failures.append("null cursor websocket included resume parameters")
	var ahead: Dictionary = Urls.build_websocket(ORIGIN, STREAM, 5, 0, 5)
	if ahead["connect"] or ahead["reason_code"] != "cursor_ahead":
		failures.append("after_tick at world.tick should fail before connect")
	var plain: Dictionary = Urls.build_websocket("http://observer.example", STREAM, 1, 0, 5)
	if not str(plain["url"]).begins_with("ws://") or "after_tick=1" not in str(plain["url"]):
		failures.append("http origin should use ws with both resume parameters")
	var full := {
		"count": 2,
		"limit": 2,
		"events": [{"tick": 1, "sequence": 0}, {"tick": 1, "sequence": 1}],
	}
	var nxt: Dictionary = Urls.next_page_cursor(full)
	if nxt["done"] or nxt["after_tick"] != 1 or nxt["after_sequence"] != 1:
		failures.append("full page should resume at the last event")
	var short := {"count": 1, "limit": 2, "events": [{"tick": 2, "sequence": 0}]}
	if not Urls.next_page_cursor(short)["done"]:
		failures.append("short page should stop")
	var walked: Dictionary = Urls.walk_pages([full, short])
	if not walked["done"] or walked["event_count"] != 3 or walked["cursors"].size() != 1:
		failures.append("pager did not stop on the short page")
	var focused: Dictionary = Urls.build_get(ORIGIN, EVENTS, {
		"agent_id": "body-a",
		"event_type": "AGENT_ATTACKED",
		"location_id": "loc-1",
		"after_child_run_id": "child-1",
		"sequence": 9,
		"limit": 5,
	})
	var focused_url := str(focused["url"])
	for key in [
		"agent_id=body-a",
		"event_type=AGENT_ATTACKED",
		"location_id=loc-1",
		"after_child_run_id=child-1",
		"sequence=9",
	]:
		if key not in focused_url:
			failures.append("focus/branch allowlist missing %s" % key)
	return failures
