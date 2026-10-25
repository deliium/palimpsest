class_name CivilizationSource

## Session-owned, bounded civilization sidecar navigation. Objective map pages,
## captured overlays and markers are cursor-pinned, scope-checked and cached.

const Civ := preload("res://scripts/protocol/civilization.gd")
const Evidence := preload("res://scripts/presentation/evidence_class.gd")
const ObserverLog := preload("res://scripts/log.gd")

const MAX_ROWS := 800
const MAX_PAGES := 8
const MAX_LAYER_BYTES := 8 * 1024 * 1024
const MAX_CACHE_BOUNDARIES := 4
const MAX_CACHE_BYTES := 32 * 1024 * 1024
const MAX_INFLIGHT := 2
const PAGE_LIMIT := 100
const MAP_LAYERS := ["regions", "routes", "locations", "projects", "repositories", "records"]
const CAPTURED_LAYERS := ["settlements", "migration", "trade", "culture", "technology", "social_groups", "institutions"]
const MIXED_LAYERS := ["technology", "social_groups", "institutions"]
const OBJECTIVE_SECTIONS := ["regions", "routes", "locations", "projects", "repositories", "records", "migration"]
const ANALYSIS_LAYERS := ["settlements", "trade", "culture"]

var enabled_layers: Dictionary = {}
var states: Dictionary = {}
var layer_modes: Dictionary = {}
var filters: Dictionary = {}
var selected_owner_id := ""
var selected_owner_generation := 0
var catalogue: Dictionary = {}
var markers: Dictionary = {}

var _sink: Callable
var _run_id := ""
var _epoch := 0
var _credential_generation := 0
var _private_generation := 0
var _source_generation := 0
var _frame_generation := 0
var _selector_generation := 0
var _request_serial := 0
var _bundle_serial := 0
var _inflight: Dictionary = {}
var _cancelled_keys: Dictionary = {}
var _queue: Array = []
var _queued_layers: Dictionary = {}
var _active_bundle: Dictionary = {}
var _queued_bundle: Dictionary = {}
var _boundary_order: Array = []
var _boundary_bytes: Dictionary = {}
var _cursor: Dictionary = {}
var _partial_prefix := false
var _last_frame_epoch := -1
var _last_frame_credential := -1

signal layer_changed(layer_id: String, state: Dictionary)
signal bundle_ready(cursor: Dictionary, layer_states: Dictionary)
signal catalogue_changed(state: Dictionary)
signal markers_changed(state: Dictionary)


func set_request_sink(sink: Callable) -> void:
	_sink = sink


func set_context(run_id: String, epoch: int, credential_generation: int) -> void:
	if run_id != _run_id:
		clear("source_changed")
	_run_id = run_id
	_epoch = epoch
	_credential_generation = credential_generation


func set_layer_enabled(layer_id: String, value: bool) -> void:
	if layer_id not in MAP_LAYERS and layer_id not in CAPTURED_LAYERS:
		return
	_selector_generation += 1
	if value:
		enabled_layers[layer_id] = true
		if not _cursor.is_empty():
			_request_layer(layer_id, _cursor, "", false)
	else:
		enabled_layers.erase(layer_id)
		states.erase(layer_id)
		_cancel_layer_requests(layer_id)
		layer_changed.emit(layer_id, {"status": "off", "layer": layer_id})


func set_layer_mode(layer_id: String, mode: String, owner_id: String = "") -> void:
	if layer_id in MIXED_LAYERS and mode in ["subjective", "analytical"]:
		_selector_generation += 1
		layer_modes[layer_id] = {"mode": mode, "owner_id": owner_id}
		_clear_private_layers()
		if enabled_layers.has(layer_id) and not _cursor.is_empty():
			_request_layer(layer_id, _cursor, "", false)


func set_owner(owner_id: String) -> void:
	if owner_id == selected_owner_id:
		return
	_selector_generation += 1
	selected_owner_id = owner_id
	selected_owner_generation += 1
	_clear_private_layers()
	if not _cursor.is_empty():
		for layer_id in enabled_ids():
			if _wire_evidence(layer_id) == "SUBJECTIVE":
				_request_layer(layer_id, _cursor, "", false)


func set_filters(layer_id: String, values: Dictionary) -> void:
	var clean := {}
	for key in ["location_id", "region_id", "entity_id"]:
		var value: Variant = values.get(key)
		if value != null and typeof(value) == TYPE_STRING and not str(value).is_empty():
			clean[key] = str(value)
	if clean.get("location_id", null) != null and clean.get("region_id", null) != null:
		clean.erase("region_id")
	if filters.get(layer_id, {}) == clean:
		return
	_selector_generation += 1
	filters[layer_id] = clean
	states.erase(layer_id)
	_cancel_layer_requests(layer_id)
	if enabled_layers.has(layer_id) and not _cursor.is_empty():
		_request_layer(layer_id, _cursor, "", false)


func enabled_ids() -> Array:
	var result: Array = enabled_layers.keys()
	result.sort()
	return result


