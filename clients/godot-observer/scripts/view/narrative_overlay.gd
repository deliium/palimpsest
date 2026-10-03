extends Node2D

## SUBJECTIVE narrative hop highlighter. No Myth furniture; no content tokens.

const ObserverLog := preload("res://scripts/log.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")

var enabled := false
var _payload: Variant = null
var _selected_variant_id := ""
var _centers := {}
var _agent_points := {}


func set_centers(centers: Dictionary) -> void:
	_centers = centers
	_rebuild()


func set_agent_points(points: Dictionary) -> void:
	_agent_points = points
	_rebuild()


func apply_payload(payload: Variant) -> void:
	if typeof(payload) != TYPE_DICTIONARY:
		_payload = null
	elif str(payload.get("layer", "")) != "subjective_narrative_hops":
		_payload = null
	else:
		_payload = payload
	_rebuild()


func set_enabled(value: bool) -> void:
	enabled = value
	_rebuild()


func select_variant(variant_id: String) -> void:
	_selected_variant_id = variant_id
	ObserverLog.info("view", "narrative_selected id=%s" % variant_id)
	_rebuild()


func variant_ids() -> Array[String]:
	var ids: Array[String] = []
	if _payload == null:
		return ids
	for item in _payload.get("variants", []):
		if typeof(item) == TYPE_DICTIONARY:
			ids.append(str(item.get("variant_id", "")))
	return ids


func selected_opaque_event_ids() -> Array[String]:
	## Opaque ids only — never content tokens or fingerprints.
	var ids: Array[String] = []
	var selected = _selected_variant()
	if selected == null:
		return ids
	for key in ["source_event_id", "last_communication_id"]:
		var value := str(selected.get(key, ""))
		if value != "" and value != "<null>" and not ids.has(value):
			ids.append(value)
	return ids


func _selected_variant() -> Variant:
	if _payload == null:
		return null
	var variants: Variant = _payload.get("variants", [])
	if typeof(variants) != TYPE_ARRAY:
		return null
	for item in variants:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		if _selected_variant_id == "" or str(item.get("variant_id", "")) == _selected_variant_id:
			return item
	return null


func _rebuild() -> void:
	var existing := get_children()
	for child in existing:
		remove_child(child)
		child.free()
	if not enabled or _payload == null:
		return
	var variants: Variant = _payload.get("variants", [])
	if typeof(variants) != TYPE_ARRAY or variants.is_empty():
		ObserverLog.warn("view", "narrative_overlay_unavailable reason_code=empty_ledger")
		return
	var selected = _selected_variant()
	if selected == null:
		return
	var hop := 0
	for carrier in selected.get("carrier_agent_ids", []):
		var carrier_id := str(carrier)
		var point: Vector2 = _agent_points.get(carrier_id, Vector2.ZERO)
		var marker := Node2D.new()
		marker.position = point
		marker.set_meta("evidence_class", EvidenceClass.SUBJECTIVE)
		marker.set_meta("copy", "SUBJECTIVE hop %s" % hop)
		var badge := Label.new()
		badge.text = "SUBJECTIVE #%s" % hop
		badge.modulate = Themes.evidence_color(EvidenceClass.SUBJECTIVE)
		badge.position = Vector2(6, -20)
		marker.add_child(badge)
		add_child(marker)
		hop += 1
	for location_id in selected.get("location_ids", []):
		var lid := str(location_id)
		if not _centers.has(lid):
			continue
		var place := Node2D.new()
		place.position = _centers[lid]
		place.set_meta("evidence_class", EvidenceClass.SUBJECTIVE)
		place.set_meta("copy", "SUBJECTIVE narrative location")
		add_child(place)
	var opaque := selected_opaque_event_ids()
	ObserverLog.debug(
		"view",
		"narrative_hops hop_count=%s location_count=%s opaque_event_count=%s" % [
			hop,
			selected.get("location_ids", []).size() if selected.get("location_ids", []) is Array else 0,
			opaque.size(),
		],
	)
