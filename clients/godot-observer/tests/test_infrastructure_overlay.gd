extends RefCounted

const InfrastructureOverlay := preload("res://scripts/view/infrastructure_overlay.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _mapping(), "infrastructure overlay mapping")
	_expect(failures, _styles(), "infrastructure overlay styles")
	_expect(failures, _unknown_kind(), "infrastructure unknown kind")
	_expect(failures, _forbidden(), "infrastructure forbidden payload")
	_expect(failures, _kind_payload(), "infrastructure kind payload")
	_expect(failures, _route_payload(), "infrastructure route payload")
	_expect(failures, _no_write_path(), "infrastructure no write path")
	return failures


func _mapping() -> String:
	if InfrastructureOverlay.evidence_for_kind("infrastructure_node") != EvidenceClass.OBJECTIVE:
		return "node must be objective"
	if InfrastructureOverlay.evidence_for_kind("infrastructure_edge") != EvidenceClass.OBJECTIVE:
		return "edge must be objective"
	if InfrastructureOverlay.evidence_for_kind("infrastructure_damaged") != EvidenceClass.OBJECTIVE:
		return "damaged must be objective"
	if InfrastructureOverlay.evidence_for_kind("infrastructure_destroyed") != EvidenceClass.OBJECTIVE:
		return "destroyed must be objective"
	if InfrastructureOverlay.evidence_for_kind("unknown_kind") != "":
		return "unknown kind must not guess a class"
	if EvidenceClass.for_overlay("infrastructure_node") != EvidenceClass.OBJECTIVE:
		return "evidence_class node mapping"
	if EvidenceClass.for_overlay("infrastructure_edge") != EvidenceClass.OBJECTIVE:
		return "evidence_class edge mapping"
	if EvidenceClass.for_overlay("infrastructure_damaged") != EvidenceClass.OBJECTIVE:
		return "evidence_class damaged mapping"
	if EvidenceClass.for_overlay("infrastructure_destroyed") != EvidenceClass.OBJECTIVE:
		return "evidence_class destroyed mapping"
	if EvidenceClass.for_overlay("route_open") != EvidenceClass.OBJECTIVE:
		return "evidence_class route open mapping"
	if EvidenceClass.for_overlay("route_restricted") != EvidenceClass.OBJECTIVE:
		return "evidence_class route restricted mapping"
	if EvidenceClass.for_overlay("route_closed") != EvidenceClass.OBJECTIVE:
		return "evidence_class route closed mapping"
	return ""


func _styles() -> String:
	var overlay = InfrastructureOverlay.new()
	var styles := {}
	for layer in [
		"infrastructure_node",
		"infrastructure_edge",
		"infrastructure_damaged",
		"infrastructure_destroyed",
	]:
		styles[str(overlay._marker_style(layer))] = true
	overlay.free()
	if styles.size() != 4:
		return "four distinct visual styles for infrastructure kinds"
	if styles.has("hidden"):
		return "known layers must not use hidden style"
	return ""


func _unknown_kind() -> String:
	var overlay = InfrastructureOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload({"items": [{"location_id": "loc-a", "topology": "node"}]}, "not_a_kind")
	if overlay.get_child_count() != 0:
		overlay.free()
		return "unknown kind must stay hidden"
	overlay.free()
	return ""


func _forbidden() -> String:
	var overlay = InfrastructureOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload(
		{"items": [{"location_id": "loc-a", "topology": "node", "score": 1}]},
		"infrastructure_node"
	)
	if overlay.get_child_count() != 0:
		overlay.free()
		return "forbidden score field must be rejected"
	overlay.apply_payload(
		{"items": [{"location_id": "loc-a", "topology": "node", "composite": true}]},
		"infrastructure_edge"
	)
	if overlay.get_child_count() != 0:
		overlay.free()
		return "forbidden composite field must be rejected"
	overlay.free()
	return ""


func _kind_payload() -> String:
	var overlay = InfrastructureOverlay.new()
	overlay.set_centers({"loc-a": Vector2.ZERO, "loc-b": Vector2.ZERO})
	overlay.set_enabled(true)
	overlay.apply_payload(
		{
			"items": [
				{
					"asset_id": "infra-1",
					"location_id": "loc-a",
					"topology": "node",
					"status": "operational",
				},
				{
					"asset_id": "infra-2",
					"location_id": "loc-b",
					"topology": "edge",
					"status": "operational",
				},
			]
		},
		"infrastructure_node"
	)
	if overlay.get_child_count() != 1:
		overlay.free()
		return "node topology should render"
	overlay.apply_payload(
		{
			"items": [
				{
					"asset_id": "infra-2",
					"location_id": "loc-b",
					"endpoint_location_id": "loc-a",
					"topology": "edge",
					"status": "operational",
				}
			]
		},
		"infrastructure_edge"
	)
	if overlay.get_child_count() != 1:
		overlay.free()
		return "edge topology should render"
	overlay.apply_payload(
		{
			"items": [
				{
					"asset_id": "infra-3",
					"location_id": "loc-a",
					"topology": "node",
					"status": "damaged",
				}
			]
		},
		"infrastructure_damaged"
	)
	if overlay.get_child_count() != 1:
		overlay.free()
		return "damaged status should render"
	overlay.apply_payload(
		{
			"items": [
				{
					"asset_id": "infra-4",
					"location_id": "loc-b",
					"topology": "node",
					"status": "destroyed",
				}
			]
		},
		"infrastructure_destroyed"
	)
	if overlay.get_child_count() != 1:
		overlay.free()
		return "destroyed status should render"
	var text := str(overlay._copy()).to_lower()
	if text.find("score") >= 0 or text.find("civilization") >= 0:
		overlay.free()
		return "copy must not use score/civilization"
	overlay.free()
	return ""


func _route_payload() -> String:
	var overlay = InfrastructureOverlay.new()
	overlay.set_centers({"loc-a": Vector2.ZERO, "loc-b": Vector2.ZERO, "loc-c": Vector2.ZERO})
	overlay.set_enabled(true)
	overlay.apply_payload(
		{
			"items": [
				{"origin_location_id": "loc-a", "destination_location_id": "loc-b", "status": "open"},
				{"origin_location_id": "loc-b", "destination_location_id": "loc-c", "status": "restricted"},
				{"origin_location_id": "loc-c", "destination_location_id": "loc-a", "status": "closed"},
			]
		},
		"infrastructure_edge"
	)
	if overlay.get_child_count() != 3:
		overlay.free()
		return "route rows must render through the objective edge overlay"
	var kinds := {}
	for child in overlay.get_children():
		kinds[str(child.get_meta("overlay_kind", ""))] = true
	if not kinds.has("infrastructure_edge"):
		overlay.free()
		return "open route status mapping"
	if not kinds.has("infrastructure_damaged"):
		overlay.free()
		return "restricted route status mapping"
	if not kinds.has("infrastructure_destroyed"):
		overlay.free()
		return "closed route status mapping"
	overlay.apply_payload(
		{"items": [{"origin_location_id": "loc-a", "destination_location_id": "loc-b", "status": "unknown"}]},
		"infrastructure_edge"
	)
	if overlay.get_child_count() != 0:
		overlay.free()
		return "unknown route status must stay hidden"
	overlay.apply_payload(
		{"items": [{"origin_location_id": "loc-a", "destination_location_id": "loc-b", "status": "open", "score": 1}]},
		"infrastructure_edge"
	)
	if overlay.get_child_count() != 0:
		overlay.free()
		return "route score field must be rejected"
	overlay.free()
	return ""


func _no_write_path() -> String:
	var overlay = InfrastructureOverlay.new()
	if overlay.has_method("publish") or overlay.has_method("write") or overlay.has_method("mutate"):
		overlay.free()
		return "overlay must not expose write methods"
	overlay.free()
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
