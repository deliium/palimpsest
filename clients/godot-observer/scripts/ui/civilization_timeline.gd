extends Control

## Read-only civilization marker timeline. Backend catalogue/marker identities
## only; it never infers transitions or invents private labels.

const ObserverLog := preload("res://scripts/log.gd")

signal seek_requested(tick: int)
signal marker_window_requested(from_tick: int, to_tick: int, evidence_class: String, owner_id: String, layer: String)
signal marker_load_more_requested(from_tick: int, to_tick: int, evidence_class: String, owner_id: String, layer: String)
signal catalogue_requested(evidence_class: String, owner_id: String)
signal catalogue_load_more_requested(evidence_class: String, owner_id: String)
signal recorded_mode_changed(enabled: bool)

const MAX_MARKERS := 200
const MAX_WINDOWS := 4
const TRACKS: Array[String] = ["movement", "settlement", "knowledge", "institution"]
const TRACK_LABELS := {
	"movement": "OBJECTIVE movement / population",
	"settlement": "ANALYTICAL settlements",
	"knowledge": "Knowledge acquisition / diffusion",
	"institution": "Institution evidence transitions",
}
const TRACK_TYPES := {
	"journey_started": "movement",
	"journey_arrived": "movement",
	"journey_ended": "movement",
	"settlement_activated": "settlement",
	"settlement_deactivated": "settlement",
	"technology_acquired": "knowledge",
	"institution_transition": "institution",
}

var _run_id := ""
var _owner_id := ""
var _debug_present := false
var _inspection_present := false
var _viewed_tick := 0
var _live_tick := 0
var _accepted_tick := 0
var _target_tick := -1
var _skipped := 0
var _marker_states: Dictionary = {}
var _marker_order: Array = []
var _markers: Array = []
var _catalogue: Dictionary = {}
var _requested: Dictionary = {}
var _catalogue_requested := false
var _population_context := ""
var _recorded_button: CheckButton
var _load_more_button: Button
var _gap_count := 0
var _catalogue_gaps := 0
var _truncated := false
var _pages := 0
var _status_notes: Array = []


func _ready() -> void:
	custom_minimum_size = Vector2(760, 112)
	_build_controls()
	ObserverLog.debug("civilization_timeline", "ready max_markers=%s" % MAX_MARKERS)


func _build_controls() -> void:
	var row := get_node_or_null("Controls") as HBoxContainer
	if row == null:
		row = HBoxContainer.new()
		row.name = "Controls"
		add_child(row)
	_recorded_button = CheckButton.new()
	_recorded_button.name = "RecordedBoundaries"
	_recorded_button.text = "Recorded boundaries only"
	_recorded_button.disabled = true
	_recorded_button.toggled.connect(_on_recorded_toggled)
	row.add_child(_recorded_button)
	_load_more_button = Button.new()
	_load_more_button.name = "LoadMore"
	_load_more_button.text = "Load more markers"
	_load_more_button.disabled = true
	_load_more_button.pressed.connect(_on_load_more)
	row.add_child(_load_more_button)


func set_context(run_id: String, owner_id: String, debug_present: bool, inspection_present: bool) -> void:
	if owner_id != _owner_id:
		_drop_private_windows()
	_owner_id = owner_id
	_debug_present = debug_present
	_inspection_present = inspection_present
	_run_id = run_id
	_requested.clear()
	_catalogue_requested = false
	_update_recorded_control()
	queue_redraw()


func set_span(viewed_tick: int, live_tick: int) -> void:
	var next_viewed := maxi(0, viewed_tick)
	var next_live := maxi(0, live_tick)
	if next_viewed != _viewed_tick or next_live != _live_tick:
		_requested.clear()
	_viewed_tick = next_viewed
	_live_tick = next_live
	queue_redraw()


func set_playback_state(accepted_tick: int, target_tick: int, skipped: int) -> void:
	_accepted_tick = maxi(0, accepted_tick)
	_target_tick = target_tick
	_skipped = maxi(0, skipped)
	queue_redraw()


func set_population_context(model: Variant) -> void:
	_population_context = ""
	if model == null:
		queue_redraw()
		return
	if str(_field(model, "availability", "")) != "available":
		queue_redraw()
		return
	var living := 0
	var agents: Array = _field(model, "agents", [])
	for row in agents:
		if str(_field(row, "life_status", "ALIVE")) != "DEAD":
			living += 1
	_population_context = "population context: %s living" % living
	queue_redraw()


