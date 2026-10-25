extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
const Evidence := preload("res://scripts/presentation/evidence_class.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")
const Plan := preload("res://scripts/presentation/civilization_plan.gd")

signal row_inspect_requested(summary: Dictionary)

var _semantic: Dictionary = {}
var _draw_plan: Dictionary = {}
var _lod := "full"


func apply_plan(semantic_plan: Dictionary) -> void:
	_semantic = semantic_plan.duplicate(true)
	_draw_plan = Plan.draw_plan(_semantic, _lod)
	queue_redraw()
	ObserverLog.debug(
		"civilization",
		"facilities_plan rows=%s glyphs=%s links=%s unplaced=%s" % [
			_semantic.get("rows", []).size(),
			_draw_plan.get("glyphs", []).size(),
			_draw_plan.get("links", []).size(),
			int(_semantic.get("unresolved_anchor_count", 0)),
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
	return _draw_plan.get("glyphs", []).size()


func link_count() -> int:
	return _draw_plan.get("links", []).size()


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
	ObserverLog.debug("civilization", "row_inspected layer=%s" % str(click.get("layer", "")))
	get_viewport().set_input_as_handled()


func _hit(point: Vector2) -> Dictionary:
	var best := {}
	var best_distance := 18.0
	for glyph in _draw_plan.get("glyphs", []):
		if str(glyph.get("kind", "")) in ["migration", "trade", "culture", "technology"]:
			continue
		var distance := point.distance_to(glyph.get("point", Vector2.ZERO))
		if distance <= best_distance:
			best_distance = distance
			best = glyph.get("click", {}).duplicate(true)
	for label in _draw_plan.get("labels", []):
		if str(label.get("kind", "")) in ["migration", "trade", "culture", "technology"]:
			continue
		var distance := point.distance_to(label.get("point", Vector2.ZERO))
		if distance <= best_distance:
			best_distance = distance
			best = label.get("click", {}).duplicate(true)
	for link in _draw_plan.get("links", []):
		if str(link.get("kind", "")) != "configured_route":
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
		_draw_glyph(glyph)
	for label in _draw_plan.get("labels", []):
		if str(label.get("kind", "")) in ["migration", "trade", "culture", "technology"]:
			continue
		_draw_label(label)


func _draw_link(link: Dictionary) -> void:
	var color: Color = Themes.evidence_color(str(link.get("evidence_class", "")))
	if str(link.get("kind", "")) == "region_envelope":
		var bounds: Rect2 = link.get("bounds", Rect2())
		if bounds.size == Vector2.ZERO:
			return
		var envelope := bounds.grow(14.0)
		_dashed_rect(envelope, Color(color.r, color.g, color.b, 0.55), 1.0)
		var text := str(link.get("region_label", ""))
		if text.is_empty():
			text = str(link.get("label", ""))
		if text.is_empty():
			return
		draw_string(
			ThemeDB.fallback_font,
			envelope.position + Vector2(4.0, -4.0),
			"%s %s" % [_prefix(str(link.get("evidence_class", ""))), text],
			HORIZONTAL_ALIGNMENT_LEFT,
			-1,
			ThemeDB.fallback_font_size,
			color,
		)
		return
	var points: Array = link.get("points", [])
	if points.size() != 2:
		return
	var from: Vector2 = points[0]
	var to: Vector2 = points[1]
	draw_dashed_line(from, to, color, 2.0, 7.0, true, true)
	draw_circle(from, 3.0, color)
	draw_circle(to, 3.0, color)
	var text := str(link.get("label", ""))
	if text.is_empty():
		return
	var midpoint := (from + to) * 0.5
	draw_string(
		ThemeDB.fallback_font,
		midpoint + Vector2(4.0, -4.0),
		"%s %s" % [_prefix(str(link.get("evidence_class", ""))), text],
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		ThemeDB.fallback_font_size,
		color,
	)


func _draw_glyph(glyph: Dictionary) -> void:
	var point: Vector2 = glyph.get("point", Vector2.ZERO)
	var color: Color = Themes.evidence_color(str(glyph.get("evidence_class", "")))
	match str(glyph.get("kind", "")):
		"locations":
			var radius := _population_radius(str(glyph.get("size_band", "none")))
			draw_circle(point, radius, Color(color.r, color.g, color.b, 0.22))
			draw_arc(point, radius, 0.0, TAU, 24, color, 2.0, true)
			draw_circle(point, 2.0, color)
		"settlements":
			_draw_settlement(point, color, glyph)
		"projects":
			_draw_project(point, color, glyph)
		"public_act":
			_draw_public_act(point, color, glyph)
		"repositories":
			_draw_repository(point, color, glyph)
		"records":
			_draw_record(point, color, glyph)


func _draw_settlement(point: Vector2, color: Color, glyph: Dictionary) -> void:
	var style := str(glyph.get("style", "solid"))
	var radius := 11.0
	var diamond := PackedVector2Array([
		point + Vector2(0, -radius),
		point + Vector2(radius, 0),
		point + Vector2(0, radius),
		point + Vector2(-radius, 0),
	])
	if style == "solid":
		draw_colored_polygon(diamond, Color(color.r, color.g, color.b, 0.35))
		draw_polyline(PackedVector2Array([diamond[0], diamond[1], diamond[2], diamond[3], diamond[0]]), color, 2.0)
	elif style == "hollow":
		draw_polyline(PackedVector2Array([diamond[0], diamond[1], diamond[2], diamond[3], diamond[0]]), color, 1.5)
	else:
		draw_polyline(PackedVector2Array([diamond[0], diamond[1], diamond[2], diamond[3], diamond[0]]), color, 1.0)
		for offset in [-6.0, 0.0, 6.0]:
			draw_line(
				point + Vector2(-8.0, offset),
				point + Vector2(8.0, offset - 6.0),
				Color(color.r, color.g, color.b, 0.55),
				1.0,
			)


func _draw_project(point: Vector2, color: Color, glyph: Dictionary) -> void:
	var size := Vector2(18.0, 12.0)
	var rect := Rect2(point - size * 0.5, size)
	draw_rect(rect, Color(color.r, color.g, color.b, 0.2), true)
	draw_rect(rect, color, false, 1.5)
	var labor := float(glyph.get("labor_ratio", 0.0))
	var material := float(glyph.get("material_ratio", 0.0))
	draw_rect(Rect2(rect.position + Vector2(1.0, 1.5), Vector2(maxf(0.0, (size.x - 2.0) * labor), 3.0)), color, true)
	draw_rect(Rect2(rect.position + Vector2(1.0, 6.5), Vector2(maxf(0.0, (size.x - 2.0) * material), 3.0)), Color(color.r, color.g, color.b, 0.6), true)
	var linked: Variant = glyph.get("linked_structure_point", null)
	if linked != null:
		draw_arc(linked, 12.0, 0.0, TAU, 20, Color(color.r, color.g, color.b, 0.8), 1.5, true)


func _draw_public_act(point: Vector2, color: Color, glyph: Dictionary) -> void:
	var index := int(glyph.get("act_index", 0))
	var offset := Vector2(-18.0 + float(index) * 12.0, 16.0)
	var at := point + offset
	match str(glyph.get("act", "")):
		"benefit":
			draw_circle(at, 4.0, color)
		"draw":
			draw_colored_polygon(PackedVector2Array([at + Vector2(0, -5), at + Vector2(5, 4), at + Vector2(-5, 4)]), color)
		"maintenance":
			draw_rect(Rect2(at - Vector2(4, 4), Vector2(8, 8)), color, true)
		"opposition":
			draw_line(at + Vector2(-4, -4), at + Vector2(4, 4), color, 2.0)
			draw_line(at + Vector2(-4, 4), at + Vector2(4, -4), color, 2.0)
	draw_string(
		ThemeDB.fallback_font,
		at + Vector2(6.0, 4.0),
		str(glyph.get("count", 0)),
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		ThemeDB.fallback_font_size,
		color,
	)


func _draw_repository(point: Vector2, color: Color, glyph: Dictionary) -> void:
	var status := str(glyph.get("status", ""))
	var rect := Rect2(point - Vector2(9.0, 7.0), Vector2(18.0, 14.0))
	if status == "destroyed":
		draw_rect(rect, Color(0.5, 0.22, 0.2, 0.25), true)
		draw_rect(rect, Color(color.r, color.g, color.b, 0.7), false, 1.0)
		draw_line(rect.position, rect.end, Color(0.9, 0.3, 0.25, 0.9), 2.0)
		draw_line(Vector2(rect.position.x, rect.end.y), Vector2(rect.end.x, rect.position.y), Color(0.9, 0.3, 0.25, 0.9), 2.0)
		return
	draw_rect(rect, Color(color.r, color.g, color.b, 0.18), true)
	if status == "neglected":
		_dashed_rect(rect, color, 1.0)
	elif status == "inaccessible":
		draw_rect(rect, color, false, 1.0)
		draw_line(rect.position + Vector2(3, 7), rect.end - Vector2(3, 7), color, 1.0)
	else:
		draw_rect(rect, color, false, 1.5)
	draw_line(rect.position + Vector2(2.0, 4.0), Vector2(rect.end.x - 2.0, rect.position.y + 4.0), color, 1.0)


func _draw_record(point: Vector2, color: Color, glyph: Dictionary) -> void:
	var integrity := str(glyph.get("integrity", "intact"))
	var rect := Rect2(point - Vector2(5.0, 6.0), Vector2(10.0, 12.0))
	draw_rect(rect, Color(color.r, color.g, color.b, 0.25), true)
	draw_rect(rect, color, false, 1.0)
	if integrity in ["damaged", "partially_lost", "destroyed"]:
		draw_line(rect.position + Vector2(1, 1), rect.end - Vector2(1, 1), Color(0.9, 0.35, 0.28, 0.95), 1.5)


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


func _dashed_rect(rect: Rect2, color: Color, width: float) -> void:
	draw_dashed_line(rect.position, Vector2(rect.end.x, rect.position.y), color, width, 5.0, true, true)
	draw_dashed_line(Vector2(rect.end.x, rect.position.y), rect.end, color, width, 5.0, true, true)
	draw_dashed_line(rect.end, Vector2(rect.position.x, rect.end.y), color, width, 5.0, true, true)
	draw_dashed_line(Vector2(rect.position.x, rect.end.y), rect.position, color, width, 5.0, true, true)


func _population_radius(band: String) -> float:
	match band:
		"none":
			return 4.0
		"small":
			return 7.0
		"medium":
			return 10.0
		_:
			return 13.0


func _prefix(evidence_class: String) -> String:
	match evidence_class:
		Evidence.LABEL_OBJECTIVE:
			return "O|"
		Evidence.LABEL_SUBJECTIVE:
			return "S<>"
		_:
			return "A~"
