extends RefCounted

const MigrationOverlay := preload("res://scripts/view/migration_overlay.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _mapping(), "migration overlay mapping")
	_expect(failures, _styles(), "migration overlay styles")
	_expect(failures, _unknown_kind(), "migration unknown kind")
	_expect(failures, _forbidden(), "migration forbidden payload")
	_expect(failures, _kind_payload(), "migration kind payload")
	_expect(failures, _no_write_path(), "migration no write path")
	return failures


func _mapping() -> String:
	if MigrationOverlay.evidence_for_kind("migration_route") != EvidenceClass.OBJECTIVE:
		return "route must be objective"
	if MigrationOverlay.evidence_for_kind("migration_cause") != EvidenceClass.SUBJECTIVE:
		return "cause must be subjective"
	if MigrationOverlay.evidence_for_kind("migration_wave") != EvidenceClass.ANALYTICAL:
		return "wave must be analytical"
	if MigrationOverlay.evidence_for_kind("migration_integration") != EvidenceClass.ANALYTICAL:
		return "integration must be analytical"
	if MigrationOverlay.evidence_for_kind("unknown_kind") != "":
		return "unknown kind must not guess a class"
	if EvidenceClass.for_overlay("migration_route") != EvidenceClass.OBJECTIVE:
		return "evidence_class route mapping"
	if EvidenceClass.for_overlay("migration_cause") != EvidenceClass.SUBJECTIVE:
		return "evidence_class cause mapping"
	return ""


func _styles() -> String:
	var overlay = MigrationOverlay.new()
	var styles := {}
	for layer in ["migration_route", "migration_cause", "migration_wave", "migration_integration"]:
		styles[str(overlay._marker_style(layer))] = true
	overlay.free()
	if styles.size() != 4:
		return "four distinct visual styles for cause/wave distinction"
	if styles.has("hidden"):
		return "known layers must not use hidden style"
	return ""


func _unknown_kind() -> String:
	var overlay = MigrationOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload({"items": [{"destination_token": "mdl-1"}]}, "not_a_kind")
	if overlay.get_child_count() != 0:
		overlay.free()
		return "unknown kind must stay hidden"
	overlay.free()
	return ""


func _forbidden() -> String:
	var overlay = MigrationOverlay.new()
	overlay.set_enabled(true)
	overlay.apply_payload(
		{"items": [{"destination_token": "mdl-1", "refugee": true}]},
		"migration_route"
	)
	if overlay.get_child_count() != 0:
		overlay.free()
		return "forbidden refugee field must be rejected"
	overlay.apply_payload(
		{"items": [{"destination_token": "mdl-1", "asylum": "x"}]},
		"migration_cause"
	)
	if overlay.get_child_count() != 0:
		overlay.free()
		return "forbidden asylum field must be rejected"
	overlay.apply_payload(
		{"items": [{"destination_token": "mdl-1", "forced": true}]},
		"migration_wave"
	)
	if overlay.get_child_count() != 0:
		overlay.free()
		return "forbidden forced field must be rejected"
	overlay.free()
	return ""


func _kind_payload() -> String:
	var overlay = MigrationOverlay.new()
	overlay.set_centers({"loc-1": Vector2.ZERO, "loc-2": Vector2.ZERO})
	overlay.set_enabled(true)
	overlay.apply_payload(
		{"items": [{"origin_token": "loc-1", "destination_token": "loc-2", "route_tokens": ["loc-1", "loc-2"]}]},
		"migration_route"
	)
	if overlay.get_child_count() < 1:
		overlay.free()
		return "route tokens should render"
	overlay.apply_payload(
		{"items": [{"cause_token": "mdcse-1", "cause_kind": "conflict", "anchor_token": ""}]},
		"migration_cause"
	)
	if overlay.get_child_count() != 1:
		overlay.free()
		return "cause token should render"
	overlay.apply_payload(
		{"items": [{"wave_token": "mig-1", "route_tokens": ["loc-1"], "displacement_classification": "displacement_like"}]},
		"migration_wave"
	)
	if overlay.get_child_count() != 1:
		overlay.free()
		return "wave tokens should render"
	overlay.apply_payload(
		{"items": [{"outcome_token": "mdo-1", "destination_token": "loc-2", "classification": "settled"}]},
		"migration_integration"
	)
	if overlay.get_child_count() != 1:
		overlay.free()
		return "integration tokens should render"
	var text := str(overlay._copy())
	if text.to_lower().find("refugee") >= 0 or text.to_lower().find("asylum") >= 0 or text.to_lower().find("forced") >= 0:
		overlay.free()
		return "copy must not use refugee/asylum/forced"
	overlay.free()
	return ""


func _no_write_path() -> String:
	var overlay = MigrationOverlay.new()
	if overlay.has_method("publish") or overlay.has_method("write") or overlay.has_method("mutate"):
		overlay.free()
		return "overlay must not expose write methods"
	overlay.free()
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
