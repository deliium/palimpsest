extends RefCounted

const SourceScript := preload("res://scripts/net/civilization_source.gd")
const Evidence := preload("res://scripts/presentation/evidence_class.gd")
const BASE := "res://fixtures/protocol/civilization/"


class CursorStub:
	extends RefCounted
	var after_tick: Variant = null
	var after_sequence: Variant = null


class WorldStub:
	extends RefCounted
	var tick: int = 4
	var revision: int = 4


class FrameStub:
	extends RefCounted
	var cursor: CursorStub = CursorStub.new()
	var world: WorldStub = WorldStub.new()


func run() -> Array:
	var failures: Array = []
	_expect(failures, _overlay_requests(), "overlay requests")
	_expect(failures, _map_and_prefix(), "map and prefix")
	_expect(failures, _bundle_queue(), "bundle queue")
	_expect(failures, _caps_and_gone(), "caps and gone")
	_expect(failures, _markers_and_catalogue(), "markers and catalogue")
	_expect(failures, _stale_and_logout(), "stale and logout")
	_expect(failures, _delayed_replies(), "delayed replies")
	return failures


func _load(name: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(BASE + name))


func _source(run_id: String) -> Array:
	var source: Variant = SourceScript.new()
	var requests: Array = []
	var signals: Array = []
	source.set_request_sink(func(kind: String, path: String, meta: Dictionary, query: Dictionary) -> void:
		requests.append({"kind": kind, "path": path, "meta": meta.duplicate(true), "query": query.duplicate(true)})
	)
	source.layer_changed.connect(func(layer_id: String, state: Dictionary) -> void:
		signals.append({"signal": "layer", "layer": layer_id, "state": state})
	)
	source.bundle_ready.connect(func(cursor: Dictionary, states: Dictionary) -> void:
		signals.append({"signal": "bundle", "cursor": cursor, "states": states})
	)
	source.set_context(run_id, 3, 7)
	return [source, requests, signals]


func _respond(source: Variant, request: Dictionary, payload: Variant, reason: String = "", status: int = 200) -> void:
	source.handle_response(request["meta"], payload, reason, status)


func _overlay_requests() -> String:
	var pair: Array = _source("run-capture")
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	var signals: Array = pair[2]
	source.set_layer_enabled("settlements", true)
	source.prepare_bundle({"run_id": "run-capture", "tick": 4, "revision": 4, "boundary_tick": 4}, ["settlements"])
	if requests.size() != 1:
		return "overlay request missing"
	var request: Dictionary = requests[0]
	if str(request["kind"]) != "civilization_overlay":
		return "wrong overlay kind"
	if not str(request["path"]).ends_with("/observer/civilization/overlays"):
		return "wrong overlay path"
	if int(request["query"].get("tick", -1)) != 4 or str(request["query"].get("layer", "")) != "settlements":
		return "overlay tick/layer missing"
	if str(request["query"].get("evidence_class", "")) != "ANALYTICAL":
		return "analytical evidence missing"
	if str(request["meta"].get("capability", "")) != "debug":
		return "analytical request must use debug"
	if str(request["query"]).contains("token") or str(request["query"]).contains("secret"):
		return "credential entered overlay query"
	_respond(source, request, _load("overlay_settlements.json"))
	var state: Dictionary = source.states.get("settlements", {})
	if state.get("status", "") != "available" or state["rows"].size() != 2:
		return "overlay state missing"
	if str(state.get("evidence_class", "")) != Evidence.ANALYTICAL:
		return "analytical state mapping missing"
	if not _has_bundle(signals, 4):
		return "bundle_ready missing for exact cursor"
	return ""


func _map_and_prefix() -> String:
	var pair: Array = _source("run-physical")
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	source.set_layer_enabled("locations", true)
	source.prepare_bundle({"run_id": "run-physical", "tick": 4, "revision": 4, "boundary_tick": 4}, ["locations"])
	if requests.size() != 1 or str(requests[0]["kind"]) != "civilization_map":
		return "map request missing"
	if str(requests[0]["meta"].get("capability", "")) != "inspection":
		return "objective map must use inspection"
	if str(requests[0]["query"].get("section", "")) != "locations" or int(requests[0]["query"].get("tick", -1)) != 4:
		return "map section/tick missing"
	_respond(source, requests[0], _load("map_locations.json"))
	if source.states.get("locations", {}).get("status", "") != "available":
		return "map state missing"

	var prefix_pair: Array = _source("run-capture")
	var prefix_source: Variant = prefix_pair[0]
	var prefix_requests: Array = prefix_pair[1]
	prefix_source.set_layer_enabled("settlements", true)
	prefix_source.set_layer_enabled("locations", true)
	var frame := FrameStub.new()
	frame.world.tick = 4
	frame.cursor.after_tick = 4
	frame.cursor.after_sequence = 1
	prefix_source.on_frame(frame, 3, 7)
	var settlement_state: Dictionary = prefix_source.states.get("settlements", {})
	if settlement_state.get("reason_code", "") != "finalized_boundary_required":
		return "prefix settlement not marked finalized-only"
	var map_requested := false
	for request in prefix_requests:
		if str(request["kind"]) == "civilization_overlay":
			return "prefix issued a captured overlay request"
		if str(request["kind"]) == "civilization_map" and str(request["query"].get("section", "")) == "locations":
			map_requested = true
			if int(request["query"].get("through_sequence", -1)) != 1:
				return "prefix map sequence missing"
	if not map_requested:
		return "prefix objective map did not refresh"
	return ""