func on_frame(frame: Variant, epoch: int = -1, credential_generation: int = -1) -> void:
	if frame == null or frame.cursor == null or frame.world == null:
		return
	_epoch = epoch if epoch >= 0 else _epoch
	_credential_generation = credential_generation if credential_generation >= 0 else _credential_generation
	_partial_prefix = false
	var tick := int(frame.world.tick)
	var after_tick: Variant = frame.cursor.after_tick
	if after_tick != null and tick <= int(after_tick):
		_partial_prefix = true
	_cursor = {
		"run_id": _run_id,
		"tick": int(after_tick) if _partial_prefix else tick,
		"revision": int(frame.world.revision),
		"boundary_tick": null if _partial_prefix else tick,
		"through_sequence": frame.cursor.after_sequence if _partial_prefix else null,
	}
	_frame_generation += 1
	_mark_stale()
	for layer_id in enabled_ids():
		if _partial_prefix and layer_id not in MAP_LAYERS:
			_set_terminal(layer_id, _unavailable(layer_id, "finalized_boundary_required"))
		elif layer_id not in MAP_LAYERS:
			states.erase(layer_id)
	if _partial_prefix:
		for layer_id in enabled_ids():
			if layer_id in MAP_LAYERS:
				_request_layer(layer_id, _cursor, "", false)
	else:
		refresh_enabled()


func note_live_event_ahead() -> void:
	_frame_generation += 1
	cancel_bundle("event_ahead")
	for layer_id in enabled_ids():
		var state: Dictionary = states.get(layer_id, {})
		if not state.is_empty():
			state["status"] = "stale"
			state["reason_code"] = "event_ahead"
			state["rows"] = []
			state["next_cursor"] = null
			state["truncated"] = false
			layer_changed.emit(layer_id, state.duplicate(true))


func refresh_enabled() -> void:
	if _cursor.is_empty():
		return
	for layer_id in enabled_ids():
		_request_layer(layer_id, _cursor, "", false)


func clear(reason: String = "") -> void:
	_source_generation += 1
	_frame_generation += 1
	_private_generation += 1
	_selector_generation += 1
	enabled_layers.clear()
	states.clear()
	layer_modes.clear()
	filters.clear()
	catalogue.clear()
	markers.clear()
	selected_owner_id = ""
	_inflight.clear()
	_cancelled_keys.clear()
	_queue.clear()
	_queued_layers.clear()
	_active_bundle = {}
	_queued_bundle = {}
	_boundary_order.clear()
	_boundary_bytes.clear()
	_cursor.clear()
	_partial_prefix = false
	_last_frame_epoch = -1
	_last_frame_credential = -1


func clear_private(reason_code: String = "debug_revoked") -> void:
	_private_generation += 1
	var removed: Array = []
	for layer_id in states.keys():
		var state: Dictionary = states[layer_id]
		if str(state.get("evidence_class", "")) != Evidence.OBJECTIVE:
			removed.append(layer_id)
	for layer_id in removed:
		states.erase(layer_id)
		layer_changed.emit(layer_id, _unavailable(layer_id, reason_code))
	for layer_id in enabled_ids():
		if _wire_evidence(layer_id) != "OBJECTIVE":
			_cancel_layer_requests(layer_id)
	if not catalogue.is_empty() and str(catalogue.get("evidence_class", "")) != Evidence.OBJECTIVE:
		catalogue = {}
	if not markers.is_empty() and str(markers.get("evidence_class", "")) != Evidence.OBJECTIVE:
		markers = {}


func on_credentials_changed(inspection_present: bool, debug_present: bool, generation: int) -> void:
	_credential_generation = generation
	if not inspection_present:
		clear("credentials")
	elif not debug_present:
		clear_private("restricted")


func on_seek() -> void:
	cancel_bundle("seek")
	_source_generation += 1
	_frame_generation += 1
	_selector_generation += 1
	states.clear()
	catalogue.clear()
	markers.clear()
	_queue.clear()
	_queued_layers.clear()
	_inflight.clear()
	_cancelled_keys.clear()
	_boundary_order.clear()
	_boundary_bytes.clear()
	_cursor.clear()


func prepare_bundle(cursor: Dictionary, layers: Array) -> void:
	var bundle := {
		"id": _bundle_serial + 1,
		"cursor": _normalize_cursor(cursor),
		"layers": _unique_strings(layers),
		"states": {},
		"pending": {},
	}
	_bundle_serial = int(bundle["id"])
	if not _active_bundle.is_empty():
		_queued_bundle = bundle
		return
	_start_bundle(bundle)


func cancel_bundle(reason: String = "") -> void:
	_bundle_serial += 1
	_active_bundle = {}
	_queued_bundle = {}
	_queue.clear()
	_queued_layers.clear()


func load_more(layer_id: String) -> void:
	var state: Dictionary = states.get(layer_id, {})
	if state.get("status", "") not in ["available", "partial", "empty"]:
		return
	var next_cursor: Variant = state.get("next_cursor", null)
	if next_cursor == null:
		return
	if int(state.get("pages", 0)) >= MAX_PAGES:
		state["status"] = "partial"
		state["truncated"] = true
		state["client_cap"] = "pages"
		state["next_cursor"] = null
		layer_changed.emit(layer_id, state.duplicate(true))
		return
	var cursor: Dictionary = state.get("cursor", _cursor)
	_request_layer(layer_id, cursor, "", true, next_cursor, state.get("publication", null))


