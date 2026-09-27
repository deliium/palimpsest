extends Node2D

const ObserverLog := preload("res://scripts/log.gd")

var _items: Array = []
var _resources: Array = []
var _centers := {}


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)


func show_world(world: Variant, zone_centers: Dictionary) -> void:
	_items = world.items
	_resources = world.resources
	_centers = zone_centers
	queue_redraw()


func _draw() -> void:
	var font := ThemeDB.fallback_font
	var font_size := ThemeDB.fallback_font_size
	var resource_index := {}
	for resource in _resources:
		var seen: int = int(resource_index.get(resource.location_id, 0))
		resource_index[resource.location_id] = seen + 1
		var center: Vector2 = _centers.get(resource.location_id, Vector2.ZERO)
		var point := center + Vector2(-40.0, 28.0 + seen * 18.0)
		draw_circle(point, 5.0, Color(0.45, 0.75, 0.85))
		var label := "%s %s %s" % [resource.name, resource.quantity, resource.unit]
		draw_string(font, point + Vector2(10, 4), label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0.9, 0.95, 0.96))
	var ground_index := {}
	for item in _items:
		if item.location_id == null:
			continue
		var seen: int = int(ground_index.get(item.location_id, 0))
		ground_index[item.location_id] = seen + 1
		var center: Vector2 = _centers.get(item.location_id, Vector2.ZERO)
		var point := center + Vector2(24.0, 16.0 + seen * 18.0)
		draw_rect(Rect2(point - Vector2(5, 5), Vector2(10, 10)), Color(0.86, 0.72, 0.38), true)
		draw_string(font, point + Vector2(10, 4), item.name, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0.96, 0.92, 0.82))
