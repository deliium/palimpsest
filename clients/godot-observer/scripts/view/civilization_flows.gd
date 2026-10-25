extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")
const Plan := preload("res://scripts/presentation/civilization_plan.gd")

signal row_inspect_requested(summary: Dictionary)

const FLOW_KINDS := ["migration", "trade", "culture", "technology"]

var _semantic: Dictionary = {}
var _draw_plan: Dictionary = {}
var _lod := "full"


func apply_plan(semantic_plan: Dictionary) -> void:
	_semantic = semantic_plan.duplicate(true)
	_draw_plan = Plan.draw_plan(_semantic, _lod)
	queue_redraw()
	ObserverLog.debug(
		"civilization",
		"flow_plan segments=%s glyphs=%s suppressed=%s" % [
			link_count(),
			glyph_count(),
			str(_draw_plan.get("suppressed", {})),
		],
	)


func clear_plan() -> void:
	_semantic = {}
	_draw_plan = {}
	queue_redraw()


func set_lod(lod: String) -> void:
	if lod == _lod:
		return
	_lod = lod
	_draw_plan = Plan.draw_plan(_semantic, _lod)
	queue_redraw()


func lod() -> String:
	return _lod


func has_plan() -> bool:
	return bool(_semantic.get("ok", false))


func semantic_plan() -> Dictionary:
	return _semantic


func draw_plan() -> Dictionary:
	return _draw_plan


func glyph_count() -> int:
	var count := 0
	for glyph in _draw_plan.get("glyphs", []):
		if str(glyph.get("kind", "")) in FLOW_KINDS:
			count += 1
	return count


func link_count() -> int:
	var count := 0
	for link in _draw_plan.get("links", []):
		if str(link.get("kind", "")) in [
			"journey_intention",
			"journey_outcome",
			"journey_ended",
			"knowledge_diffusion",
		]:
			count += 1
	return count


func display_truncated() -> bool:
	return bool(_draw_plan.get("display_truncated", false))


func suppressed_count() -> int:
	var suppressed: Dictionary = _draw_plan.get("suppressed", {})
	return int(suppressed.get("links", 0)) + int(suppressed.get("glyphs", 0))


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	var mouse := event as InputEventMouseButton
	if not mouse.pressed or mouse.button_index != MOUSE_BUTTON_LEFT:
		return
	var point := get_global_mouse_position()
	var click := _hit(point)
	if click.is_empty():
		return
	row_inspect_requested.emit(click)
	ObserverLog.debug("civilization", "flow_inspected layer=%s" % str(click.get("layer", "")))
	get_viewport().set_input_as_handled()


func _hit(point: Vector2) -> Dictionary:
	var best := {}
	var best_distance := 18.0
	for glyph in _draw_plan.get("glyphs", []):
		if str(glyph.get("kind", "")) not in FLOW_KINDS:
			continue
		var distance := point.distance_to(glyph.get("point", Vector2.ZERO))
		if distance <= best_distance:
			best_distance = distance
			best = glyph.get("click", {}).duplicate(true)
	for label in _draw_plan.get("labels", []):
		if str(label.get("kind", "")) not in FLOW_KINDS:
			continue
		var distance := point.distance_to(label.get("point", Vector2.ZERO))
		if distance <= best_distance:
			best_distance = distance
			best = label.get("click", {}).duplicate(true)
	for link in _draw_plan.get("links", []):
		if str(link.get("kind", "")) == "configured_route" or str(link.get("kind", "")) == "region_envelope":
			continue
		var points: Array = link.get("points", [])
		if points.size() != 2:
			continue
		var midpoint: Vector2 = (points[0] + points[1]) * 0.5
		var distance := point.distance_to(midpoint)
		if distance <= best_distance:
			best_distance = distance
			best = link.get("click", {}).duplicate(true)
	return best


func _draw() -> void:
	if not bool(_draw_plan.get("ok", false)):
		return
	for link in _draw_plan.get("links", []):
		_draw_link(link)
	for glyph in _draw_plan.get("glyphs", []):
		if str(glyph.get("kind", "")) in FLOW_KINDS:
			_draw_glyph(glyph)
	for label in _draw_plan.get("labels", []):
		if str(label.get("kind", "")) in FLOW_KINDS:
			_draw_label(label)