func request_markers(
	from_tick: int,
	to_tick: int,
	evidence_class: String = "ANALYTICAL",
	owner_id: String = "",
	layer: String = "",
) -> void:
	if _run_id.is_empty():
		return
	markers = {"status": "loading", "markers": [], "requested_window": {"start_tick": from_tick, "end_tick": to_tick}}
	var query := {
		"evidence_class": evidence_class,
		"from_tick": from_tick,
		"to_tick": to_tick,
		"limit": PAGE_LIMIT,
	}
	if not owner_id.is_empty():
		query["owner_id"] = owner_id
	if not layer.is_empty():
		query["layer"] = layer
	var request_key := _request_key("markers", {"tick": from_tick, "end_tick": to_tick}, evidence_class, owner_id, layer, null)
	_request(
		"civilization_markers",
		"/v1/simulations/%s/observer/civilization/markers" % _run_id,
		{
			"source": "civilization",
			"kind": "civilization_markers",
			"layer": "markers",
			"capability": "debug" if evidence_class != "OBJECTIVE" else "inspection",
			"request_key": request_key,
			"evidence_class": evidence_class,
			"owner_id": owner_id,
			"filters": {"layer": layer},
			"cursor": {"tick": from_tick, "end_tick": to_tick},
			"source_generation": _source_generation,
			"frame_generation": _frame_generation,
			"selector_generation": _selector_generation,
			"private_generation": _private_generation,
		},
		query,
	)


func handle_response(meta: Dictionary, body: Variant, reason: String, _status: int) -> void:
	var request_key := str(meta.get("request_key", ""))
	ObserverLog.debug(
		"civilization",
		"response layer=%s reason=%s inflight=%s" % [str(meta.get("layer", "")), reason, _inflight.size()],
	)
	_inflight.erase(request_key)
	if _cancelled_keys.has(request_key):
		_cancelled_keys.erase(request_key)
		_pump()
		return
	var layer_id := str(meta.get("layer", ""))
	if not _response_current(meta):
		_pump()
		return
	if reason != "":
		_apply_error(meta, reason)
		_pump()
		return
	var kind := str(meta.get("kind", ""))
	if kind == "civilization_map":
		_apply_map(meta, Civ.parse_map(body))
	elif kind == "civilization_overlay":
		_apply_overlay(meta, Civ.parse_overlay(body))
	elif kind == "civilization_markers":
		_apply_markers(meta, Civ.parse_markers(body))
	elif kind == "civilization_catalogue":
		_apply_catalogue(meta, Civ.parse_catalogue(body))
	else:
		_apply_error(meta, "invalid_civilization_contract")
	_pump()


func _start_bundle(bundle: Dictionary) -> void:
	_active_bundle = bundle
	_active_bundle["pending"] = {}
	for layer_id in bundle["layers"]:
		if not enabled_layers.has(layer_id):
			continue
		_active_bundle["pending"][layer_id] = true
		var existing: Dictionary = states.get(layer_id, {})
		if _state_matches_cursor(existing, bundle["cursor"]):
			_bundle_terminal(layer_id, existing)
		else:
			_set_loading(layer_id, bundle["cursor"])
			_request_layer(layer_id, bundle["cursor"], str(bundle["id"]), false)
	_check_bundle()


func _bundle_terminal(layer_id: String, state: Dictionary) -> void:
	if _active_bundle.is_empty() or not _active_bundle["pending"].has(layer_id):
		return
	if not _state_matches_cursor(state, _active_bundle["cursor"]) and str(state.get("status", "")) not in ["unavailable", "restricted", "error"]:
		return
	_active_bundle["pending"].erase(layer_id)
	_active_bundle["states"][layer_id] = state.duplicate(true)
	_check_bundle()


func _check_bundle() -> void:
	if _active_bundle.is_empty() or not _active_bundle["pending"].is_empty():
		return
	var cursor: Dictionary = _active_bundle["cursor"].duplicate(true)
	var states_out: Dictionary = _active_bundle["states"].duplicate(true)
	_active_bundle = {}
	bundle_ready.emit(cursor, states_out)
	if not _queued_bundle.is_empty():
		var next_bundle: Dictionary = _queued_bundle
		_queued_bundle = {}
		_start_bundle(next_bundle)


