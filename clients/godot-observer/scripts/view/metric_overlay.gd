extends Node2D

## ANALYTICAL metric family markers (groups/norms/conventions/reputation/etc.).

const ObserverLog := preload("res://scripts/log.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")

var enabled := false
var overlay_kind := "metric"
var _payload: Variant = null
var _centers := {}


func set_centers(centers: Dictionary) -> void:
	_centers = centers
	_rebuild()


func apply_payload(payload: Variant) -> void:
	if typeof(payload) != TYPE_DICTIONARY:
		_payload = null
	else:
		_payload = payload
	_rebuild()


func set_enabled(value: bool) -> void:
	enabled = value
	_rebuild()
	ObserverLog.debug(
		"view",
		"analytical_overlay kind=%s marker_count=%s evidence_class=%s" % [
			overlay_kind,
			get_child_count(),
			EvidenceClass.ANALYTICAL,
		],
	)


func _rebuild() -> void:
	var existing := get_children()
	for child in existing:
		remove_child(child)
		child.free()
	if not enabled or _payload == null:
		return
	var markers := _extract_markers()
	for entry in markers:
		var location_id := str(entry.get("location_id", ""))
		var point: Vector2 = _centers.get(location_id, Vector2.ZERO)
		if location_id != "" and not _centers.has(location_id):
			continue
		var marker := Node2D.new()
		marker.name = "AnalyticalMarker"
		marker.position = point
		marker.set_meta("evidence_class", EvidenceClass.ANALYTICAL)
		marker.set_meta("overlay_kind", overlay_kind)
		marker.set_meta("copy", "ANALYTICAL %s" % overlay_kind)
		marker.set_meta("style", "dashed")
		var badge := Label.new()
		badge.text = "ANALYTICAL"
		badge.modulate = Themes.evidence_color(EvidenceClass.ANALYTICAL)
		badge.position = Vector2(-20, -22)
		marker.add_child(badge)
		add_child(marker)
	ObserverLog.debug(
		"view",
		"analytical_overlay kind=%s marker_count=%s evidence_class=%s" % [
			overlay_kind,
			get_child_count(),
			EvidenceClass.ANALYTICAL,
		],
	)


func _extract_markers() -> Array:
	var rows: Array = []
	if _payload.has("readings") and _payload["readings"] is Array:
		for item in _payload["readings"]:
			if typeof(item) == TYPE_DICTIONARY and str(item.get("location_id", "")) != "":
				rows.append(item)
		return rows
	var values: Variant = _payload.get("values", {})
	if typeof(values) != TYPE_DICTIONARY:
		# List-style documents: emit one list marker at origin when non-empty.
		if not _payload.is_empty():
			rows.append({"location_id": ""})
		return rows
	for key in ["location_ids", "locations", "cluster_locations"]:
		var listed: Variant = values.get(key, null)
		if listed is Array:
			for location_id in listed:
				rows.append({"location_id": str(location_id)})
	if rows.is_empty() and not values.is_empty():
		rows.append({"location_id": ""})
	return rows