func refresh() -> void:
	if _run_id.is_empty():
		return
	var window := _window()
	if _debug_present and not _catalogue_requested:
		_catalogue_requested = true
		catalogue_requested.emit("ANALYTICAL", "")
	_request_window(window, "OBJECTIVE", "")
	if _debug_present:
		_request_window(window, "ANALYTICAL", "")
		if not _owner_id.is_empty():
			_request_window(window, "SUBJECTIVE", _owner_id)


func _request_window(window: Vector2i, evidence_class: String, owner_id: String) -> void:
	var key := "%s|%s|%s|%s|%s" % [
		evidence_class, owner_id, "", window.x, window.y,
	]
	if _requested.has(key):
		return
	_requested[key] = true
	marker_window_requested.emit(window.x, window.y, evidence_class, owner_id, "")


func _window() -> Vector2i:
	var high := maxi(maxi(_live_tick, _viewed_tick), _accepted_tick)
	for boundary in _catalogue.get("boundaries", []):
		high = maxi(high, int(_field(boundary, "boundary_tick", 0)))
	if _target_tick > high:
		high = _target_tick
	return Vector2i(0, high + 1)


func apply_catalogue(state: Dictionary) -> void:
	_catalogue = state.duplicate(true)
	_catalogue_gaps = _gaps_in(state.get("coverage", null))
	for boundary in _catalogue.get("boundaries", []):
		_catalogue_gaps += _gaps_in(_field(boundary, "coverage", null))
	_update_recorded_control()
	_requested.clear()
	_rebuild_markers()
	ObserverLog.debug(
		"civilization_timeline",
		"catalogue_applied status=%s boundaries=%s pages=%s" % [
			str(_catalogue.get("status", "")),
			_catalogue.get("boundaries", []).size(),
			int(_catalogue.get("pages", 0)),
		],
	)


func apply_markers(state: Dictionary) -> void:
	var key := str(state.get("window_key", ""))
	if key.is_empty():
		key = "%s|%s|%s|%s|%s" % [
			str(state.get("evidence_class", "")),
			str(state.get("owner_id", "")),
			str(state.get("layer", "")),
			int(_field(state.get("requested_window", null), "start_tick", 0)),
			int(_field(state.get("requested_window", null), "end_tick", 0)),
		]
	if not _marker_states.has(key):
		_marker_order.append(key)
	_marker_states[key] = state.duplicate(true)
	while _marker_order.size() > MAX_WINDOWS:
		var evicted: String = _marker_order.pop_front()
		_marker_states.erase(evicted)
	_rebuild_markers()


func clear_all() -> void:
	_run_id = ""
	_owner_id = ""
	_debug_present = false
	_inspection_present = false
	_marker_states.clear()
	_marker_order.clear()
	_markers.clear()
	_catalogue.clear()
	_requested.clear()
	_catalogue_requested = false
	_population_context = ""
	_gap_count = 0
	_catalogue_gaps = 0
	_truncated = false
	_pages = 0
	_status_notes.clear()
	_target_tick = -1
	_skipped = 0
	if _recorded_button != null:
		_recorded_button.button_pressed = false
	_update_recorded_control()
	queue_redraw()
	ObserverLog.debug("civilization_timeline", "cleared")


func clear_private() -> void:
	_drop_private_windows()
	_catalogue.clear()
	_catalogue_requested = false
	_update_recorded_control()
	_rebuild_markers()


func marker_count() -> int:
	return _markers.size()


func catalogue_boundary_count() -> int:
	return _catalogue.get("boundaries", []).size()


func recorded_mode_enabled() -> bool:
	return _recorded_button != null and _recorded_button.button_pressed


func recorded_available() -> bool:
	return _recorded_available()


func gap_count() -> int:
	return _gap_count


func truncated() -> bool:
	return _truncated


func page_count() -> int:
	return _pages


func status_notes() -> Array:
	return _status_notes.duplicate()


func load_more_enabled() -> bool:
	return _load_more_button != null and not _load_more_button.disabled


func tracks_for_test() -> Dictionary:
	var counts := {}
	for track in TRACKS:
		counts[track] = 0
	for marker in _markers:
		var track := str(marker.get("track", ""))
		if counts.has(track):
			counts[track] = int(counts[track]) + 1
	return counts


func collect_marks_for_test() -> Array:
	return _markers.duplicate(true)