func _request_layer(
	layer_id: String,
	cursor: Dictionary,
	bundle_id: String,
	append: bool,
	after: Variant = null,
	publication: Variant = null,
) -> void:
	var normalized: Dictionary = _normalize_cursor(cursor)
	if normalized.get("boundary_tick", null) == null and layer_id not in MAP_LAYERS:
		_set_terminal(layer_id, _unavailable(layer_id, "finalized_boundary_required"))
		_bundle_terminal(layer_id, states.get(layer_id, {}))
		return
	var wire := _wire_evidence(layer_id)
	var owner := _owner_for(layer_id)
	if wire == "SUBJECTIVE" and owner.is_empty():
		_set_terminal(layer_id, _unavailable(layer_id, "restricted"))
		_bundle_terminal(layer_id, states.get(layer_id, {}))
		return
	var limit := PAGE_LIMIT
	var query := {"limit": limit}
	var path := ""
	var kind := ""
	if layer_id in MAP_LAYERS:
		kind = "civilization_map"
		path = "/v1/simulations/%s/observer/civilization/map" % _run_id
		query["section"] = layer_id
		query["tick"] = int(normalized["tick"])
		if normalized.get("through_sequence", null) != null:
			query["through_sequence"] = normalized["through_sequence"]
		for key in ["location_id", "region_id", "entity_id"]:
			if filters.get(layer_id, {}).has(key):
				query[key] = filters[layer_id][key]
	else:
		kind = "civilization_overlay"
		path = "/v1/simulations/%s/observer/civilization/overlays" % _run_id
		query["tick"] = int(normalized["boundary_tick"])
		query["layer"] = layer_id
		query["evidence_class"] = wire
		if wire == "SUBJECTIVE":
			query["owner_id"] = owner
		for key in ["location_id", "region_id", "entity_id"]:
			if filters.get(layer_id, {}).has(key):
				query[key] = filters[layer_id][key]
		if publication != null:
			query["publication_id"] = publication.publication_id
	if append and after != null:
		query["cursor"] = after
	var publication_key: String = "" if publication == null else str(publication.publication_id)
	var request_key := _request_key(layer_id, normalized, wire, owner, layer_id, publication_key)
	request_key = "%s|%s|%s" % [request_key, "append" if append else "first", str(after)]
	if _has_pending(request_key):
		return
	_request(
		kind,
		path,
		{
			"source": "civilization",
			"kind": kind,
			"layer": layer_id,
			"capability": "debug" if wire != "OBJECTIVE" else "inspection",
			"request_key": request_key,
			"evidence_class": wire,
			"owner_id": owner,
			"filters": filters.get(layer_id, {}).duplicate(true),
			"cursor": normalized.duplicate(true),
			"source_generation": _source_generation,
			"frame_generation": _frame_generation,
			"private_generation": _private_generation,
			"selector_generation": _selector_generation,
			"bundle_id": bundle_id,
			"append": append,
			"publication_id": publication_key,
			"page": int(states.get(layer_id, {}).get("pages", 0)) + 1 if append else 1,
		},
		query,
	)


func restart_layer(layer_id: String) -> void:
	states.erase(layer_id)
	_cancel_layer_requests(layer_id)
	if enabled_layers.has(layer_id) and not _cursor.is_empty():
		_request_layer(layer_id, _cursor, "", false)


func request_catalogue(evidence_class: String = "ANALYTICAL", owner_id: String = "", layer: String = "") -> void:
	if _run_id.is_empty():
		return
	catalogue = {"status": "loading"}
	var query := {"evidence_class": evidence_class, "limit": PAGE_LIMIT}
	if not owner_id.is_empty():
		query["owner_id"] = owner_id
	if not layer.is_empty():
		query["layer"] = layer
	var request_key := _request_key("catalogue", {"evidence_class": evidence_class, "owner_id": owner_id, "layer": layer}, evidence_class, owner_id, layer, null)
	_request(
		"civilization_catalogue",
		"/v1/simulations/%s/observer/civilization/catalogue" % _run_id,
		{
			"source": "civilization",
			"kind": "civilization_catalogue",
			"layer": "catalogue",
			"capability": "debug" if evidence_class != "OBJECTIVE" else "inspection",
			"request_key": request_key,
			"evidence_class": evidence_class,
			"owner_id": owner_id,
			"filters": {"layer": layer},
			"source_generation": _source_generation,
			"frame_generation": _frame_generation,
			"selector_generation": _selector_generation,
			"private_generation": _private_generation,
		},
		query,
	)


func _request(kind: String, path: String, meta: Dictionary, query: Dictionary) -> void:
	if _sink.is_null() or _run_id.is_empty():
		return
	meta["epoch"] = _epoch
	meta["credential_generation"] = _credential_generation
	ObserverLog.debug(
		"civilization",
		"request kind=%s layer=%s inflight=%s queued=%s" % [kind, str(meta.get("layer", "")), _inflight.size(), _queued_layers.size()],
	)
	if _inflight.size() >= MAX_INFLIGHT:
		_queued_layers[str(meta.get("layer", ""))] = {
			"kind": kind, "path": path, "meta": meta.duplicate(true), "query": query.duplicate(true)
		}
		return
	_inflight[str(meta["request_key"])] = str(meta.get("layer", ""))
	_sink.call(kind, path, meta, query)


func _pump() -> void:
	while _inflight.size() < MAX_INFLIGHT and not _queued_layers.is_empty():
		var layer_id: String = str(_queued_layers.keys()[0])
		var item: Dictionary = _queued_layers[layer_id]
		_queued_layers.erase(layer_id)
		if _inflight.has(str(item["meta"].get("request_key", ""))):
			continue
		_inflight[str(item["meta"]["request_key"])] = str(item["meta"].get("layer", ""))
		_sink.call(str(item["kind"]), str(item["path"]), item["meta"], item["query"])


func _has_pending(request_key: String) -> bool:
	if _inflight.has(request_key):
		return true
	for item in _queued_layers.values():
		if str(item["meta"].get("request_key", "")) == request_key:
			return true
	return false


func _response_current(meta: Dictionary) -> bool:
	if int(meta.get("source_generation", -1)) != _source_generation:
		return false
	if int(meta.get("frame_generation", -1)) != _frame_generation:
		return false
	if int(meta.get("epoch", _epoch)) != _epoch:
		return false
	if int(meta.get("credential_generation", _credential_generation)) != _credential_generation:
		return false
	if str(meta.get("evidence_class", "")) != "OBJECTIVE" and int(meta.get("private_generation", -1)) != _private_generation:
		return false
	if int(meta.get("selector_generation", -1)) != _selector_generation:
		return false
	var bundle_id := str(meta.get("bundle_id", ""))
	if not bundle_id.is_empty() and bundle_id != str(_active_bundle.get("id", "")) and bundle_id != str(_queued_bundle.get("id", "")):
		return false
	return true


