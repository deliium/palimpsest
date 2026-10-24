class_name GenerationalSource

## Session-owned, bounded demographic/marker requests. Presentation-only state:
## never derives generation, cohort, age, or ancestry locally.

const Demographics := preload("res://scripts/protocol/demographics.gd")

const PAGE_SIZE := 100
const MAX_PAGES := 8
const MAX_AGENT_ROWS := 800
const MAX_MARKERS := 200

var demographics_enabled := false
var markers_enabled := false
var section := "agents"
var run_id := ""
var cursor: Dictionary = {}
var availability := "unavailable"
var reason_code := "unavailable"
var stale := false
var pages: Array = []
var agent_rows: Dictionary = {}
var selected_agent_id := ""
var selected_row: Variant = null
var selection_state := "unavailable"
var next_after_agent_id: Variant = null
var next_after_group_key: Variant = null
var groups: Array = []
var markers: Array = []
var markers_truncated := false
var next_after_generation_index: Variant = null
var marker_window: Dictionary = {}

var _sink: Callable
var _generation := 0
var _credential_generation := 0
var _epoch := 0
var _pending := {}
var _inflight := {}

signal changed


func set_request_sink(sink: Callable) -> void:
	_sink = sink


func set_context(next_run_id: String, epoch: int, credential_generation: int) -> void:
	run_id = next_run_id
	_epoch = epoch
	_credential_generation = credential_generation


func set_demographics_enabled(value: bool) -> void:
	demographics_enabled = value
	if not value:
		_clear_demographics("disabled")


func set_markers_enabled(value: bool) -> void:
	markers_enabled = value
	if not value:
		markers = []
		markers_truncated = false
		next_after_generation_index = null
		changed.emit()


func choose_section(value: String) -> void:
	if value not in ["agents", "cohorts", "generations"]:
		return
	section = value
	pages = []
	agent_rows.clear()
	next_after_group_key = null
	if demographics_enabled and not cursor.is_empty():
		_fetch_first_page()


func select_agent(agent_id: String) -> void:
	selected_agent_id = agent_id
	selected_row = null
	if agent_id.is_empty():
		selection_state = "unavailable"
		changed.emit()
		return
	if not demographics_enabled or cursor.is_empty():
		selection_state = "unavailable"
		changed.emit()
		return
	var query := _base_query()
	query["section"] = "agents"
	query["agent_id"] = agent_id
	_request("demographics_selection", query)


func set_marker_window(from_tick: Variant = null, to_tick: Variant = null) -> void:
	marker_window = {}
	if from_tick != null:
		marker_window["from_tick"] = int(from_tick)
	if to_tick != null:
		marker_window["to_tick"] = int(to_tick)
	if markers_enabled and not cursor.is_empty():
		_request_markers()


func canonical_cursor(frame: Variant) -> Dictionary:
	if frame == null or frame.cursor == null or frame.world == null:
		return {"kind": "invalid", "reason_code": "cursor_missing"}
	var world_tick := int(frame.world.tick)
	var after_tick: Variant = frame.cursor.after_tick
	if after_tick == null or world_tick > int(after_tick):
		return {"kind": "full", "tick": world_tick, "sequence": null}
	if world_tick == int(after_tick):
		return {
			"kind": "prefix",
			"tick": int(after_tick),
			"sequence": null if frame.cursor.after_sequence == null else int(frame.cursor.after_sequence),
		}
	return {"kind": "invalid", "reason_code": "cursor_ahead_of_world"}


func on_frame(frame: Variant, epoch: int, credential_generation: int) -> void:
	_epoch = epoch
	_credential_generation = credential_generation
	var descriptor := canonical_cursor(frame)
	if str(descriptor.get("kind", "")) == "invalid":
		cursor = {}
		_clear_demographics(str(descriptor.get("reason_code", "invalid_cursor")))
		markers = []
		markers_truncated = false
		changed.emit()
		return
	cursor = descriptor
	stale = false
	_generation += 1
	_clear_demographics("loading")
	pages = []
	agent_rows.clear()
	selected_row = null
	markers = []
	markers_truncated = false
	next_after_generation_index = null
	if demographics_enabled:
		_fetch_first_page()
	if markers_enabled:
		_request_markers()


