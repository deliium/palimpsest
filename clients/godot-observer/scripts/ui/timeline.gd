extends Control

const ObserverLog := preload("res://scripts/log.gd")

signal seek_requested(tick: int, sequence: int)

var viewed_tick := 0
var live_tick := 0
var show_selected := false

var _deaths: Array = []
var _selected: Array = []
var _selected_id := ""
var _events: Array = []


func _ready() -> void:
	custom_minimum_size = Vector2(640, 36)
	$Toggle.pressed.connect(_on_toggle)


func set_window(events: Array, focus_tick: int, next_live_tick: int, selected_id: String) -> void:
	_events = events
	viewed_tick = focus_tick
	live_tick = next_live_tick
	_selected_id = selected_id
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


func _on_toggle() -> void:
	show_selected = $Toggle.button_pressed
	_collect()
	queue_redraw()


func _collect() -> void:
	_deaths = []
	_selected = []
	for event in _events:
		var type_name := str(event.type) if not (event is Dictionary) else str(event.get("type", ""))
		var tick := int(event.tick) if not (event is Dictionary) else int(event.get("tick", 0))
		var sequence := int(event.sequence) if not (event is Dictionary) else int(event.get("sequence", 0))
		var actor := "" if event is Dictionary else ("" if event.actor_id == null else str(event.actor_id))
		var target := "" if event is Dictionary else ("" if event.target_id == null else str(event.target_id))
		if event is Dictionary:
			actor = str(event.get("actor_id", ""))
			target = str(event.get("target_id", ""))
		if type_name == "AGENT_DIED":
			_deaths.append({"tick": tick, "sequence": sequence})
		if show_selected and _selected_id != "" and (actor == _selected_id or target == _selected_id):
			_selected.append({"tick": tick, "sequence": sequence})
	ObserverLog.debug(
		"timeline",
		"marks_set death_count=%s selected_count=%s viewed_tick=%s live_tick=%s" % [
			_deaths.size(), _selected.size(), viewed_tick, live_tick,
		],
	)


func _span() -> Vector2i:
	var low := mini(viewed_tick, live_tick)
	var high := maxi(viewed_tick, live_tick)
	for mark in _deaths:
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
	for mark in _deaths:
		marks.append({
			"x": _x_for(int(mark["tick"]), span),
			"tick": int(mark["tick"]),
			"sequence": int(mark["sequence"]),
		})
	if show_selected:
		for mark in _selected:
			marks.append({
				"x": _x_for(int(mark["tick"]), span),
				"tick": int(mark["tick"]),
				"sequence": int(mark["sequence"]),
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
		"mark_clicked tick=%s sequence=%s" % [int(mark["tick"]), int(mark["sequence"])],
	)
	seek_requested.emit(int(mark["tick"]), int(mark["sequence"]))
	accept_event()


func _draw() -> void:
	var span := _span()
	var left := _x_for(span.x, span)
	var right := _x_for(span.y, span)
	draw_line(Vector2(left, 18), Vector2(right, 18), Color(0.35, 0.4, 0.38), 2.0)
	draw_circle(Vector2(_x_for(viewed_tick, span), 18), 4.0, Color(0.95, 0.86, 0.45))
	draw_circle(Vector2(_x_for(live_tick, span), 18), 3.0, Color(0.45, 0.75, 0.55))
	for mark in _deaths:
		draw_rect(Rect2(Vector2(_x_for(int(mark["tick"]), span) - 2, 8), Vector2(4, 10)), Color(0.85, 0.35, 0.3))
	if show_selected:
		for mark in _selected:
			draw_rect(Rect2(Vector2(_x_for(int(mark["tick"]), span) - 2, 20), Vector2(4, 8)), Color(0.55, 0.7, 0.9))
	var font := ThemeDB.fallback_font
	draw_string(font, Vector2(4, 22), "tick %s / live %s" % [viewed_tick, live_tick], HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.9, 0.9, 0.86))