func _apply_map(meta: Dictionary, parsed: Dictionary) -> void:
	var layer_id := str(meta.get("layer", ""))
	if not bool(parsed.get("ok", false)):
		ObserverLog.warn("civilization", "map_parse_failed layer=%s" % layer_id)
		_apply_error(meta, str(parsed.get("reason_code", "civilization_invalid")))
		return
	var model = parsed["value"]
	if model.run_id != _run_id or model.section != layer_id or str(meta.get("evidence_class", "")) != "OBJECTIVE":
		_apply_error(meta, "civilization_scope_mismatch")
		return
	var requested: Dictionary = meta.get("cursor", {})
	if int(requested.get("revision", -1)) != model.resolved_cursor.revision:
		_apply_error(meta, "civilization_cursor_mismatch")
		return
	if requested.get("boundary_tick", null) != null:
		if model.resolved_cursor.boundary_tick != requested.get("boundary_tick", null):
			_apply_error(meta, "civilization_cursor_mismatch")
			return
	elif model.resolved_cursor.through_sequence != requested.get("through_sequence", null):
		_apply_error(meta, "civilization_cursor_mismatch")
		return
	var append := bool(meta.get("append", false))
	var previous: Dictionary = states.get(layer_id, {})
	var rows: Array = previous.get("rows", []).duplicate() if append else []
	var seen := {}
	for row in rows:
		seen[row.context.row_id] = _row_fingerprint(row)
	for row in model.rows:
		var key := str(row.context.row_id)
		var fingerprint := _row_fingerprint(row)
		if seen.has(key):
			if str(seen[key]) != fingerprint:
				_apply_error(meta, "civilization_source_conflict")
				return
			continue
		seen[key] = fingerprint
		rows.append(row)
	var state := _page_state(layer_id, Evidence.OBJECTIVE, "", model.resolved_cursor, null, model.coverage)
	state["rows"] = rows
	state["next_cursor"] = model.next_cursor
	state["truncated"] = model.truncated
	state["request_key"] = str(meta.get("request_key", ""))
	state["cursor"] = _cursor_from(model.resolved_cursor)
	state["filters"] = meta.get("filters", {}).duplicate(true)
	state["source_revision"] = model.source_revision
	state["section"] = model.section
	state["page_limit"] = PAGE_LIMIT
	state["policy_version"] = "objective-map-v1"
	state["pages"] = int(previous.get("pages", 0)) + 1 if append else 1
	_apply_page_limits(state)
	_set_state(layer_id, state)
	_bundle_terminal(layer_id, state)


func _apply_overlay(meta: Dictionary, parsed: Dictionary) -> void:
	var layer_id := str(meta.get("layer", ""))
	if not bool(parsed.get("ok", false)):
		ObserverLog.warn("civilization", "overlay_parse_failed layer=%s" % layer_id)
		_apply_error(meta, str(parsed.get("reason_code", "civilization_invalid")))
		return
	var model = parsed["value"]
	if model.run_id != _run_id or model.scope.layer != layer_id:
		_apply_error(meta, "civilization_scope_mismatch")
		return
	var requested: Dictionary = meta.get("cursor", {})
	if model.requested_tick != int(requested.get("boundary_tick", -1)):
		_apply_error(meta, "civilization_cursor_mismatch")
		return
	if model.availability == "available" and int(requested.get("revision", -1)) != model.resolved_cursor.revision:
		_apply_error(meta, "civilization_cursor_mismatch")
		return
	if model.scope.evidence_class != _evidence_display(str(meta.get("evidence_class", ""))) or _normalize_owner(model.scope.owner_id) != _normalize_owner(meta.get("owner_id", "")):
		_apply_error(meta, "civilization_owner_mismatch")
		return
	if model.availability == "unavailable":
		var unavailable := _unavailable(layer_id, str(model.reason), model.publication)
		unavailable["evidence_class"] = model.scope.evidence_class
		unavailable["owner_id"] = model.scope.owner_id
		_set_state(layer_id, unavailable)
		_bundle_terminal(layer_id, unavailable)
		return
	var append := bool(meta.get("append", false))
	var previous: Dictionary = states.get(layer_id, {})
	if append and not previous.is_empty():
		if not _same_publication(previous.get("publication", null), model.publication):
			_apply_error(meta, "civilization_publication_changed")
			return
		if not _same_cursor(previous.get("cursor", {}), _cursor_from(model.resolved_cursor)):
			_apply_error(meta, "civilization_cursor_mismatch")
			return
	var rows: Array = previous.get("rows", []).duplicate() if append else []
	var seen := {}
	for row in rows:
		seen[row.context.row_id] = _row_fingerprint(row)
	var conflict := false
	for row in model.rows:
		var key := str(row.context.row_id)
		var fingerprint := _row_fingerprint(row)
		if seen.has(key):
			if str(seen[key]) != fingerprint:
				conflict = true
				break
			continue
		seen[key] = fingerprint
		rows.append(row)
	if conflict:
		_apply_error(meta, "civilization_source_conflict")
		return
	var state := _page_state(
		layer_id,
		model.scope.evidence_class,
		model.scope.owner_id,
		model.resolved_cursor,
		model.publication,
		model.coverage,
	)
	state["rows"] = rows
	state["next_cursor"] = model.next_cursor
	state["truncated"] = model.truncated
	state["request_key"] = str(meta.get("request_key", ""))
	state["cursor"] = _cursor_from(model.resolved_cursor)
	state["filters"] = meta.get("filters", {}).duplicate(true)
	state["source_revision"] = model.source_revision
	state["window"] = _window_dict(model.window)
	state["policy_version"] = (
		str(model.rows[0].history.policy_version) if not model.rows.is_empty() else ""
	)
	state["pages"] = int(previous.get("pages", 0)) + 1 if append else 1
	_apply_page_limits(state)
	_set_state(layer_id, state)
	_bundle_terminal(layer_id, state)


