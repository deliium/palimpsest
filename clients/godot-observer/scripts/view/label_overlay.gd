extends Node2D

const ObserverLog := preload("res://scripts/log.gd")

var enabled := false
var _payload: Variant = null
var _centers := {}
var _objective_names := {}


func set_centers(centers: Dictionary) -> void:
	_centers = centers
	_rebuild()


func set_objective_names(names: Dictionary) -> void:
	_objective_names = names
	_rebuild()


func apply_payload(payload: Variant) -> void:
	if typeof(payload) != TYPE_DICTIONARY:
		_payload = null
	elif str(payload.get("layer", "")) != "subjective_labels":
		_payload = null
	else:
		_payload = payload
	_rebuild()


func set_enabled(value: bool) -> void:
	enabled = value
	_rebuild()
	ObserverLog.debug(
		"view",
		"label_overlay layer=%s markers=%s" % ["subjective_labels", get_child_count()],
	)


func primary_caption(objective_id: String) -> String:
	"""Canonical researcher identity stays primary; never replaced by slang."""
	if _objective_names.has(objective_id):
		return str(_objective_names[objective_id])
	return objective_id


func _rebuild() -> void:
	var existing := get_children()
	for child in existing:
		remove_child(child)
		child.free()
	if not enabled or _payload == null:
		return
	var readings: Variant = _payload.get("readings", [])
	if typeof(readings) != TYPE_ARRAY:
		return
	var seen := {}
	for reading in readings:
		if typeof(reading) != TYPE_DICTIONARY:
			continue
		var objective_id := str(reading.get("objective_id", ""))
		if objective_id == "" or seen.has(objective_id):
			continue
		if not _centers.has(objective_id):
			continue
		seen[objective_id] = true
		var label_display := str(reading.get("label_display", ""))
		if label_display == "":
			label_display = str(reading.get("label_token", ""))
		if label_display == "":
			continue
		var marker := Node2D.new()
		marker.name = "LabelMarker"
		marker.position = _centers.get(objective_id, Vector2.ZERO)
		marker.set_meta("objective_id", objective_id)
		marker.set_meta("objective_display", primary_caption(objective_id))
		marker.set_meta("subjective_label", label_display)
		marker.set_meta("copy", "~ %s" % label_display)
		marker.set_meta("label_source", str(reading.get("label_source", "agent_perspective")))
		var caption := Label.new()
		caption.text = "~ %s" % label_display
		caption.position = Vector2(-24, 10)
		caption.add_theme_color_override("font_color", Color(0.72, 0.86, 0.78))
		caption.add_theme_font_size_override("font_size", 11)
		marker.add_child(caption)
		add_child(marker)
