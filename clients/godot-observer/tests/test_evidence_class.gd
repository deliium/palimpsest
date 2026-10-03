extends RefCounted

const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _labels_and_mapping(), "evidence class labels")
	_expect(failures, _theme_tokens(), "evidence theme tokens")
	_expect(failures, _legend_defaults_off(), "overlay legend defaults off")
	return failures


func _labels_and_mapping() -> String:
	if EvidenceClass.short_label(EvidenceClass.OBJECTIVE) != "OBJECTIVE":
		return "objective short label"
	if EvidenceClass.short_label(EvidenceClass.SUBJECTIVE) != "SUBJECTIVE":
		return "subjective short label"
	if EvidenceClass.short_label(EvidenceClass.ANALYTICAL) != "ANALYTICAL":
		return "analytical short label"
	if EvidenceClass.for_overlay("territorial_claims") != EvidenceClass.SUBJECTIVE:
		return "claims must be SUBJECTIVE"
	if EvidenceClass.for_overlay("spatial_control") != EvidenceClass.ANALYTICAL:
		return "spatial_control must be ANALYTICAL"
	if EvidenceClass.for_overlay("communication_flows") != EvidenceClass.OBJECTIVE:
		return "communication_flows must be OBJECTIVE"
	if not EvidenceClass.is_valid(EvidenceClass.ANALYTICAL):
		return "analytical should be valid"
	return ""


func _theme_tokens() -> String:
	if Themes.evidence_color("OBJECTIVE") != Themes.EVIDENCE_OBJECTIVE:
		return "objective color"
	if Themes.evidence_color("SUBJECTIVE_TO_SELECTED_AGENT") != Themes.EVIDENCE_SUBJECTIVE:
		return "subjective color"
	if Themes.evidence_color("ANALYTICAL_INFERRED") != Themes.EVIDENCE_ANALYTICAL:
		return "analytical color"
	return ""


func _legend_defaults_off() -> String:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	var legend = load("res://scenes/ui/overlay_legend.tscn").instantiate()
	if legend == null:
		return "legend missing"
	tree.root.add_child(legend)
	if legend.is_overlay_enabled("relationships"):
		legend.queue_free()
		return "relationships should default off"
	if legend.is_overlay_enabled("spatial_control"):
		legend.queue_free()
		return "spatial_control should default off"
	var seen := {"kind": "", "class": "", "enabled": false}
	legend.overlay_toggled.connect(func(kind: String, evidence_class: String, enabled: bool) -> void:
		seen["kind"] = kind
		seen["class"] = evidence_class
		seen["enabled"] = enabled
	)
	legend.set_overlay_enabled("relationships", true)
	if seen["kind"] != "relationships" or not seen["enabled"]:
		legend.queue_free()
		return "toggle signal missing"
	if seen["class"] != EvidenceClass.SUBJECTIVE:
		legend.queue_free()
		return "toggle evidence class"
	var logged := "\n".join(preload("res://scripts/log.gd").recent)
	if "overlay_toggled kind=relationships" not in logged:
		legend.queue_free()
		return "toggle log missing"
	legend.queue_free()
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
