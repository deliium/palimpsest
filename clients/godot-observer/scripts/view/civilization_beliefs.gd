extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")
const Plan := preload("res://scripts/presentation/civilization_plan.gd")

signal row_inspect_requested(summary: Dictionary)

const BELIEF_KINDS := ["social_groups", "institutions"]
const MEMBER_HALO_CAP := 64
const SITE_CAP := 64
const GROUP_COLORS := [
	Color(0.62, 0.70, 0.86, 0.95),
	Color(0.70, 0.62, 0.86, 0.95),
	Color(0.58, 0.78, 0.72, 0.95),
	Color(0.82, 0.70, 0.56, 0.95),
	Color(0.76, 0.60, 0.68, 0.95),
	Color(0.60, 0.76, 0.82, 0.95),
	Color(0.72, 0.76, 0.58, 0.95),
	Color(0.66, 0.66, 0.78, 0.95),
]

var _semantic: Dictionary = {}
var _draw_plan: Dictionary = {}
var _lod := "full"


func apply_plan(semantic_plan: Dictionary) -> void:
	_semantic = semantic_plan.duplicate(true)
	_draw_plan = Plan.draw_plan(_semantic, _lod)
	queue_redraw()
	ObserverLog.debug(
		"civilization",
		"belief_plan groups=%s institutions=%s unplaced=%s" % [
			int(_semantic.get("counts", {}).get("social_groups", 0)),
			int(_semantic.get("counts", {}).get("institutions", 0)),
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


func has_plan() -> bool:
	return bool(_semantic.get("ok", false))


func semantic_plan() -> Dictionary:
	return _semantic


func draw_plan() -> Dictionary:
	return _draw_plan


func glyph_count() -> int:
	var count := 0
	for glyph in _draw_plan.get("glyphs", []):
		if str(glyph.get("kind", "")) in BELIEF_KINDS:
			count += 1
	return count


func node_count() -> int:
	var count := 0
	for glyph in _draw_plan.get("glyphs", []):
		var kind := str(glyph.get("kind", ""))
		if kind == "social_groups":
			count += mini(glyph.get("member_points", {}).size(), MEMBER_HALO_CAP)
		elif kind == "institutions":
			count += mini(glyph.get("site_points", []).size(), SITE_CAP)
	return count


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	var mouse := event as InputEventMouseButton
	if not mouse.pressed or mouse.button_index != MOUSE_BUTTON_LEFT:
		return
	var click := _hit(get_global_mouse_position())
	if click.is_empty():
		return
	row_inspect_requested.emit(click)
	ObserverLog.debug("civilization", "belief_inspected layer=%s" % str(click.get("layer", "")))
	get_viewport().set_input_as_handled()


func _hit(point: Vector2) -> Dictionary:
	var best := {}
	var best_distance := 18.0
	for glyph in _draw_plan.get("glyphs", []):
		var kind := str(glyph.get("kind", ""))
		if kind not in BELIEF_KINDS:
			continue
		var candidates: Array = []
		if kind == "social_groups":
			candidates = glyph.get("member_points", {}).values()
		else:
			candidates = glyph.get("site_points", [])
		for candidate in candidates:
			var distance := point.distance_to(candidate)
			if distance <= best_distance:
				best_distance = distance
				best = glyph.get("click", {}).duplicate(true)
	for label in _draw_plan.get("labels", []):
		if str(label.get("kind", "")) not in BELIEF_KINDS:
			continue
		var distance := point.distance_to(label.get("point", Vector2.ZERO))
		if distance <= best_distance:
			best_distance = distance
			best = label.get("click", {}).duplicate(true)
	return best


func _draw() -> void:
	if not bool(_draw_plan.get("ok", false)):
		return
	for glyph in _draw_plan.get("glyphs", []):
		match str(glyph.get("kind", "")):
			"social_groups":
				_draw_group(glyph)
			"institutions":
				_draw_institution(glyph)
	for label in _draw_plan.get("labels", []):
		if str(label.get("kind", "")) in BELIEF_KINDS:
			_draw_label(label)


func _draw_group(glyph: Dictionary) -> void:
	var points: Dictionary = glyph.get("member_points", {})
	var member_ids: Array = points.keys()
	member_ids.sort()
	var color := _group_color(str(glyph.get("color_key", "")))
	var inferred := str(glyph.get("style", "")) == "inferred_community"
	var drawn := 0
	for member_id in member_ids:
		if drawn >= MEMBER_HALO_CAP:
			break
		var point: Vector2 = points[member_id]
		if inferred:
			draw_arc(point, 12.0, 0.0, TAU, 24, color, 1.0, true)
			draw_dashed_line(point + Vector2(-14, 0), point + Vector2(14, 0), color, 1.0, 4.0, true, true)
		else:
			draw_arc(point, 11.0, 0.0, TAU, 24, color, 2.0, true)
		drawn += 1


func _draw_institution(glyph: Dictionary) -> void:
	var sites: Array = glyph.get("site_points", [])
	var color: Color = Themes.evidence_color(str(glyph.get("evidence_class", "")))
	var status := str(glyph.get("status", ""))
	var drawn := 0
	for index in sites.size():
		if drawn >= SITE_CAP:
			break
		var point: Vector2 = sites[index]
		_draw_pin(point, color, status, bool(glyph.get("historical_evidence", false)))
		drawn += 1


func _draw_pin(point: Vector2, color: Color, status: String, historical: bool) -> void:
	var top := point + Vector2(0, -12)
	draw_line(top, point, Color(color.r, color.g, color.b, 0.7), 1.5)
	draw_dashed_line(point + Vector2(5, -5), point + Vector2(13, -13), color, 1.0, 3.0, true, true)
	if status in ["collapsed", "lost"]:
		draw_line(point + Vector2(-5, -5), point + Vector2(5, 5), Color(0.9, 0.35, 0.28, 0.95), 2.0)
		draw_line(point + Vector2(-5, 5), point + Vector2(5, -5), Color(0.9, 0.35, 0.28, 0.95), 2.0)
	elif status in ["censored", "uncertain", "contested", "vacant", "gap"]:
		draw_dashed_line(point + Vector2(-7, -7), point + Vector2(7, 7), color, 1.0, 3.0, true, true)
		draw_arc(point, 6.0, 0.0, TAU, 16, color, 1.0, true)
	else:
		draw_circle(point, 5.0, Color(color.r, color.g, color.b, 0.55))
		draw_arc(point, 6.0, 0.0, TAU, 16, color, 1.5, true)
	if historical:
		draw_string(
			ThemeDB.fallback_font,
			point + Vector2(8, 4),
			"t",
			HORIZONTAL_ALIGNMENT_LEFT,
			-1,
			ThemeDB.fallback_font_size,
			color,
		)


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


func _group_color(key: String) -> Color:
	var value := 2166136261
	for index in key.length():
		value = (value ^ key.unicode_at(index)) * 16777619
		value = value & 0x7fffffff
	return GROUP_COLORS[value % GROUP_COLORS.size()]


func _prefix(evidence_class: String) -> String:
	match evidence_class:
		"OBJECTIVE":
			return "O|"
		"SUBJECTIVE":
			return "S<>"
		_:
			return "A~"