func _rebuild_markers() -> void:
	var merged: Array = []
	var seen := {}
	var gaps := 0
	var truncated := false
	var pages := 0
	var notes: Array = []
	for key in _marker_order:
		var state: Dictionary = _marker_states[key]
		pages = maxi(pages, int(state.get("pages", 0)))
		truncated = truncated or bool(state.get("truncated", false))
		gaps += state.get("missing_intervals", []).size()
		var status := str(state.get("status", ""))
		if status != "available":
			var reason := str(state.get("reason_code", status))
			if reason != "" and reason not in notes:
				notes.append(reason)
			continue
		for marker in state.get("markers", []):
			var marker_id := str(_field(marker, "marker_id", ""))
			if seen.has(marker_id):
				continue
			seen[marker_id] = true
			merged.append({
				"marker_id": marker_id,
				"marker_type": str(_field(marker, "marker_type", "")),
				"seek_tick": int(_field(marker, "seek_boundary", 0)),
				"evidence_class": str(_field(marker, "evidence_class", "")),
				"owner_id": (
					"" if _field(marker, "owner_id", null) == null
					else str(_field(marker, "owner_id", null))
				),
				"layer": str(_field(marker, "layer", "")),
				"row_id": str(_field(marker, "row_id", "")),
				"track": str(TRACK_TYPES.get(str(_field(marker, "marker_type", "")), "")),
			})
	merged.sort_custom(func(left: Dictionary, right: Dictionary) -> bool:
		if int(left["seek_tick"]) != int(right["seek_tick"]):
			return int(left["seek_tick"]) < int(right["seek_tick"])
		if str(left["marker_type"]) != str(right["marker_type"]):
			return str(left["marker_type"]) < str(right["marker_type"])
		return str(left["marker_id"]) < str(right["marker_id"])
	)
	_truncated = truncated or merged.size() > MAX_MARKERS
	if merged.size() > MAX_MARKERS:
		merged = merged.slice(0, MAX_MARKERS)
	_markers = merged
	_gap_count = gaps + _catalogue_gaps
	_pages = pages
	_status_notes = notes
	_refresh_load_more()
	queue_redraw()
	ObserverLog.debug(
		"civilization_timeline",
		"markers_applied count=%s pages=%s gaps=%s truncated=%s" % [
			_markers.size(), _pages, _gap_count, _truncated,
		],
	)


func _refresh_load_more() -> void:
	var can_load := false
	for state in _marker_states.values():
		if state.get("next_cursor", null) != null and int(state.get("pages", 0)) < 8:
			can_load = true
			break
	if _load_more_button != null:
		_load_more_button.disabled = not can_load


func _on_load_more() -> void:
	for key in _marker_order:
		var state: Dictionary = _marker_states[key]
		if state.get("next_cursor", null) == null or int(state.get("pages", 0)) >= 8:
			continue
		var window: Variant = state.get("requested_window", null)
		marker_load_more_requested.emit(
			int(_field(window, "start_tick", 0)),
			int(_field(window, "end_tick", 0)),
			str(state.get("evidence_class", "")),
			str(state.get("owner_id", "")),
			str(state.get("layer", "")),
		)
	var catalogue_cursor: Variant = _catalogue.get("next_cursor", null)
	if catalogue_cursor != null and int(_catalogue.get("pages", 0)) < 8:
		catalogue_load_more_requested.emit(
			str(_catalogue.get("evidence_class", "ANALYTICAL")),
			str(_catalogue.get("owner_id", "") if _catalogue.get("owner_id", null) != null else ""),
		)


func _on_recorded_toggled(enabled: bool) -> void:
	if enabled and not _recorded_available():
		_recorded_button.set_pressed_no_signal(false)
		enabled = false
	recorded_mode_changed.emit(enabled)
	ObserverLog.debug("civilization_timeline", "recorded_mode enabled=%s" % enabled)


func _recorded_available() -> bool:
	return (
		_debug_present
		and str(_catalogue.get("status", "")) == "available"
		and not _catalogue.get("boundaries", []).is_empty()
	)


func _update_recorded_control() -> void:
	if _recorded_button == null:
		return
	_recorded_button.disabled = not _recorded_available()
	if _recorded_button.disabled and _recorded_button.button_pressed:
		_recorded_button.set_pressed_no_signal(false)
		recorded_mode_changed.emit(false)


func _drop_private_windows() -> void:
	var keep: Array = []
	for key in _marker_order:
		var state: Dictionary = _marker_states[key]
		if str(state.get("evidence_class", "")) == "OBJECTIVE":
			keep.append(key)
		else:
			_marker_states.erase(key)
	_marker_order = keep
	_rebuild_markers()