func _bundle_queue() -> String:
	var pair: Array = _source("run-capture")
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	var signals: Array = pair[2]
	for layer in ["settlements", "culture", "trade", "institutions"]:
		source.set_layer_enabled(layer, true)
	source.set_layer_mode("institutions", "subjective", "agent-a")
	source.prepare_bundle({"run_id": "run-capture", "tick": 4, "revision": 4, "boundary_tick": 4}, ["settlements", "culture", "trade", "institutions"])
	if requests.size() != 2:
		return "two-request cap not enforced"
	source.prepare_bundle({"run_id": "run-capture", "tick": 5, "revision": 5, "boundary_tick": 5}, ["settlements", "culture", "trade", "institutions"])
	if requests.size() != 2:
		return "queued target canceled active bundle"
	var index := 0
	while index < requests.size() and not _has_bundle(signals, 4):
		var request: Dictionary = requests[index]
		_respond(source, request, null, "gone", 410)
		index += 1
	if not _has_bundle(signals, 4):
		return "active bundle did not complete"
	var started_next := false
	for request in requests:
		if int(request["meta"].get("cursor", {}).get("tick", -1)) == 5:
			started_next = true
			break
	if not started_next:
		return "queued forward target did not start"
	return ""


func _caps_and_gone() -> String:
	var pair: Array = _source("run-capture")
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	source.set_layer_enabled("settlements", true)
	var base: Dictionary = _load("overlay_settlements.json")
	var template: Dictionary = base["rows"][0]
	source.prepare_bundle({"run_id": "run-capture", "tick": 4, "revision": 4, "boundary_tick": 4}, ["settlements"])
	var request_index := 0
	for page in range(5):
		var payload: Dictionary = base.duplicate(true)
		var page_rows: Array = []
		for offset in range(200):
			var index := page * 200 + offset
			var row: Dictionary = template.duplicate(true)
			row["context"]["row_id"] = "settlement:cap-%04d" % index
			row["location_id"] = "loc-%04d" % index
			page_rows.append(row)
		payload["rows"] = page_rows
		payload["truncated"] = page < 4
		payload["next_cursor"] = "page-%d" % (page + 1) if page < 4 else null
		_respond(source, requests[request_index], payload)
		request_index += 1
		if page < 4:
			source.load_more("settlements")
			if requests.size() <= request_index:
				return "load-more request missing"
	var state: Dictionary = source.states.get("settlements", {})
	if state.get("status", "") != "partial" or state["rows"].size() != 800:
		return "row cap not marked partial"
	if state.get("client_cap", "") != "rows" or state.get("next_cursor", null) != null:
		return "row cap did not stop continuation"

	var sparse_pair: Array = _source("run-capture")
	var sparse_source: Variant = sparse_pair[0]
	var sparse_requests: Array = sparse_pair[1]
	sparse_source.set_layer_enabled("settlements", true)
	var sparse: Dictionary = _load("overlay_settlements.json")
	sparse["rows"] = []
	sparse["next_cursor"] = "next-page"
	sparse["truncated"] = true
	sparse["coverage"]["state"] = "partial"
	sparse["coverage"]["reason"] = "capture_gap"
	sparse_source.prepare_bundle({"run_id": "run-capture", "tick": 4, "revision": 4, "boundary_tick": 4}, ["settlements"])
	_respond(sparse_source, sparse_requests[0], sparse)
	var sparse_state: Dictionary = sparse_source.states.get("settlements", {})
	if sparse_state.get("status", "") != "partial" or sparse_state.get("next_cursor", null) == null:
		return "empty continuation treated as exhaustion"
	sparse_source.load_more("settlements")
	if sparse_requests.size() != 2 or sparse_requests[1]["query"].get("cursor", null) == null:
		return "load-more cursor missing"
	_respond(sparse_source, sparse_requests[1], null, "gone", 410)
	var gone_state: Dictionary = sparse_source.states.get("settlements", {})
	if gone_state.get("reason_code", "") != "cursor_gone" or not bool(gone_state.get("restart_required", false)):
		return "410 restart state missing"

	var append_pair: Array = _source("run-capture")
	var append_source: Variant = append_pair[0]
	var append_requests: Array = append_pair[1]
	append_source.set_layer_enabled("settlements", true)
	var first: Dictionary = _load("overlay_settlements.json")
	first["next_cursor"] = "next-page"
	first["truncated"] = true
	append_source.prepare_bundle({"run_id": "run-capture", "tick": 4, "revision": 4, "boundary_tick": 4}, ["settlements"])
	_respond(append_source, append_requests[0], first)
	append_source.load_more("settlements")
	var changed: Dictionary = _load("overlay_settlements.json")
	changed["publication"]["digest"] = "f".repeat(64)
	_respond(append_source, append_requests[1], changed)
	var append_state: Dictionary = append_source.states.get("settlements", {})
	if append_state.get("reason_code", "") != "civilization_publication_changed":
		return "publication mismatch append was mixed"
	return ""


