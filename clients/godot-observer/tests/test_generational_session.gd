extends RefCounted

const SessionScript := preload("res://scripts/net/session.gd")
const SourceScript := preload("res://scripts/net/generational_source.gd")
const BASE := "res://fixtures/protocol/generational/"


class CursorStub:
	extends RefCounted
	var after_tick: Variant = null
	var after_sequence: Variant = null


class WorldStub:
	extends RefCounted
	var tick: int = 16
	var revision: int = 42


class FrameStub:
	extends RefCounted
	var cursor: CursorStub = CursorStub.new()
	var world: WorldStub = WorldStub.new()


func run() -> Array:
	var failures: Array = []
	_expect(failures, _canonical_cursor(), "canonical cursor")
	_expect(failures, _credentials(), "credential generations")
	_expect(failures, _demographic_requests(), "demographic requests")
	_expect(failures, _stale_and_mismatch(), "stale replies")
	_expect(failures, _markers_and_errors(), "markers and errors")
	return failures


func _full_frame(tick: int = 16) -> FrameStub:
	var frame := FrameStub.new()
	frame.world.tick = tick
	frame.cursor.after_tick = null
	frame.cursor.after_sequence = null
	return frame


func _canonical_cursor() -> String:
	var source: Variant = SourceScript.new()
	var full := _full_frame(16)
	full.cursor.after_tick = 15
	full.cursor.after_sequence = 3
	var descriptor: Dictionary = source.canonical_cursor(full)
	if str(descriptor.get("kind", "")) != "full" or int(descriptor.get("tick", -1)) != 16:
		return "resume pair should not make a newer world frame partial"
	var partial := _full_frame(16)
	partial.cursor.after_tick = 16
	partial.cursor.after_sequence = 3
	var prefix: Dictionary = source.canonical_cursor(partial)
	if str(prefix.get("kind", "")) != "prefix" or int(prefix.get("sequence", -1)) != 3:
		return "genuinely partial prefix not preserved"
	var completed := _full_frame(17)
	completed.cursor.after_tick = 16
	completed.cursor.after_sequence = 4
	if str(source.canonical_cursor(completed).get("kind", "")) != "full":
		return "complete last-event prefix should be a full boundary"
	var ahead := _full_frame(16)
	ahead.cursor.after_tick = 17
	ahead.cursor.after_sequence = 0
	if str(source.canonical_cursor(ahead).get("kind", "")) != "invalid":
		return "future after_tick accepted"
	return ""


func _credentials() -> String:
	var session: Node = SessionScript.new()
	var first: bool = session.configure_credentials("inspection-secret", "debug-secret")
	if not first:
		return "valid credentials rejected"
	if not session.has_inspection_credential() or not session.has_debug_credential():
		return "runtime credentials missing"
	var generation: int = session.credential_generation()
	if not session.configure_credentials("inspection-secret", "debug-secret-2"):
		return "debug-only replacement rejected"
	if session.credential_generation() != generation + 1:
		return "debug-only replacement did not bump generation"
	if session.configure_credentials("inspection-secret\n", "debug-secret"):
		return "newline credential accepted"
	if session.credential_generation() != generation + 1:
		return "invalid credential mutated state"
	session.forget_credentials()
	if session.has_inspection_credential() or session.has_debug_credential():
		return "forget did not clear credentials"
	if session.credential_generation() <= generation:
		return "forget did not bump generation"
	session.free()
	return ""


func _source_with_sink() -> Array:
	var source: Variant = SourceScript.new()
	var requests: Array = []
	source.set_request_sink(func(kind: String, path: String, meta: Dictionary, query: Dictionary) -> void:
		requests.append({"kind": kind, "path": path, "meta": meta, "query": query.duplicate()})
	)
	source.set_context("run-generational-23", 0, 0)
	return [source, requests]


func _load(name: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(BASE + name))


func _demographic_requests() -> String:
	var pair: Array = _source_with_sink()
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	var frame := _full_frame(16)
	source.note_world(frame.world)
	source.on_frame(frame, 0, 0)
	if not requests.is_empty():
		return "disabled demographics issued a request"
	source.set_demographics_enabled(true)
	source.on_frame(frame, 0, 0)
	if requests.size() != 1:
		return "enabled demographics did not request one page"
	var request: Dictionary = requests[0]
	if str(request["path"]) != "/v1/simulations/run-generational-23/observer/demographics":
		return "demographics path wrong"
	if int(request["query"].get("tick", -1)) != 16 or request["query"].has("through_sequence"):
		return "full boundary request carried a sequence"
	if str(request["meta"].get("capability", "")) != "inspection":
		return "demographics should use inspection capability"
	source.handle_response(request["meta"], _load("demographics_agents.json"), "", 200)
	if source.availability != "available" or source.agent_rows.size() != 2:
		return "demographic rows not applied"
	if source.stale:
		return "accepted sidecar should not remain stale"
	source.on_live_event()
	if not source.stale:
		return "live event did not mark summaries stale"
	return ""


func _stale_and_mismatch() -> String:
	var pair: Array = _source_with_sink()
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	var frame := _full_frame(16)
	source.note_world(frame.world)
	source.set_demographics_enabled(true)
	source.on_frame(frame, 0, 0)
	var request: Dictionary = requests[0]
	var stale_meta: Dictionary = request["meta"].duplicate(true)
	stale_meta["generation"] = int(stale_meta["generation"]) - 1
	source.handle_response(stale_meta, _load("demographics_agents.json"), "", 200)
	if source.agent_rows.size() != 0:
		return "stale generation applied"
	var wrong_cursor: Dictionary = request["meta"].duplicate(true)
	wrong_cursor["requested_tick"] = 15
	source.handle_response(wrong_cursor, _load("demographics_agents.json"), "", 200)
	if source.agent_rows.size() != 0:
		return "mismatched cursor applied"
	source.handle_response(request["meta"], _load("demographics_agents.json"), "", 200)
	source.select_agent("agent-child")
	if requests.size() != 2:
		return "selected-agent lookup did not request"
	if str(requests[1]["query"].get("agent_id", "")) != "agent-child":
		return "selected-agent filter missing"
	var selection_query: Dictionary = requests[1]["query"]
	if selection_query.has("after_agent_id") or int(selection_query.get("limit", 0)) != 100:
		return "selected-agent request depended on roster pages"
	return ""


func _markers_and_errors() -> String:
	var pair: Array = _source_with_sink()
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	var frame := _full_frame(16)
	source.note_world(frame.world)
	source.set_markers_enabled(true)
	source.on_frame(frame, 0, 0)
	if requests.size() != 1 or str(requests[0]["kind"]) != "demographics_markers":
		return "markers were not requested"
	source.handle_response(requests[0]["meta"], _load("markers.json"), "", 200)
	if source.markers.size() != 2 or source.markers[1].seek_tick != 6:
		return "marker rows not applied"
	source.set_markers_enabled(false)
	source.set_demographics_enabled(true)
	source.on_frame(frame, 0, 0)
	var latest: Dictionary = requests[requests.size() - 1]
	source.handle_response(latest["meta"], null, "not_found", 404)
	if source.reason_code != "unsupported":
		return "old backend 404 should mark unsupported"
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
