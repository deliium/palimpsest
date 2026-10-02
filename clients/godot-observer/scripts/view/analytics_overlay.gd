extends Node2D

const ObserverLog := preload("res://scripts/log.gd")

var enabled := false
var _payload: Variant = null
var _centers := {}


func set_centers(centers: Dictionary) -> void:
	_centers = centers
	_rebuild()


func apply_payload(payload: Variant) -> void:
	if typeof(payload) != TYPE_DICTIONARY:
		_payload = null
	elif str(payload.get("layer", "")) != "research_analytics":
		_payload = null
	else:
		_payload = payload
	_rebuild()


func set_enabled(value: bool) -> void:
	enabled = value
	_rebuild()
	ObserverLog.debug(
		"view",
		"territorial_overlay layer=%s markers=%s" % ["research_analytics", get_child_count()],
	)


func _rebuild() -> void:
	var existing := get_children()
	for child in existing:
		remove_child(child)
		child.free()
	if not enabled or _payload == null:
		return
	for reading in _readings():
		var marker := Node2D.new()
		marker.name = "AnalyticsMarker"
		marker.position = _centers.get(reading["location_id"], Vector2.ZERO)
		marker.set_meta("style", reading["style"])
		marker.set_meta("copy", reading["copy"])
		marker.set_meta("location_id", reading["location_id"])
		marker.set_meta("contest_source", reading["contest_source"])
		add_child(marker)


func _readings() -> Array:
	var explicit: Variant = _payload.get("readings", [])
	if explicit is Array and not explicit.is_empty():
		var rows: Array = []
		for item in explicit:
			if typeof(item) != TYPE_DICTIONARY:
				continue
			var style := str(item.get("kind", ""))
			var source := str(item.get("contest_source", ""))
			if not _accepted(style, source):
				continue
			rows.append({
				"location_id": str(item.get("location_id", "")),
				"style": style,
				"contest_source": source,
				"copy": _copy_for(style),
			})
		return rows
	return _from_intervals()


func _from_intervals() -> Array:
	var values: Variant = _payload.get("values", {})
	if typeof(values) != TYPE_DICTIONARY:
		return []
	var rows: Array = []
	var seen := {}
	for piece in str(values.get("intervals", "")).split(";", false):
		var fields := piece.split(":")
		if fields.size() < 5:
			continue
		var location_id := str(fields[0])
		if location_id == "" or seen.has(location_id):
			continue
		seen[location_id] = true
		if bool(values.get("repeated_control", false)):
			rows.append(_row(location_id, "repeated_control", "objective_control"))
		if bool(values.get("control_contest", false)):
			rows.append(_row(location_id, "control_contest", "objective_control"))
		if values.get("claim_contest", false) == true:
			rows.append(_row(location_id, "claim_contest", "subjective_claims"))
	return rows


func _accepted(style: String, source: String) -> bool:
	if style == "repeated_control":
		return true
	if style == "control_contest":
		return source == "objective_control"
	if style == "claim_contest":
		return source == "subjective_claims"
	return false


func _row(location_id: String, style: String, source: String) -> Dictionary:
	return {
		"location_id": location_id,
		"style": style,
		"contest_source": source,
		"copy": _copy_for(style),
	}


func _copy_for(style: String) -> String:
	if style == "repeated_control":
		return "analytics detects repeated control here"
	return "several agents contest this location"
