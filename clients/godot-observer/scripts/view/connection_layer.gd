extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
const Scale := preload("res://scripts/presentation/scale.gd")

var _locations: Array = []
var _index := {}


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)


func show_world(world: Variant, zone_centers: Dictionary) -> void:
	_locations = world.locations
	_index = {}
	for location in _locations:
		_index[location.location_id] = location
	set_meta("zone_centers", zone_centers)
	queue_redraw()


func _draw() -> void:
	var centers: Dictionary = get_meta("zone_centers", {})
	var drawn := {}
	for location in _locations:
		for neighbor_id in location.neighbor_ids:
			if not _index.has(neighbor_id):
				continue
			var key := _pair_key(location.location_id, neighbor_id)
			if drawn.has(key):
				continue
			drawn[key] = true
			var from := _anchor(location, neighbor_id, centers)
			var other = _index[neighbor_id]
			var to := _anchor(other, location.location_id, centers)
			draw_line(from, to, Color(0.82, 0.78, 0.7, 0.85), 2.0)


func _anchor(location: Variant, neighbor_id: String, centers: Dictionary) -> Vector2:
	var presentation = location.presentation
	if presentation != null:
		for pair in presentation.connection_anchors:
			if str(pair[0]) == neighbor_id:
				return Scale.to_pixels(float(pair[1].x), float(pair[1].y))
	return centers.get(location.location_id, Vector2.ZERO)


func _pair_key(left: String, right: String) -> String:
	if left < right:
		return "%s|%s" % [left, right]
	return "%s|%s" % [right, left]