func _apply_markers(meta: Dictionary, parsed: Dictionary) -> void:
	if not bool(parsed.get("ok", false)):
		_apply_error(meta, str(parsed.get("reason_code", "civilization_invalid")))
		return
	var model = parsed["value"]
	if model.run_id != _run_id:
		_apply_error(meta, "civilization_scope_mismatch")
		return
	if model.scope.evidence_class != _evidence_display(str(meta.get("evidence_class", ""))):
		_apply_error(meta, "civilization_scope_mismatch")
		return
	if _normalize_owner(model.scope.owner_id) != _normalize_owner(meta.get("owner_id", "")):
		_apply_error(meta, "civilization_owner_mismatch")
		return
	if _scope_layer_text(model.scope.layer) != str(meta.get("filters", {}).get("layer", "")):
		_apply_error(meta, "civilization_scope_mismatch")
		return
	if model.requested_window.start_tick != int(meta.get("cursor", {}).get("tick", -1)):
		_apply_error(meta, "civilization_scope_mismatch")
		return
	markers = {
		"status": "available" if model.availability == "available" else "unavailable",
		"reason_code": model.reason,
		"evidence_class": _evidence_display(model.scope.evidence_class),
		"owner_id": model.scope.owner_id,
		"layer": model.scope.layer,
		"publication": _publication_dict(model.publication),
		"markers": model.markers.slice(0, 200),
		"missing_intervals": _windows_list(model.missing_intervals),
		"coverage": model.coverage,
		"next_cursor": model.next_cursor,
		"truncated": model.truncated,
		"requested_window": _window_dict(model.requested_window),
		"request_key": str(meta.get("request_key", "")),
	}
	markers_changed.emit(markers.duplicate(true))


func _apply_catalogue(meta: Dictionary, parsed: Dictionary) -> void:
	if not bool(parsed.get("ok", false)):
		catalogue = {"status": "error", "reason_code": str(parsed.get("reason_code", "civilization_invalid"))}
		catalogue_changed.emit(catalogue.duplicate(true))
		return
	var model = parsed["value"]
	if model.run_id != _run_id:
		_apply_error(meta, "civilization_scope_mismatch")
		return
	if model.scope.evidence_class != _evidence_display(str(meta.get("evidence_class", ""))):
		_apply_error(meta, "civilization_scope_mismatch")
		return
	if _normalize_owner(model.scope.owner_id) != _normalize_owner(meta.get("owner_id", "")):
		_apply_error(meta, "civilization_owner_mismatch")
		return
	if _scope_layer_text(model.scope.layer) != str(meta.get("filters", {}).get("layer", "")):
		_apply_error(meta, "civilization_scope_mismatch")
		return
	catalogue = {
		"status": "available" if model.availability == "available" else "unavailable",
		"reason_code": model.reason,
		"evidence_class": _evidence_display(model.scope.evidence_class),
		"owner_id": model.scope.owner_id,
		"layer": model.scope.layer,
		"publication": _publication_dict(model.publication),
		"boundaries": model.boundaries,
		"coverage": model.coverage,
		"next_cursor": model.next_cursor,
		"truncated": model.truncated,
		"request_key": str(meta.get("request_key", "")),
	}
	catalogue_changed.emit(catalogue.duplicate(true))


func _apply_error(meta: Dictionary, reason: String) -> void:
	var layer_id := str(meta.get("layer", ""))
	ObserverLog.warn(
		"civilization",
		"response_error layer=%s reason=%s" % [layer_id, reason],
	)
	var code := reason
	if reason == "forbidden" or reason == "unauthorized":
		code = "restricted"
	elif reason == "not_found":
		code = "unsupported"
	elif reason == "gone" or reason in ["civilization_cursor_expired", "civilization_publication_gone"]:
		code = "cursor_gone"
	if layer_id == "markers":
		markers = {
			"status": "unavailable",
			"reason_code": code,
			"restart_required": code == "cursor_gone",
			"markers": [],
			"missing_intervals": [],
		}
		markers_changed.emit(markers.duplicate(true))
		return
	if layer_id == "catalogue":
		catalogue = {
			"status": "unavailable",
			"reason_code": code,
			"restart_required": code == "cursor_gone",
			"boundaries": [],
		}
		catalogue_changed.emit(catalogue.duplicate(true))
		return
	var state := _unavailable(layer_id, code)
	state["restart_required"] = code == "cursor_gone"
	state["evidence_class"] = _evidence_display(str(meta.get("evidence_class", "")))
	state["owner_id"] = meta.get("owner_id", null)
	state["request_key"] = str(meta.get("request_key", ""))
	_set_state(layer_id, state)
	_bundle_terminal(layer_id, state)


