extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")
const Slots := preload("res://scripts/protocol/slots.gd")
const Scale := preload("res://scripts/presentation/scale.gd")

var _items: Array = []
var _resources: Array = []
var _structures: Array = []
var _artifacts: Array = []
var _agents: Array = []
var _locations: Array = []
var _centers := {}
var _hidden := {}
var _holder_points := {}


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)


func clear_world() -> void:
	_items = []
	_resources = []
	_structures = []
	_artifacts = []
	_agents = []
	_locations = []
	_centers = {}
	_hidden = {}
	_holder_points = {}
	queue_redraw()
	ObserverLog.debug("objects", "world_cleared")


func show_world(world: Variant, zone_centers: Dictionary) -> void:
	_items = world.items
	_resources = world.resources
	_structures = world.structures if world.get("structures") != null else []
	_artifacts = world.artifacts if world.get("artifacts") != null else []
	_agents = world.agents
	_locations = world.locations
	_centers = zone_centers
	_hidden = {}
	_holder_points = _build_holder_points()
	var ground_count := 0
	var held_count := 0
	for plan in paint_plan():
		if str(plan["placement"]) == "ground":
			ground_count += 1
		elif str(plan["placement"]) == "held":
			held_count += 1
	ObserverLog.debug(
		"artifacts",
		"artifacts_painted ground_count=%s held_count=%s" % [ground_count, held_count],
	)
	ObserverLog.debug("structures", "structures_painted count=%s" % _structures.size())
	queue_redraw()


func structure_at(location_id: String) -> Variant:
	for structure in _structures:
		if str(structure.location_id) == location_id:
			return structure
	return null


func structures_plan() -> Array:
	var plan: Array = []
	var index_by_location := {}
	for structure in _structures:
		var location_id := str(structure.location_id)
		var seen: int = int(index_by_location.get(location_id, 0))
		index_by_location[location_id] = seen + 1
		var integrity := float(structure.integrity)
		var band := "high"
		if integrity < 0.34:
			band = "low"
		elif integrity < 0.67:
			band = "mid"
		plan.append({
			"structure_id": str(structure.structure_id),
			"location_id": location_id,
			"kind": str(structure.kind),
			"integrity": integrity,
			"integrity_band": band,
			"stored_quantity": int(structure.stored_quantity),
			"point": _structure_origin(location_id, seen),
			"color": Themes.structure_color(structure.kind),
		})
	return plan


func paint_plan() -> Array:
	## Objective glyphs from kind tokens only. Marks and interpretation are unused.
	var plan: Array = []
	var ground_index := {}
	var held_index := {}
	for artifact in _artifacts:
		var kind := str(artifact.kind)
		var color: Color = Themes.artifact_color(kind)
		var icon := Themes.artifact_icon(kind)
		if artifact.location_id != null and str(artifact.location_id) != "":
			var location_id := str(artifact.location_id)
			var seen: int = int(ground_index.get(location_id, 0))
			ground_index[location_id] = seen + 1
			plan.append({
				"artifact_id": str(artifact.artifact_id),
				"kind": kind,
				"icon": icon,
				"color": color,
				"placement": "ground",
				"location_id": location_id,
				"holder_id": "",
				"point": _artifact_ground_origin(location_id, seen),
				"label": kind,
			})
			continue
		if artifact.holder_id == null or str(artifact.holder_id) == "":
			continue
		var holder_id := str(artifact.holder_id)
		if not _holder_points.has(holder_id):
			continue
		var held_seen: int = int(held_index.get(holder_id, 0))
		held_index[holder_id] = held_seen + 1
		var anchor: Vector2 = _holder_points[holder_id]
		plan.append({
			"artifact_id": str(artifact.artifact_id),
			"kind": kind,
			"icon": icon,
			"color": color,
			"placement": "held",
			"location_id": "",
			"holder_id": holder_id,
			"point": anchor + Vector2(14.0 + float(held_seen) * 10.0, -14.0),
			"label": kind,
		})
	return plan


func ground_point(location_id: String, item_id: String) -> Vector2:
	var index := 0
	var found := false
	for item in _items:
		if str(item.item_id) == item_id:
			found = true
			break
		if item.location_id != null and str(item.location_id) == location_id:
			index += 1
	if not found:
		for item in _items:
			if item.location_id != null and str(item.location_id) == location_id:
				index += 1
	return _ground_origin(location_id, index)


func hold_item(item_id: String) -> void:
	if item_id == "":
		return
	_hidden[item_id] = true
	queue_redraw()


func release_item(item_id: String) -> void:
	_hidden.erase(item_id)
	queue_redraw()


