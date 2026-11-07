extends RefCounted

const BorderOverlay := preload("res://scripts/view/border_overlay.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _mapping(), "border overlay mapping")
	_expect(failures, _styles(), "border overlay styles")
	_expect(failures, _forbidden(), "border overlay forbidden payload")
	_expect(failures, _toggle_clear(), "border overlay clear")
	return failures


func _mapping() -> String:
	if BorderOverlay.layer_for_kind("border_physical") != "physical_control":
		return "physical kind mapping"
	if BorderOverlay.layer_for_kind("border_claims") != "subjective_claims":
		return "claims kind mapping"
	if BorderOverlay.layer_for_kind("border_agreements") != "subjective_agreements":
		return "agreements kind mapping"
	if BorderOverlay.layer_for_kind("border_patterns") != "analytical_pattern":
		return "patterns kind mapping"
	if BorderOverlay.evidence_for_layer("subjective_agreements") != EvidenceClass.SUBJECTIVE:
		return "agreement must stay subjective"
	if BorderOverlay.evidence_for_layer("analytical_pattern") != EvidenceClass.ANALYTICAL:
		return "pattern must stay analytical"
	return ""


func _styles() -> String:
	var overlay = BorderOverlay.new()
	var styles := {}
	for layer in ["physical_control", "subjective_claims", "subjective_agreements", "analytical_pattern"]:
		styles[str(overlay._marker_style(layer))] = true
	overlay.free()
	if styles.size() != 4:
		return "four distinct visual styles"
	return ""


func _forbidden() -> String:
	var overlay = BorderOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload({"layer": "subjective_claims", "rows": [{"winner": "x"}]})
	if overlay.get_child_count() != 0:
		overlay.free()
		return "forbidden field must be rejected"
	overlay.apply_payload({"layer": "unknown_layer", "rows": []})
	if overlay.get_child_count() != 0:
		overlay.free()
		return "unknown layer must be rejected"
	overlay.free()
	return ""


func _toggle_clear() -> String:
	var overlay = BorderOverlay.new()
	overlay.set_centers({"loc-1": Vector2.ZERO})
	overlay.set_enabled(true)
	overlay.apply_payload({"layer": "physical_control", "rows": [{"location_token": "loc-1"}]})
	if overlay.get_child_count() != 1:
		overlay.free()
		return "expected one marker"
	overlay.set_enabled(false)
	if overlay.get_child_count() != 0:
		overlay.free()
		return "toggle off must clear markers"
	overlay.free()
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