func _draw_link(link: Dictionary) -> void:
	var kind := str(link.get("kind", ""))
	if kind not in ["journey_intention", "journey_outcome", "journey_ended", "knowledge_diffusion"]:
		return
	var color: Color = Themes.evidence_color(str(link.get("evidence_class", "")))
	var points: Array = link.get("points", [])
	if points.size() != 2:
		return
	var from: Vector2 = points[0]
	var to: Vector2 = points[1]
	var style := str(link.get("style", ""))
	if kind == "journey_intention":
		draw_dashed_line(from, to, color, 1.5, 5.0, true, true)
		draw_arc(from, 5.0, 0.0, TAU, 16, color, 1.5, true)
	elif kind == "journey_outcome":
		draw_line(from, to, Color(color.r, color.g, color.b, 0.7), 1.5)
		_arrow(to, from, color)
	elif kind == "journey_ended":
		draw_dashed_line(from, to, Color(color.r, color.g, color.b, 0.55), 1.0, 3.0, true, true)
		draw_line(to + Vector2(-4, -4), to + Vector2(4, 4), Color(0.9, 0.4, 0.3, 0.95), 2.0)
		draw_line(to + Vector2(-4, 4), to + Vector2(4, -4), Color(0.9, 0.4, 0.3, 0.95), 2.0)
	elif kind == "knowledge_diffusion":
		_draw_diffusion_line(from, to, color, style)
	var label := str(link.get("label", ""))
	if label.is_empty():
		return
	var anchor := (from + to) * 0.5
	draw_string(
		ThemeDB.fallback_font,
		anchor + Vector2(4.0, -4.0),
		"%s %s" % [_prefix(str(link.get("evidence_class", ""))), label],
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		ThemeDB.fallback_font_size,
		color,
	)


func _draw_diffusion_line(from: Vector2, to: Vector2, color: Color, style: String) -> void:
	match style:
		"teaching_dashed":
			draw_dashed_line(from, to, color, 2.0, 8.0, true, true)
		"record_dotted":
			draw_dashed_line(from, to, color, 1.5, 3.0, true, true)
		"observation_dashdot":
			draw_dashed_line(from, to, color, 1.5, 6.0, true, true)
			draw_dashed_line((from + to) * 0.5, to, color, 1.5, 2.0, true, true)
		"practice_solid":
			draw_line(from, to, color, 2.0)
		_:
			draw_dashed_line(from, to, color, 1.0, 4.0, true, true)
	_arrow(to, from, color)


func _arrow(to: Vector2, from: Vector2, color: Color) -> void:
	var direction := (to - from).normalized()
	if direction == Vector2.ZERO:
		return
	var side := Vector2(-direction.y, direction.x)
	draw_colored_polygon(
		PackedVector2Array([
			to,
			to - direction * 8.0 + side * 4.0,
			to - direction * 8.0 - side * 4.0,
		]),
		color,
	)


func _draw_glyph(glyph: Dictionary) -> void:
	var point: Vector2 = glyph.get("point", Vector2.ZERO)
	var color: Color = Themes.evidence_color(str(glyph.get("evidence_class", "")))
	match str(glyph.get("kind", "")):
		"migration":
			draw_arc(point, 7.0, 0.0, TAU, 20, color, 2.0, true)
			draw_circle(point, 2.0, color)
		"trade":
			draw_arc(point, 10.0, 0.2, TAU - 0.2, 24, color, 2.0, true)
			draw_circle(point, 2.0, color)
		"culture":
			_draw_culture_badge(point, color)
		"technology":
			_draw_technology_node(point, color, glyph)


func _draw_culture_badge(point: Vector2, color: Color) -> void:
	var rect := Rect2(point - Vector2(12.0, 8.0), Vector2(24.0, 16.0))
	draw_rect(rect, Color(color.r, color.g, color.b, 0.16), true)
	draw_rect(rect, Color(color.r, color.g, color.b, 0.75), false, 1.0)
	for offset in [-8.0, -2.0, 4.0, 10.0]:
		draw_line(
			point + Vector2(offset, -8.0),
			point + Vector2(offset - 6.0, 8.0),
			Color(color.r, color.g, color.b, 0.45),
			1.0,
		)


func _draw_technology_node(point: Vector2, color: Color, glyph: Dictionary) -> void:
	var radius := 8.0
	var points := PackedVector2Array()
	for index in 6:
		var angle := TAU * float(index) / 6.0
		points.append(point + Vector2(cos(angle), sin(angle)) * radius)
	var filled := str(glyph.get("status", "")) != "lost"
	if filled:
		draw_colored_polygon(points, Color(color.r, color.g, color.b, 0.3))
	points.append(points[0])
	draw_polyline(points, color, 1.5)
	if not bool(glyph.get("has_diffusion_edge", false)):
		draw_circle(point, 2.0, color)


func _draw_label(label: Dictionary) -> void:
	var color: Color = Themes.evidence_color(str(label.get("evidence_class", "")))
	draw_string(
		ThemeDB.fallback_font,
		label.get("point", Vector2.ZERO),
		"%s %s" % [_prefix(str(label.get("evidence_class", ""))), str(label.get("text", ""))],
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		ThemeDB.fallback_font_size,
		color,
	)


func _prefix(evidence_class: String) -> String:
	match evidence_class:
		"OBJECTIVE":
			return "O|"
		"SUBJECTIVE":
			return "S<>"
		_:
			return "A~"
