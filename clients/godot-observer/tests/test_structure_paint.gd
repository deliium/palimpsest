extends RefCounted

const Protocol := preload("res://scripts/protocol/models.gd")
const ObjectLayer := preload("res://scripts/view/object_layer.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _structures_from_frame(), "structures paint plan")
	_expect(failures, _tool_theme(), "tool kind theme")
	return failures


func _structures_from_frame() -> String:
	var parsed = Protocol.parse_text(
		"frame",
		FileAccess.get_file_as_string("res://fixtures/protocol/reference_frame.json")
	)
	if not parsed.ok:
		return "frame parse failed"
	var layer := ObjectLayer.new()
	var centers := {
		"loc-camp": Vector2(0, 0),
		"loc-spring": Vector2(0, -80),
		"loc-grove": Vector2(-80, 40),
		"loc-ridge": Vector2(80, 40),
	}
	layer.show_world(parsed.value.world, centers)
	var plan: Array = layer.structures_plan()
	if plan.size() != 1:
		layer.free()
		return "expected one structure"
	var entry: Dictionary = plan[0]
	if str(entry["structure_id"]) != "struct-shelter-1":
		layer.free()
		return "structure id"
	if str(entry["integrity_band"]) != "high":
		layer.free()
		return "integrity band"
	if int(entry["stored_quantity"]) != 2:
		layer.free()
		return "stored quantity cue"
	var logged := "\n".join(preload("res://scripts/log.gd").recent)
	if "structures_painted count=1" not in logged:
		layer.free()
		return "structures_painted log missing"
	layer.free()
	return ""


func _tool_theme() -> String:
	if not Themes.is_tool_kind("axe"):
		return "axe should be tool"
	if Themes.is_tool_kind("container"):
		return "container should not be tool"
	if Themes.item_color("axe") == Themes.item_color("container"):
		return "tool color should differ"
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