func _page_state(layer_id: String, evidence_class: String, owner_id: Variant, resolved_cursor: Variant, publication: Variant, coverage: Variant) -> Dictionary:
	var state := {
		"status": "page",
		"reason_code": null,
		"restart_required": false,
		"layer": layer_id,
		"evidence_class": evidence_class,
		"owner_id": owner_id,
		"publication": _publication_dict(publication),
		"resolved_cursor": _cursor_dict(resolved_cursor),
		"coverage": coverage,
		"rows": [],
		"next_cursor": null,
		"truncated": false,
		"pages": 1,
		"client_cap": "",
	}
	return state


func _set_loading(layer_id: String, cursor: Dictionary) -> void:
	var state := {
		"status": "loading",
		"layer": layer_id,
		"evidence_class": _evidence_display(_wire_evidence(layer_id)),
		"owner_id": _owner_for(layer_id) if _wire_evidence(layer_id) == "SUBJECTIVE" else null,
		"cursor": cursor.duplicate(true),
		"rows": [],
		"next_cursor": null,
		"truncated": false,
	}
	_set_state(layer_id, state)


func _set_terminal(layer_id: String, state: Dictionary) -> void:
	_set_state(layer_id, state)
	_bundle_terminal(layer_id, state)


func _set_state(layer_id: String, state: Dictionary) -> void:
	state["layer"] = layer_id
	var rows: Array = state.get("rows", [])
	var coverage: Variant = state.get("coverage", null)
	var status := str(state.get("status", ""))
	if status in ["unavailable", "restricted", "error", "stale"]:
		pass
	elif status == "loading":
		pass
	elif rows.is_empty() and coverage != null and coverage.state == "partial":
		state["status"] = "partial"
	elif rows.is_empty() and state.get("next_cursor", null) != null:
		state["status"] = "partial"
	elif str(state.get("client_cap", "")) != "":
		state["status"] = "partial"
	elif rows.is_empty():
		state["status"] = "empty"
	elif coverage != null and coverage.state == "partial":
		state["status"] = "partial"
	else:
		state["status"] = "available"
	_register_boundary(state)
	states[layer_id] = state
	layer_changed.emit(layer_id, state.duplicate(true))


func _apply_page_limits(state: Dictionary) -> void:
	var rows: Array = state.get("rows", [])
	if rows.size() > MAX_ROWS:
		state["rows"] = rows.slice(0, MAX_ROWS)
		state["truncated"] = true
		state["client_cap"] = "rows"
		state["next_cursor"] = null
		return
	var page_count := int(state.get("pages", 1))
	if page_count > MAX_PAGES:
		state["pages"] = MAX_PAGES
		state["truncated"] = true
		state["client_cap"] = "pages"
		state["next_cursor"] = null
		return
	var total := 0
	var kept: Array = []
	for row in state["rows"]:
		var size := _bytes(row)
		if total + size > MAX_LAYER_BYTES:
			state["truncated"] = true
			state["client_cap"] = "bytes"
			state["next_cursor"] = null
			break
		total += size
		kept.append(row)
	state["rows"] = kept
	state["bytes"] = total


func _register_boundary(state: Dictionary) -> void:
	var cursor: Dictionary = state.get("cursor", {})
	var boundary := "%s|%s|%s" % [cursor.get("run_id", ""), cursor.get("boundary_tick", null), cursor.get("revision", 0)]
	if not _boundary_bytes.has(boundary):
		_boundary_order.append(boundary)
		_boundary_bytes[boundary] = 0
	_boundary_bytes[boundary] = int(_boundary_bytes.get(boundary, 0)) + int(state.get("bytes", 0))
	while _boundary_order.size() > MAX_CACHE_BOUNDARIES:
		var evicted: String = _boundary_order.pop_front()
		_boundary_bytes.erase(evicted)
		for layer_id in states.keys():
			var existing: Dictionary = states[layer_id]
			var cursor_dict: Dictionary = existing.get("cursor", {})
			var key := "%s|%s|%s" % [cursor_dict.get("run_id", ""), cursor_dict.get("boundary_tick", null), cursor_dict.get("revision", 0)]
			if key == evicted:
				states.erase(layer_id)
				layer_changed.emit(layer_id, _unavailable(layer_id, "cache_evicted"))
	var total := 0
	for value in _boundary_bytes.values():
		total += int(value)
	if total > MAX_CACHE_BYTES:
		while not _boundary_order.is_empty() and total > MAX_CACHE_BYTES:
			var oldest: String = _boundary_order.pop_front()
			total -= int(_boundary_bytes.get(oldest, 0))
			_boundary_bytes.erase(oldest)


func _state_matches_cursor(state: Dictionary, cursor: Dictionary) -> bool:
	if state.get("status", "") not in ["available", "empty", "partial", "unavailable", "restricted", "error"]:
		return false
	return _same_cursor(state.get("cursor", {}), cursor)


func _same_cursor(left: Dictionary, right: Dictionary) -> bool:
	return (
		int(left.get("tick", -1)) == int(right.get("tick", -2))
		and int(left.get("revision", -1)) == int(right.get("revision", -2))
		and left.get("boundary_tick", null) == right.get("boundary_tick", null)
	)


func _normalize_cursor(cursor: Dictionary) -> Dictionary:
	return {
		"run_id": str(cursor.get("run_id", _run_id)),
		"tick": int(cursor.get("tick", 0)),
		"revision": int(cursor.get("revision", 0)),
		"boundary_tick": cursor.get("boundary_tick", null),
		"through_sequence": cursor.get("through_sequence", null),
	}