func on_live_event() -> void:
	## A streamed event advances beyond the accepted sidecars.
	if demographics_enabled or markers_enabled:
		stale = true
		changed.emit()


func clear() -> void:
	cursor = {}
	pages = []
	agent_rows.clear()
	groups = []
	markers = []
	selected_row = null
	selection_state = "unavailable"
	next_after_agent_id = null
	next_after_group_key = null
	next_after_generation_index = null
	markers_truncated = false
	availability = "unavailable"
	reason_code = "unavailable"
	stale = false
	_pending.clear()
	_inflight.clear()
	changed.emit()


func load_more_agents() -> void:
	if next_after_agent_id == null:
		return
	var query := _base_query()
	query["after_agent_id"] = next_after_agent_id
	_request("demographics_page", query)


func load_more_section() -> void:
	if next_after_group_key == null:
		return
	var query := _base_query()
	query["section"] = section
	query["after_group_key"] = next_after_group_key
	_request("demographics_page", query)


func load_more_markers() -> void:
	if next_after_generation_index == null:
		return
	var query := _marker_query()
	query["after_generation_index"] = next_after_generation_index
	_request("demographics_markers", query)


func handle_response(meta: Dictionary, body: Variant, reason: String, status: int) -> void:
	var serial := int(meta.get("serial", -1))
	var kind := str(meta.get("kind", ""))
	_inflight.erase(kind)
	if int(meta.get("epoch", _epoch)) != _epoch:
		return
	if int(meta.get("credential_generation", _credential_generation)) != _credential_generation:
		return
	if int(meta.get("generation", _generation)) != _generation:
		return
	if serial != int(_pending.get(kind, -1)):
		return
	if reason != "":
		_apply_error(kind, reason, status)
		return
	if kind == "demographics_markers":
		_apply_markers(meta, body)
	else:
		_apply_demographics(meta, body)


func _fetch_first_page() -> void:
	if section == "agents":
		_request("demographics_page", _base_query())
	else:
		var query := _base_query()
		query["section"] = section
		_request("demographics_page", query)


func _base_query() -> Dictionary:
	var query := {"limit": PAGE_SIZE}
	if cursor.has("tick"):
		query["tick"] = int(cursor["tick"])
	if cursor.get("sequence", null) != null:
		query["through_sequence"] = int(cursor["sequence"])
	return query


func _marker_query() -> Dictionary:
	var query := {"limit": PAGE_SIZE}
	if cursor.has("tick"):
		if str(cursor.get("kind", "")) == "prefix":
			query["tick"] = int(cursor["tick"])
		else:
			query["tick"] = int(cursor["tick"])
	for key in marker_window.keys():
		query[key] = marker_window[key]
	return query


func _request(kind: String, query: Dictionary) -> void:
	if _sink.is_null() or run_id.is_empty():
		return
	if _inflight.has(kind):
		return
	var path := "/v1/simulations/%s/observer" % run_id
	if kind == "demographics_markers":
		path += "/generation-markers"
	else:
		path += "/demographics"
	_inflight[kind] = true
	_pending[kind] = int(_pending.get(kind, 0)) + 1
	var meta := {
		"source": "generational",
		"kind": kind,
		"capability": "inspection",
		"epoch": _epoch,
		"credential_generation": _credential_generation,
		"generation": _generation,
		"serial": _pending[kind],
		"requested_tick": int(cursor.get("tick", 0)),
		"requested_sequence": cursor.get("sequence", null),
		"section": section,
		"selected_agent": selected_agent_id,
		"revision": int(_revision),
	}
	_sink.call(kind, path, meta, query)


var _revision := 0


