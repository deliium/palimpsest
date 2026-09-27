extends RefCounted
class_name ObserverSlots

const GOLDEN_ANGLE := 2.399963


static func ordered_entity_ids(entity_ids: Array) -> Array:
	var ordered: Array = entity_ids.duplicate()
	ordered.sort()
	return ordered


static func display_position(slot: Variant, bounds: Variant, index: int) -> Dictionary:
	# Display only. The request dictionary is never sent to the simulation.
	var request := {}
	if _has_coordinates(slot):
		return {
			"x": _number(slot, "local_x"),
			"y": _number(slot, "local_y"),
			"fallback": false,
			"request": request,
		}
	if _has_bounds(bounds):
		var width := _number(bounds, "width")
		var height := _number(bounds, "height")
		var radius := minf(width, height) * 0.25
		var angle := float(index) * GOLDEN_ANGLE
		var center_x := _number(bounds, "x") + width / 2.0
		var center_y := _number(bounds, "y") + height / 2.0
		return {
			"x": center_x + radius * cos(angle),
			"y": center_y + radius * sin(angle),
			"fallback": true,
			"request": request,
		}
	return {"x": 0.0, "y": 0.0, "fallback": true, "request": request}


static func _has_coordinates(slot: Variant) -> bool:
	if slot == null:
		return false
	var local_x = _raw(slot, "local_x")
	var local_y = _raw(slot, "local_y")
	return local_x != null and local_y != null


static func _has_bounds(bounds: Variant) -> bool:
	if bounds == null:
		return false
	return _raw(bounds, "width") != null and _raw(bounds, "height") != null


static func _raw(value: Variant, key: String) -> Variant:
	if value is Dictionary:
		return value.get(key, null)
	return value.get(key)


static func _number(value: Variant, key: String) -> float:
	return float(_raw(value, key))