func _request_key(layer_id: String, cursor: Dictionary, evidence: String, owner: String, layer: String, publication: Variant) -> String:
	var filter_text := JSON.stringify(filters.get(layer_id, {}))
	return "%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s" % [
		_source_generation,
		_frame_generation,
		_selector_generation,
		_epoch,
		_credential_generation,
		_private_generation,
		_run_id,
		layer_id,
		JSON.stringify(cursor),
		evidence,
		owner,
		"%s|%s" % [publication, filter_text],
	]


func _wire_evidence(layer_id: String) -> String:
	if layer_id in OBJECTIVE_SECTIONS:
		return "OBJECTIVE"
	if layer_id in ANALYSIS_LAYERS:
		return "ANALYTICAL"
	if layer_id in MIXED_LAYERS:
		var mode: Dictionary = layer_modes.get(layer_id, {"mode": "analytical", "owner_id": ""})
		return "SUBJECTIVE" if str(mode.get("mode", "analytical")) == "subjective" else "ANALYTICAL"
	return "ANALYTICAL"


func _owner_for(layer_id: String) -> String:
	if _wire_evidence(layer_id) != "SUBJECTIVE":
		return ""
	if layer_id in MIXED_LAYERS:
		var mode: Dictionary = layer_modes.get(layer_id, {})
		var configured := str(mode.get("owner_id", ""))
		return configured if not configured.is_empty() else selected_owner_id
	return selected_owner_id


func _evidence_display(wire: String) -> String:
	match wire:
		"OBJECTIVE":
			return Evidence.OBJECTIVE
		"SUBJECTIVE":
			return Evidence.SUBJECTIVE
		"ANALYTICAL":
			return Evidence.ANALYTICAL
		_:
			return ""


func _clear_private_layers() -> void:
	_private_generation += 1
	var private: Array = []
	for layer_id in states.keys():
		if str(states[layer_id].get("evidence_class", "")) != Evidence.OBJECTIVE:
			private.append(layer_id)
	for layer_id in private:
		states.erase(layer_id)
		_cancel_layer_requests(layer_id)
	for layer_id in enabled_ids():
		if _wire_evidence(layer_id) != "OBJECTIVE":
			states.erase(layer_id)
			layer_changed.emit(layer_id, _unavailable(layer_id, "stale"))


func _cancel_layer_requests(layer_id: String) -> void:
	_queued_layers.erase(layer_id)
	var keys: Array = _inflight.keys()
	for key in keys:
		if str(_inflight[key]) == layer_id:
			_cancelled_keys[key] = true
			_inflight.erase(key)


func _mark_stale() -> void:
	for layer_id in enabled_ids():
		var state: Dictionary = states.get(layer_id, {})
		if not state.is_empty() and not _state_matches_cursor(state, _cursor):
			state["status"] = "stale"
			state["reason_code"] = "stale"
			state["rows"] = []
			state["next_cursor"] = null
			state["truncated"] = false
			layer_changed.emit(layer_id, state.duplicate(true))


func _unavailable(layer_id: String, reason: Variant, publication: Variant = null) -> Dictionary:
	return {
		"status": "unavailable",
		"reason_code": "" if reason == null else str(reason),
		"restart_required": false,
		"layer": layer_id,
		"evidence_class": _evidence_display(_wire_evidence(layer_id)),
		"owner_id": _owner_for(layer_id) if _wire_evidence(layer_id) == "SUBJECTIVE" else null,
		"publication": _publication_dict(publication),
		"coverage": null,
		"rows": [],
		"next_cursor": null,
		"truncated": false,
	}


func _publication_dict(value: Variant) -> Variant:
	if value == null:
		return null
	return {"publication_id": value.publication_id, "digest": value.digest, "policy_version": value.policy_version}


func _cursor_dict(value: Variant) -> Variant:
	if value == null:
		return null
	return _cursor_from(value)


func _cursor_from(value: Variant) -> Dictionary:
	return {
		"run_id": value.run_id,
		"world_id": value.world_id,
		"tick": value.tick,
		"through_sequence": value.through_sequence,
		"boundary_tick": value.boundary_tick,
		"revision": value.revision,
	}


func _window_dict(value: Variant) -> Variant:
	if value == null:
		return null
	return {"start_tick": value.start_tick, "end_tick": value.end_tick}


func _windows_list(values: Array) -> Array:
	var result: Array = []
	for value in values:
		result.append(_window_dict(value))
	return result


func _copy_rows(values: Array) -> Array:
	var result: Array = []
	for value in values:
		result.append(value)
	return result


func _same_publication(left: Variant, right: Variant) -> bool:
	if left == null or right == null:
		return left == right
	return left.publication_id == right.publication_id and left.digest == right.digest


func _normalize_owner(value: Variant) -> String:
	return "" if value == null else str(value)


func _scope_layer_text(value: Variant) -> String:
	return "" if value == null else str(value)


func _row_fingerprint(row: Variant) -> String:
	return JSON.stringify(row)


func _bytes(value: Variant) -> int:
	return JSON.stringify(value).to_utf8_buffer().size()


func _unique_strings(values: Array) -> Array:
	var result: Array = []
	var seen := {}
	for value in values:
		if typeof(value) == TYPE_STRING and not seen.has(value):
			seen[value] = true
			result.append(value)
	return result
