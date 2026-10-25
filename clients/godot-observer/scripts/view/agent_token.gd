extends Node2D

const Identity := preload("res://scripts/presentation/identity.gd")

var entity_id := ""
var label := ""
var label_visible := true
var dead := false
var selected := false
var activity := ""
var fill := Color.WHITE
var demographic_badge := ""


func setup(agent: Variant, slot_label: String) -> void:
	entity_id = str(agent.entity_id)
	label = slot_label
	dead = Identity.is_dead(agent)
	fill = Identity.color_for(agent)
	queue_redraw()


func set_dead(value: bool) -> void:
	dead = value
	queue_redraw()


func set_selected(value: bool) -> void:
	selected = value
	queue_redraw()


func set_label_visible(value: bool) -> void:
	if label_visible == value:
		return
	label_visible = value
	queue_redraw()


func set_activity(text: String) -> void:
	activity = text
	queue_redraw()


func set_demographic_badge(text: String) -> void:
	demographic_badge = text
	queue_redraw()


func _draw() -> void:
	if dead:
		draw_line(Vector2(-8, -8), Vector2(8, 8), Color(0.75, 0.75, 0.75), 2.0)
		draw_line(Vector2(-8, 8), Vector2(8, -8), Color(0.75, 0.75, 0.75), 2.0)
	else:
		draw_circle(Vector2.ZERO, 8.0, fill)
	if selected:
		draw_arc(Vector2.ZERO, 12.0, 0.0, TAU, 24, Color(0.95, 0.86, 0.45), 1.5)
	var font := ThemeDB.fallback_font
	var font_size := 12
	if label_visible or selected:
		draw_string(font, Vector2(-16, -12), label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0.96, 0.95, 0.92))
	if demographic_badge != "":
		var badge_rect := Rect2(Vector2(-18, -34), Vector2(maxf(36.0, demographic_badge.length() * 6.0), 14))
		draw_rect(badge_rect, Color(0.12, 0.16, 0.18, 0.9))
		draw_rect(badge_rect, Color(0.45, 0.75, 0.6), false, 1.0)
		draw_string(font, Vector2(-15, -23), demographic_badge, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.86, 0.96, 0.9))
	if activity != "":
		draw_string(font, Vector2(-16, 22), activity, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0.85, 0.88, 0.8))
