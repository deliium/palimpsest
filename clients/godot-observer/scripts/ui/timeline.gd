extends Control

const ObserverLog := preload("res://scripts/log.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")

signal seek_requested(tick: int, sequence: int)
signal category_toggled(category: String, enabled: bool)

const MARK_CAP := 64
const CATEGORY_TYPES := {
	"birth": ["AGENT_CREATED", "AGENT_ENTERED_WORLD", "AGENT_INITIALIZED"],
	"death": ["AGENT_DIED"],
	"attack": ["AGENT_ATTACKED"],
	"weather_environment": [
		"WEATHER_CHANGED",
		"SEASON_CHANGED",
		"TEMPERATURE_BAND_CHANGED",
		"ENVIRONMENTAL_HAZARD_STARTED",
		"ENVIRONMENTAL_HAZARD_ENDED",
		"RESOURCE_NODE_DEPLETED",
		"RESOURCE_NODE_RECOVERED",
	],
	"artifact_creation": ["ARTIFACT_CREATED"],
	"structure_creation": ["STRUCTURE_BUILT"],
	"branch_point": [],  # synthetic
}

var viewed_tick := 0
var live_tick := 0
var show_selected := false

var _selected: Array = []
var _selected_id := ""
var _events: Array = []
var _enriched: Array = []
var _branch_ticks: Array = []
var _marks: Array = []
var _categories := {
	"birth": true,
	"death": true,
	"attack": true,
	"weather_environment": true,
	"artifact_creation": true,
	"structure_creation": true,
	"branch_point": true,
}
var _truncated := false


func _ready() -> void:
	custom_minimum_size = Vector2(640, 36)
	$Toggle.pressed.connect(_on_toggle)
	_load_category_settings()
	_build_category_toggles()


func set_window(events: Array, focus_tick: int, next_live_tick: int, selected_id: String) -> void:
	_events = events
	viewed_tick = focus_tick
	live_tick = next_live_tick
	_selected_id = selected_id
	_collect()
	queue_redraw()


func set_enriched_events(events: Array) -> void:
	_enriched = events
	_collect()
	queue_redraw()


func set_branch_points(ticks: Array) -> void:
	_branch_ticks = []
	for tick in ticks:
		_branch_ticks.append(int(tick))
	_collect()
	queue_redraw()


func set_live_tick(next_live_tick: int) -> void:
	live_tick = next_live_tick
	_collect()
	queue_redraw()


func set_viewed_tick(next_tick: int) -> void:
	viewed_tick = next_tick
	_collect()
	queue_redraw()


func set_selected(entity_id: String) -> void:
	_selected_id = entity_id
	_collect()
	queue_redraw()


func set_category_enabled(category: String, enabled: bool) -> void:
	if not _categories.has(category):
		return
	_categories[category] = enabled
	ProjectSettings.set_setting("palimpsest/marker_%s" % category, enabled)
	_collect()
	queue_redraw()
	category_toggled.emit(category, enabled)
	ObserverLog.debug("timeline", "category_toggled category=%s enabled=%s" % [category, enabled])


func category_enabled(category: String) -> bool:
	return bool(_categories.get(category, false))


func enabled_enrichment_types(budget: int = 3) -> Array:
	## Prefer types for enabled categories that are not birth/branch_point.
	var chosen: Array = []
	for category in ["death", "attack", "weather_environment", "artifact_creation", "structure_creation", "birth"]:
		if not bool(_categories.get(category, false)):
			continue
		for type_name in CATEGORY_TYPES.get(category, []):
			if type_name in chosen:
				continue
			chosen.append(type_name)
			if chosen.size() >= budget:
				return chosen
	return chosen


func clear_marks() -> void:
	_events = []
	_enriched = []
	_branch_ticks = []
	_selected = []
	_marks = []
	_selected_id = ""
	viewed_tick = 0
	live_tick = 0
	_truncated = false
	queue_redraw()
	ObserverLog.debug("timeline", "marks_cleared")


func mark_at(local_position: Vector2) -> Dictionary:
	var marks := _drawn_marks()
	var best: Dictionary = {}
	var best_distance := 12.0
	for mark in marks:
		var distance := absf(float(mark["x"]) - local_position.x)
		if distance <= best_distance:
			best_distance = distance
			best = mark
	return best


func collect_marks_for_test() -> Array:
	_collect()
	return _marks.duplicate(true)


func _on_toggle() -> void:
	show_selected = $Toggle.button_pressed
	_collect()
	queue_redraw()


func _load_category_settings() -> void:
	for category in _categories.keys():
		var key := "palimpsest/marker_%s" % category
		if ProjectSettings.has_setting(key):
			_categories[category] = bool(ProjectSettings.get_setting(key))


func _build_category_toggles() -> void:
	var row = get_node_or_null("Categories")
	if row == null:
		return
	for child in row.get_children():
		child.queue_free()
	for category in ["death", "attack", "weather_environment", "artifact_creation", "structure_creation", "branch_point", "birth"]:
		var button := CheckButton.new()
		button.text = category
		button.button_pressed = bool(_categories.get(category, true))
		button.toggled.connect(func(pressed: bool) -> void: set_category_enabled(category, pressed))
		row.add_child(button)


