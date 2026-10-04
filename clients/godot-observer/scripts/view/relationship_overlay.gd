extends Node2D

## SUBJECTIVE researcher edges. Dimension scores as list/edges — no friend/enemy labels.

const ObserverLog := preload("res://scripts/log.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")

var enabled := false
var _payload: Variant = null
var _agent_points := {}


func set_agent_points(points: Dictionary) -> void:
	_agent_points = points
	_rebuild()


func apply_payload(payload: Variant) -> void:
	if typeof(payload) != TYPE_DICTIONARY:
		_payload = null
	elif not payload.has("items"):
		_payload = null
	else:
		_payload = payload
	_rebuild()


func set_enabled(value: bool) -> void:
	enabled = value
	_rebuild()
	ObserverLog.debug(
		"view",
		"analytical_overlay kind=relationships marker_count=%s evidence_class=%s" % [
			get_child_count(),
			EvidenceClass.SUBJECTIVE,
		],
	)


func _rebuild() -> void:
	var existing := get_children()
	for child in existing:
		remove_child(child)
		child.free()
	if not enabled or _payload == null:
		return
	var items: Variant = _payload.get("items", [])
	if typeof(items) != TYPE_ARRAY:
		return
	var count := 0
	for item in items:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var target_id := str(item.get("target_id", ""))
		var owner_id := str(item.get("owner_id", ""))
		if target_id == "" or not _agent_points.has(target_id):
			# Targets may be agent ids; also try entity map keys already in points.
			if not _agent_points.has(target_id):
				continue
		var marker := Node2D.new()
		marker.name = "RelationshipMarker"
		marker.position = _agent_points.get(target_id, Vector2.ZERO)
		marker.set_meta("evidence_class", EvidenceClass.SUBJECTIVE)
		marker.set_meta("owner_id", owner_id)
		marker.set_meta("target_id", target_id)
		marker.set_meta("copy", "SUBJECTIVE relationship dimensions")
		var dims: Variant = item.get("dimensions", [])
		var dim_count: int = dims.size() if dims is Array else 0
		marker.set_meta("dimension_count", dim_count)
		var badge := Label.new()
		badge.text = "SUBJECTIVE dims=%s" % dim_count
		badge.modulate = Themes.evidence_color(EvidenceClass.SUBJECTIVE)
		badge.position = Vector2(8, -18)
		marker.add_child(badge)
		add_child(marker)
		count += 1
	ObserverLog.debug(
		"view",
		"analytical_overlay kind=relationships marker_count=%s evidence_class=%s" % [
			count,
			EvidenceClass.SUBJECTIVE,
		],
	)
