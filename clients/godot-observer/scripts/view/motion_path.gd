extends RefCounted


static func straight(start: Vector2, finish: Vector2) -> PackedVector2Array:
	var points := PackedVector2Array()
	points.append(start)
	points.append(finish)
	return points


static func along_connection(start: Vector2, origin_end: Vector2, destination_end: Vector2, finish: Vector2) -> PackedVector2Array:
	return _compact([start, origin_end, destination_end, finish])


static func sample(points: PackedVector2Array, weight: float) -> Vector2:
	if points.is_empty():
		return Vector2.ZERO
	if points.size() == 1 or weight <= 0.0:
		return points[0]
	if weight >= 1.0:
		return points[points.size() - 1]
	var total := 0.0
	var lengths: Array[float] = []
	for index in points.size() - 1:
		var length := points[index].distance_to(points[index + 1])
		lengths.append(length)
		total += length
	if total <= 0.0:
		return points[points.size() - 1]
	var walked := weight * total
	for index in lengths.size():
		var span: float = lengths[index]
		if walked <= span or index == lengths.size() - 1:
			var local := 0.0 if span <= 0.0 else walked / span
			return points[index].lerp(points[index + 1], clampf(local, 0.0, 1.0))
		walked -= span
	return points[points.size() - 1]


static func _compact(raw: Array) -> PackedVector2Array:
	var points := PackedVector2Array()
	for entry in raw:
		var point: Vector2 = entry
		if points.is_empty() or points[points.size() - 1].distance_to(point) > 0.5:
			points.append(point)
	return points