func _collect() -> void:
	_selected = []
	var collected: Array = []
	var counts := {}
	for category in _categories.keys():
		counts[category] = 0
	for source in [_events, _enriched]:
		for event in source:
			var type_name: String = str(_event_field(event, "type"))
			var tick := int(_event_field(event, "tick"))
			var sequence := int(_event_field(event, "sequence"))
			var actor := str(_event_field(event, "actor_id"))
			var target := str(_event_field(event, "target_id"))
			var category: String = _category_for_type(type_name)
			if category != "" and bool(_categories.get(category, false)):
				collected.append({
					"tick": tick,
					"sequence": sequence,
					"category": category,
					"seek_tick_start": false,
				})
				counts[category] = int(counts.get(category, 0)) + 1
			if show_selected and _selected_id != "" and (actor == _selected_id or target == _selected_id):
				_selected.append({"tick": tick, "sequence": sequence, "category": "selected", "seek_tick_start": false})
	if bool(_categories.get("branch_point", false)):
		for tick in _branch_ticks:
			collected.append({
				"tick": int(tick),
				"sequence": 0,
				"category": "branch_point",
				"seek_tick_start": true,
			})
			counts["branch_point"] = int(counts.get("branch_point", 0)) + 1
	collected.sort_custom(func(a, b) -> bool:
		if int(a["tick"]) != int(b["tick"]):
			return int(a["tick"]) < int(b["tick"])
		return int(a["sequence"]) < int(b["sequence"])
	)
	_truncated = collected.size() > MARK_CAP
	if _truncated:
		collected = collected.slice(0, MARK_CAP)
	_marks = collected
	ObserverLog.debug(
		"timeline",
		"marks_set death=%s attack=%s weather_environment=%s artifact_creation=%s structure_creation=%s branch_point=%s birth=%s selected_count=%s truncated=%s" % [
			counts.get("death", 0),
			counts.get("attack", 0),
			counts.get("weather_environment", 0),
			counts.get("artifact_creation", 0),
			counts.get("structure_creation", 0),
			counts.get("branch_point", 0),
			counts.get("birth", 0),
			_selected.size(),
			_truncated,
		],
	)


func _category_for_type(type_name: String) -> String:
	for category in CATEGORY_TYPES.keys():
		if type_name in CATEGORY_TYPES[category]:
			return str(category)
	return ""


func _event_field(event: Variant, key: String) -> Variant:
	if event is Dictionary:
		return event.get(key, "")
	if key == "actor_id" or key == "target_id":
		var value = event.get(key)
		return "" if value == null else value
	return event.get(key)


func _span() -> Vector2i:
	var low := mini(viewed_tick, live_tick)
	var high := maxi(viewed_tick, live_tick)
	for mark in _marks:
		low = mini(low, int(mark["tick"]))
		high = maxi(high, int(mark["tick"]))
	for mark in _selected:
		low = mini(low, int(mark["tick"]))
		high = maxi(high, int(mark["tick"]))
	return Vector2i(low, maxi(high, low + 1))


func _x_for(tick: int, span: Vector2i) -> float:
	var width := maxf(size.x - 150.0, 40.0)
	var ratio := float(tick - span.x) / float(span.y - span.x)
	return 130.0 + ratio * width


func _drawn_marks() -> Array:
	var span := _span()
	var marks: Array = []
	for mark in _marks:
		marks.append({
			"x": _x_for(int(mark["tick"]), span),
			"tick": int(mark["tick"]),
			"sequence": int(mark["sequence"]),
			"category": str(mark.get("category", "")),
			"seek_tick_start": bool(mark.get("seek_tick_start", false)),
		})
	if show_selected:
		for mark in _selected:
			marks.append({
				"x": _x_for(int(mark["tick"]), span),
				"tick": int(mark["tick"]),
				"sequence": int(mark["sequence"]),
				"category": "selected",
				"seek_tick_start": false,
			})
	return marks


func _gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	var mouse := event as InputEventMouseButton
	if not mouse.pressed or mouse.button_index != MOUSE_BUTTON_LEFT:
		return
	var mark := mark_at(mouse.position)
	if mark.is_empty():
		return
	ObserverLog.debug(
		"timeline",
		"mark_clicked tick=%s sequence=%s category=%s" % [
			int(mark["tick"]), int(mark["sequence"]), str(mark.get("category", "")),
		],
	)
	if bool(mark.get("seek_tick_start", false)):
		seek_requested.emit(int(mark["tick"]), 0)
	else:
		seek_requested.emit(int(mark["tick"]), int(mark["sequence"]))
	accept_event()


func _draw() -> void:
	var span := _span()
	var left := _x_for(span.x, span)
	var right := _x_for(span.y, span)
	draw_line(Vector2(left, 18), Vector2(right, 18), Color(0.35, 0.4, 0.38), 2.0)
	draw_circle(Vector2(_x_for(viewed_tick, span), 18), 4.0, Color(0.95, 0.86, 0.45))
	draw_circle(Vector2(_x_for(live_tick, span), 18), 3.0, Color(0.45, 0.75, 0.55))
	for mark in _marks:
		var color: Color = Themes.marker_color(str(mark.get("category", "")))
		draw_rect(Rect2(Vector2(_x_for(int(mark["tick"]), span) - 2, 8), Vector2(4, 10)), color)
	if show_selected:
		for mark in _selected:
			draw_rect(
				Rect2(Vector2(_x_for(int(mark["tick"]), span) - 2, 20), Vector2(4, 8)),
				Color(0.55, 0.7, 0.9),
			)
	var font := ThemeDB.fallback_font
	var caption := "tick %s / live %s" % [viewed_tick, live_tick]
	if _truncated:
		caption += " (marks truncated)"
	draw_string(font, Vector2(4, 22), caption, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.9, 0.9, 0.86))
