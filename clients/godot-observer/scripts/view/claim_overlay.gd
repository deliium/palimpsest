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
	elif str(payload.get("layer", "")) != "subjective_claims":
		_payload = null
	else:
		_payload = payload
	_rebuild()


func set_enabled(value: bool) -> void:
	enabled = value
	_rebuild()
	ObserverLog.debug(
		"view",
		"territorial_overlay layer=%s markers=%s" % ["subjective_claims", get_child_count()],
	)


func _rebuild() -> void:
	var existing := get_children()
	for child in existing:
		remove_child(child)
		child.free()
	if not enabled or _payload == null:
		return
	var seen := {}
	for head in _payload.get("heads", []):
		if typeof(head) != TYPE_DICTIONARY:
			continue
		var kind := str(head.get("target_kind", ""))
		if kind != "location" and kind != "frequent_area":
			continue
		var location_id := str(head.get("target_entity_id", ""))
		if location_id == "" or seen.has(location_id):
			continue
		seen[location_id] = true
		var marker := Node2D.new()
		marker.name = "ClaimMarker"
		marker.position = _centers.get(location_id, Vector2.ZERO)
		marker.set_meta("copy", "SUBJECTIVE selected agent claims this location")
		marker.set_meta("location_id", location_id)
		marker.set_meta("evidence_class", "SUBJECTIVE_TO_SELECTED_AGENT")
		add_child(marker)