func _markers_and_catalogue() -> String:
	var pair: Array = _source("run-capture")
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	source.request_markers(3, 5, "SUBJECTIVE", "agent-a", "")
	if requests.size() != 1 or str(requests[0]["kind"]) != "civilization_markers":
		return "marker request missing"
	if str(requests[0]["meta"].get("capability", "")) != "debug":
		return "marker subjective request must use debug"
	if int(requests[0]["query"].get("from_tick", -1)) != 3 or int(requests[0]["query"].get("to_tick", -1)) != 5:
		return "marker window missing"
	_respond(source, requests[0], _load("markers_positive.json"))
	if source.markers.get("markers", []).size() != 2:
		return "marker response not applied"
	source.request_catalogue("ANALYTICAL")
	if requests.size() != 2 or str(requests[1]["kind"]) != "civilization_catalogue":
		return "catalogue request missing"
	_respond(source, requests[1], _load("catalogue.json"))
	if source.catalogue.get("boundaries", []).is_empty():
		return "catalogue response not applied"
	return ""


func _delayed_replies() -> String:
	var pair: Array = _source("run-capture")
	var source: Variant = pair[0]
	var requests: Array = pair[1]
	source.set_layer_enabled("settlements", true)
	source.prepare_bundle({"run_id": "run-capture", "tick": 4, "revision": 4, "boundary_tick": 4}, ["settlements"])
	var old_request: Dictionary = requests[0]
	source.on_seek()
	source.prepare_bundle({"run_id": "run-capture", "tick": 5, "revision": 5, "boundary_tick": 5}, ["settlements"])
	var current_request: Dictionary = requests[1]
	_respond(source, old_request, _load("overlay_settlements.json"))
	var after_success: Dictionary = source.states.get("settlements", {})
	if after_success.get("status", "") != "loading" or not after_success.get("rows", []).is_empty():
		return "delayed old success painted a newer cursor"
	_respond(source, old_request, null, "gone", 410)
	var after_error: Dictionary = source.states.get("settlements", {})
	if bool(after_error.get("restart_required", false)):
		return "delayed old error superseded a newer request"
	_respond(source, current_request, null, "gone", 410)
	if source.states.get("settlements", {}).get("reason_code", "") != "cursor_gone":
		return "current request error missing"
	return ""


func _stale_and_logout() -> String:
	var pair: Array = _source("run-capture")
	var source: Variant = pair[0]
	source.states["settlements"] = {
		"status": "available",
		"evidence_class": Evidence.ANALYTICAL,
		"rows": [{"row_id": "row"}],
		"cursor": {"tick": 4, "revision": 4, "boundary_tick": 4},
	}
	source.states["locations"] = {
		"status": "available",
		"evidence_class": Evidence.OBJECTIVE,
		"rows": [{"row_id": "row"}],
		"cursor": {"tick": 4, "revision": 4, "boundary_tick": 4},
	}
	source.enabled_layers["locations"] = true
	source.clear_private()
	if source.states.has("settlements"):
		return "private state survived debug revocation"
	if not source.states.has("locations"):
		return "objective state removed by debug revocation"
	source.note_live_event_ahead()
	if source.states["locations"].get("status", "") != "stale":
		return "live event did not mark objective state stale"
	source.clear()
	if not source.enabled_layers.is_empty() or not source.states.is_empty():
		return "clear did not reset enabled/state"
	return ""


func _has_bundle(signals: Array, tick: int) -> bool:
	for entry in signals:
		if entry.get("signal", "") == "bundle" and int(entry["cursor"].get("tick", -1)) == tick:
			return true
	return false


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