func note_world(world: Variant) -> void:
	if world != null:
		_revision = int(world.revision)


func _apply_demographics(meta: Dictionary, body: Variant) -> void:
	var parsed: Dictionary = Demographics.parse_demographics(body)
	if not bool(parsed.get("ok", false)):
		_clear_demographics(str(parsed.get("reason_code", "demographics_invalid")))
		return
	var model = parsed["value"]
	if model.run_id != run_id:
		_clear_demographics("demographics_mismatch")
		return
	if model.requested_tick != int(meta.get("requested_tick", -1)):
		return
	var meta_sequence: Variant = meta.get("requested_sequence", null)
	if model.requested_through_sequence != meta_sequence:
		return
	if model.revision != int(meta.get("revision", -1)):
		return
	if model.resolved_tick != int(meta.get("requested_tick", -1)):
		return
	var selected := str(meta.get("selected_agent", ""))
	if selected != "":
		if model.selection_state not in ["selected", "not_present_at_cursor"]:
			return
		selected_row = model.agents[0] if not model.agents.is_empty() else null
		selection_state = model.selection_state
		availability = model.availability
		reason_code = "" if model.reason_code == null else str(model.reason_code)
		stale = false
		changed.emit()
		return
	if model.section != str(meta.get("section", "")):
		return
	availability = model.availability
	reason_code = "" if model.reason_code == null else str(model.reason_code)
	if model.availability != "available":
		pages = []
		agent_rows.clear()
		groups = []
		next_after_agent_id = null
		next_after_group_key = null
		stale = false
		changed.emit()
		return
	var append := bool(meta.get("append", false))
	if not append:
		pages = []
		agent_rows.clear()
		groups = []
	for row in model.agents:
		if agent_rows.size() >= MAX_AGENT_ROWS:
			break
		agent_rows[row.agent_id] = row
	if model.agents.size() > 0:
		pages.append(model)
		while pages.size() > MAX_PAGES:
			pages.pop_front()
	if model.section == "cohorts" or model.section == "generations":
		groups = model.cohorts if model.section == "cohorts" else model.generations
	next_after_agent_id = model.next_after_agent_id
	next_after_group_key = model.next_after_group_key
	stale = false
	changed.emit()


func _apply_markers(meta: Dictionary, body: Variant) -> void:
	var parsed: Dictionary = Demographics.parse_markers(body)
	if not bool(parsed.get("ok", false)):
		markers = []
		markers_truncated = true
		changed.emit()
		return
	var model = parsed["value"]
	if model.run_id != run_id:
		return
	if model.requested_tick != int(meta.get("requested_tick", -1)):
		return
	if model.revision != int(meta.get("revision", -1)):
		return
	if model.availability != "available":
		markers = []
		markers_truncated = false
		next_after_generation_index = null
		changed.emit()
		return
	var append := bool(meta.get("append", false))
	if not append:
		markers = []
	markers.append_array(model.markers)
	markers_truncated = markers.size() > MAX_MARKERS
	if markers_truncated:
		markers = markers.slice(0, MAX_MARKERS)
	next_after_generation_index = model.next_after_generation_index
	changed.emit()


func _request_markers() -> void:
	_request("demographics_markers", _marker_query())


func _clear_demographics(code: String) -> void:
	availability = "unavailable"
	reason_code = code
	pages = []
	agent_rows.clear()
	groups = []
	next_after_agent_id = null
	next_after_group_key = null
	selection_state = "unavailable"
	changed.emit()


func _apply_error(kind: String, reason: String, status: int) -> void:
	var code := reason
	if status == 401:
		code = "unauthorized"
	elif status == 403:
		code = "forbidden"
	elif status == 404:
		code = "unsupported"
	elif status == 410:
		code = "cursor_gone"
	elif status == 503:
		code = "panel_unavailable"
	if kind == "demographics_markers":
		markers = []
		markers_truncated = true
	else:
		_clear_demographics(code)
	changed.emit()