func _marker_at(point: Vector2) -> Dictionary:
	var span := _span()
	for marker in _markers:
		var pos := _position_for(marker, span)
		if pos.distance_to(point) <= 10.0:
			return marker
	return {}


func _span() -> Vector2i:
	var low := 0
	var high := maxi(maxi(_viewed_tick, _live_tick), _accepted_tick)
	for marker in _markers:
		high = maxi(high, int(marker["seek_tick"]))
	for boundary in _catalogue.get("boundaries", []):
		high = maxi(high, int(_field(boundary, "boundary_tick", 0)))
	return Vector2i(low, maxi(high, low + 1))


func _x_for(tick: int, span: Vector2i) -> float:
	var width := maxf(size.x - 300.0, 120.0)
	var ratio := float(tick - span.x) / float(span.y - span.x)
	return 270.0 + ratio * width


func _y_for(track: String) -> float:
	var index := TRACKS.find(track)
	return 26.0 + (0 if index < 0 else index) * 20.0


func _position_for(marker: Dictionary, span: Vector2i) -> Vector2:
	return Vector2(_x_for(int(marker["seek_tick"]), span), _y_for(str(marker.get("track", ""))))


func _gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	var mouse := event as InputEventMouseButton
	if not mouse.pressed or mouse.button_index != MOUSE_BUTTON_LEFT:
		return
	var marker := _marker_at(mouse.position)
	if marker.is_empty():
		return
	var tick := int(marker.get("seek_tick", 0))
	ObserverLog.debug(
		"civilization_timeline",
		"marker_seek tick=%s type=%s" % [tick, str(marker.get("marker_type", ""))],
	)
	seek_requested.emit(tick)
	accept_event()


func _draw() -> void:
	var span := _span()
	var font := ThemeDB.fallback_font
	for index in TRACKS.size():
		var track: String = TRACKS[index]
		var y := _y_for(track)
		draw_line(Vector2(250, y), Vector2(size.x - 16, y), Color(0.3, 0.34, 0.32), 1.0)
		draw_string(font, Vector2(4, y + 4), str(TRACK_LABELS[track]), HORIZONTAL_ALIGNMENT_LEFT, 240, 11, Color(0.82, 0.84, 0.8))
	for marker in _markers:
		var pos := _position_for(marker, span)
		var color := Color(0.55, 0.75, 0.65)
		if str(marker.get("evidence_class", "")) == "SUBJECTIVE":
			color = Color(0.78, 0.65, 0.9)
		elif str(marker.get("evidence_class", "")) == "OBJECTIVE":
			color = Color(0.55, 0.72, 0.92)
		draw_rect(Rect2(pos - Vector2(3, 5), Vector2(6, 10)), color)
		if str(marker.get("evidence_class", "")) == "SUBJECTIVE" and str(marker.get("owner_id", "")) != "":
			draw_string(font, pos + Vector2(5, -5), str(marker.get("owner_id", "")), HORIZONTAL_ALIGNMENT_LEFT, 80, 9, Color(0.8, 0.72, 0.95))
	var cursor_x := _x_for(_viewed_tick, span)
	draw_line(Vector2(cursor_x, 14), Vector2(cursor_x, 106), Color(0.95, 0.86, 0.45), 1.0)
	var caption := "tick %s" % _viewed_tick
	if _accepted_tick > 0:
		caption = "B=%s displayed=%s" % [_accepted_tick, _viewed_tick]
	if _target_tick >= 0:
		caption += " target=%s" % _target_tick
	if _skipped > 0:
		caption += " skipped=%s" % _skipped
	if _gap_count > 0:
		caption += " gaps=%s (missing evidence, not collapse)" % _gap_count
	if _truncated:
		caption += " (markers truncated)"
	elif _pages > 0:
		caption += " pages=%s" % _pages
	if not _status_notes.is_empty():
		caption += " | " + ", ".join(_status_notes)
	if not _population_context.is_empty():
		caption += " | %s" % _population_context
	draw_string(font, Vector2(4, 108), caption, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.88, 0.9, 0.86))


func _gaps_in(coverage: Variant) -> int:
	if coverage == null:
		return 0
	var intervals: Array = _field(coverage, "missing_intervals", [])
	return intervals.size()


func _field(source: Variant, key: String, fallback: Variant = null) -> Variant:
	if source == null:
		return fallback
	if typeof(source) == TYPE_DICTIONARY:
		return source.get(key, fallback)
	if source is Object:
		var value: Variant = source.get(key)
		return fallback if value == null else value
	return fallback