func _draw() -> void:
	var font := ThemeDB.fallback_font
	var font_size := ThemeDB.fallback_font_size
	for entry in structures_plan():
		var point: Vector2 = entry["point"]
		var color: Color = entry["color"]
		var size := Vector2(14, 12)
		draw_rect(Rect2(point - size * 0.5, size), color, true)
		var band := str(entry["integrity_band"])
		var outline := Color(0.85, 0.85, 0.8, 0.9)
		if band == "mid":
			outline = Color(0.9, 0.7, 0.3, 0.95)
		elif band == "low":
			outline = Color(0.9, 0.35, 0.28, 0.95)
		draw_rect(Rect2(point - size * 0.5, size), outline, false, 1.5)
		var stored := int(entry["stored_quantity"])
		if stored > 0:
			draw_circle(point + Vector2(8, -8), 3.0, Color(0.95, 0.85, 0.45, 0.95))
		draw_string(
			font,
			point + Vector2(10, 4),
			str(entry["kind"]),
			HORIZONTAL_ALIGNMENT_LEFT,
			-1,
			font_size,
			Color(0.92, 0.9, 0.84),
		)
	var resource_index := {}
	for resource in _resources:
		var seen: int = int(resource_index.get(resource.location_id, 0))
		resource_index[resource.location_id] = seen + 1
		var center: Vector2 = _centers.get(resource.location_id, Vector2.ZERO)
		var point := center + Vector2(-40.0, 28.0 + seen * 18.0)
		draw_circle(point, 5.0, Color(0.45, 0.75, 0.85))
		var label := "%s %s %s" % [resource.name, resource.quantity, resource.unit]
		draw_string(font, point + Vector2(10, 4), label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0.9, 0.95, 0.96))
	var ground_index := {}
	for item in _items:
		if item.location_id == null:
			continue
		var seen: int = int(ground_index.get(item.location_id, 0))
		ground_index[item.location_id] = seen + 1
		if _hidden.has(str(item.item_id)):
			continue
		var point := _ground_origin(str(item.location_id), seen)
		var item_color: Color = Themes.item_color(item.kind)
		if Themes.is_tool_kind(item.kind):
			draw_colored_polygon(
				PackedVector2Array([
					point + Vector2(0, -6),
					point + Vector2(5, 5),
					point + Vector2(-5, 5),
				]),
				item_color,
			)
		else:
			draw_rect(Rect2(point - Vector2(5, 5), Vector2(10, 10)), item_color, true)
		draw_string(font, point + Vector2(10, 4), item.name, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0.96, 0.92, 0.82))
	for entry in paint_plan():
		var point: Vector2 = entry["point"]
		var color: Color = entry["color"]
		var kind := str(entry["kind"])
		if str(entry["placement"]) == "held":
			draw_circle(point, 4.0, color)
			draw_arc(point, 6.0, 0.0, TAU, 16, Color(color.r, color.g, color.b, 0.85), 1.2)
		else:
			draw_colored_polygon(
				PackedVector2Array([
					point + Vector2(0, -7),
					point + Vector2(6, 0),
					point + Vector2(0, 7),
					point + Vector2(-6, 0),
				]),
				color,
			)
		draw_string(
			font,
			point + Vector2(8, 4),
			kind,
			HORIZONTAL_ALIGNMENT_LEFT,
			-1,
			font_size,
			Color(0.94, 0.93, 0.88),
		)


func _ground_origin(location_id: String, index: int) -> Vector2:
	var center: Vector2 = _centers.get(location_id, Vector2.ZERO)
	return center + Vector2(24.0, 16.0 + float(index) * 18.0)


func _artifact_ground_origin(location_id: String, index: int) -> Vector2:
	var center: Vector2 = _centers.get(location_id, Vector2.ZERO)
	return center + Vector2(-24.0, 16.0 + float(index) * 18.0)


func _structure_origin(location_id: String, index: int) -> Vector2:
	var center: Vector2 = _centers.get(location_id, Vector2.ZERO)
	return center + Vector2(0.0, -28.0 - float(index) * 16.0)


func _build_holder_points() -> Dictionary:
	var points := {}
	var grouped := {}
	for agent in _agents:
		var bucket: Array = grouped.get(str(agent.location_id), [])
		bucket.append(agent)
		grouped[str(agent.location_id)] = bucket
	for location_id in grouped.keys():
		var agents: Array = grouped[location_id]
		agents.sort_custom(func(left, right) -> bool: return str(left.entity_id) < str(right.entity_id))
		var location = _location(str(location_id))
		var bounds = null
		if location != null and location.presentation != null:
			bounds = location.presentation.visual_bounds
		for index in agents.size():
			var agent = agents[index]
			var placed: Dictionary = Slots.display_position(agent.presentation_slot, bounds, index)
			points[str(agent.entity_id)] = Scale.to_pixels(float(placed["x"]), float(placed["y"]))
	return points


func _location(location_id: String) -> Variant:
	for location in _locations:
		if str(location.location_id) == location_id:
			return location
	return null
