extends RefCounted
class_name ObserverScale


static func pixels_per_unit() -> float:
	var raw: Variant = ProjectSettings.get_setting("palimpsest/pixels_per_unit", 8)
	var value := float(raw)
	if value <= 0.0:
		return 8.0
	return value


static func to_pixels(x: float, y: float) -> Vector2:
	var scale := pixels_per_unit()
	return Vector2(x * scale, y * scale)
