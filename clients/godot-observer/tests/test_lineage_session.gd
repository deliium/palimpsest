extends RefCounted

const SourceScript := preload("res://scripts/net/lineage_source.gd")
const BASE := "res://fixtures/protocol/generational/"


class CursorStub:
	extends RefCounted
	var after_tick: Variant = null
	var after_sequence: Variant = null


class WorldStub:
	extends RefCounted
	var tick: int = 17
	var revision: int = 42


class FrameStub:
	extends RefCounted
	var cursor: CursorStub = CursorStub.new()
	var world: WorldStub = WorldStub.new()


func run() -> Array:
	var failures: Array = []
	_expect(failures, _participants(), "participants")
	_expect(failures, _genealogy_chain(), "genealogy chain")
	_expect(failures, _partial_prefix(), "partial prefix")
	_expect(failures, _gone_and_stale(), "gone and stale")
	return failures


func _load(name: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(BASE + name))


func _source() -> Array:
	var source: Variant = SourceScript.new()
	var requests: Array = []
	source.set_request_sink(func(kind: String, path: String, meta: Dictionary, query: Dictionary) -> void:
		requests.append({"kind": kind, "path": path, "meta": meta, "query": query.duplicate()})
	)
	source.set_context("run-generational-23", 0, 0)
	source.enabled = true
	var frame := FrameStub.new()
	source.on_frame(frame)
	return [source, requests]


func _participants() -> String:
	var pair: Array = _source()
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	source.request_participants("agent-child", "learner", "subjective", "agent-founder")
	if requests.size() != 1:
		return "participant request missing"
	var request: Dictionary = requests[0]
	if str(request["kind"]) != "lineage_participants":
		return "wrong participant kind"
	if not str(request["path"]).ends_with("/lineage/mentorship/participants"):
		return "wrong participant path"
	if str(request["meta"].get("capability", "")) != "debug":
		return "private participant request must use debug capability"
	if int(request["query"].get("boundary_tick", -1)) != 17:
		return "participant boundary missing"
	if str(request["query"].get("owner_id", "")) != "agent-founder":
		return "subjective owner not explicit"
	if str(request["query"].get("agent_id", "")) != "agent-child":
		return "selected learner missing"
	if str(request["query"].get("role", "")) != "learner":
		return "role missing"
	source.handle_response(request["meta"], _load("lineage_participants.json"), "", 200)
	if source.participants.get("status", "") != "available":
		return "participant response not applied"
	if source.participants["items"].size() != 1:
		return "participant card missing"
	if source.participants["items"][0].owner_id != "agent-founder":
		return "participant owner lost"
	var mismatched: Dictionary = request["meta"].duplicate(true)
	mismatched["agent_id"] = "agent-other"
	source.handle_response(mismatched, _load("lineage_participants.json"), "", 200)
	if source.participants["items"].size() != 1:
		return "stale selected-agent response overwrote panel"
	return ""


func _genealogy_chain() -> String:
	var pair: Array = _source()
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	source.request_genealogy("agent-founder", "both")
	if requests.size() != 1 or str(requests[0]["kind"]) != "lineage_families":
		return "family discovery missing"
	if str(requests[0]["meta"].get("expected_root", "")) != "array":
		return "families must expect an array"
	source.handle_response(requests[0]["meta"], _load("lineage_families.json"), "", 200)
	if requests.size() != 2 or str(requests[1]["kind"]) != "lineage_genealogy_nodes":
		return "native node lookup missing"
	if str(requests[1]["query"].get("native_kind", "")) != "agent":
		return "native agent lookup missing"
	if str(requests[1]["query"].get("evidence_class", "")) != "objective":
		return "genealogy must be objective"
	source.handle_response(requests[1]["meta"], _load("lineage_nodes.json"), "", 200)
	if requests.size() != 3 or str(requests[2]["kind"]) != "lineage_traverse":
		return "traversal missing"
	if int(requests[2]["query"].get("max_depth", -1)) != 1:
		return "direct navigation must stay depth 1"
	if str(requests[2]["query"].get("direction", "")) != "both":
		return "direction missing"
	source.handle_response(requests[2]["meta"], _load("lineage_graph.json"), "", 200)
	if source.genealogy.get("status", "") != "available":
		return "graph not applied"
	if source.genealogy["children"].size() != 1:
		return "direct child not projected"
	if not source.genealogy["parents"].is_empty():
		return "founder should have no direct parent"
	if source.genealogy["children"][0].ref.native_id != "agent-child":
		return "wrong direct child"
	for request in requests:
		if str(request["query"]).contains("token"):
			return "credential entered a lineage query"
	return ""


func _partial_prefix() -> String:
	var pair: Array = _source()
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	var prefix := FrameStub.new()
	prefix.world.tick = 17
	prefix.cursor.after_tick = 17
	prefix.cursor.after_sequence = 2
	source.on_frame(prefix)
	source.request_genealogy("agent-founder")
	if not requests.is_empty():
		return "partial prefix issued a private request"
	if source.genealogy.get("status", "") != "finalized_boundary_required":
		return "partial prefix not marked unavailable"
	var completed := FrameStub.new()
	completed.world.tick = 18
	completed.cursor.after_tick = 17
	completed.cursor.after_sequence = 3
	source.on_frame(completed)
	source.request_genealogy("agent-founder")
	if requests.is_empty():
		return "complete prefix should allow lineage"
	return ""


func _gone_and_stale() -> String:
	var pair: Array = _source()
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	source.request_participants("agent-child", "learner", "subjective", "agent-founder")
	var request: Dictionary = requests[0]
	var stale: Dictionary = request["meta"].duplicate(true)
	stale["panel_generation"] = int(stale["panel_generation"]) - 1
	source.handle_response(stale, _load("lineage_participants.json"), "", 200)
	if source.participants.get("status", "") == "available":
		return "stale panel generation applied"
	source.handle_response(request["meta"], null, "gone", 410)
	if source.participants.get("reason_code", "") != "cursor_gone":
		return "410 did not require explicit restart"
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
