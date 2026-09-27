extends RefCounted

const MotionPath := preload("res://scripts/view/motion_path.gd")
const ItemTravel := preload("res://scripts/view/item_travel.gd")
const ConnectionLayer := preload("res://scripts/view/connection_layer.gd")
const Protocol := preload("res://scripts/protocol/models.gd")
const Scale := preload("res://scripts/presentation/scale.gd")


func run() -> Array:
	var failures: Array = []
	_path(failures)
	_items(failures)
	_segment(failures)
	return failures


func _path(failures: Array) -> void:
	var start := Vector2(0, 0)
	var finish := Vector2(100, 0)
	var points := MotionPath.along_connection(start, Vector2(0, 100), Vector2(100, 100), finish)
	var middle := MotionPath.sample(points, 0.5)
	if middle.distance_to(Vector2(50, 100)) > 0.01:
		failures.append("connection midpoint left the rendered segment")
	if middle.distance_to(start.lerp(finish, 0.5)) < 1.0:
		failures.append("connection path collapsed to a slot lerp")
	if MotionPath.sample(points, 0.0).distance_to(start) > 0.01:
		failures.append("path does not start at the origin slot")
	if MotionPath.sample(points, 1.0).distance_to(finish) > 0.01:
		failures.append("path does not end at the destination slot")
	var direct := MotionPath.straight(start, finish)
	if MotionPath.sample(direct, 0.5).distance_to(Vector2(50, 0)) > 0.01:
		failures.append("direct path should stay on the slot segment")


func _items(failures: Array) -> void:
	var actor := Vector2(10, 20)
	var target := Vector2(80, 20)
	var ground := Vector2(40, 90)
	var took: Dictionary = ItemTravel.endpoints("AGENT_TOOK_ITEM", actor, target, ground)
	var dropped: Dictionary = ItemTravel.endpoints("AGENT_DROPPED_ITEM", actor, target, ground)
	var gave: Dictionary = ItemTravel.endpoints("AGENT_GAVE_ITEM", actor, target, ground)
	if took["from"] != ground or took["to"] != actor:
		failures.append("taken item should travel from the ground toward the actor")
	if dropped["from"] != actor or dropped["to"] != ground:
		failures.append("dropped item should travel from the actor into the zone")
	if gave["from"] != actor or gave["to"] != target:
		failures.append("given item should travel from the actor toward the target")


func _segment(failures: Array) -> void:
	var parsed = Protocol.parse_text("frame", FileAccess.get_file_as_string("res://fixtures/protocol/reference_frame.json"))
	if not parsed.ok:
		failures.append("reference frame did not parse")
		return
	var layer = ConnectionLayer.new()
	var centers := {
		"loc-camp": Vector2(50, 50),
		"loc-spring": Vector2(9, 9),
		"loc-grove": Vector2(4, 4),
	}
	layer.show_world(parsed.value.world, centers)
	var linked: Dictionary = layer.segment("loc-camp", "loc-spring")
	var missing: Dictionary = layer.segment("loc-grove", "loc-spring")
	layer.free()
	if not bool(linked.get("drawn", false)):
		failures.append("camp-spring connection was not the rendered link")
	var expected_from := Scale.to_pixels(0.0, -28.0)
	var expected_to := Scale.to_pixels(0.0, -64.0)
	var from_point: Vector2 = linked["from"]
	var to_point: Vector2 = linked["to"]
	if from_point.distance_to(expected_from) > 0.01:
		failures.append("connection start ignored the origin anchor")
	if to_point.distance_to(expected_to) > 0.01:
		failures.append("connection end ignored the destination anchor")
	if bool(missing.get("drawn", true)):
		failures.append("unlinked locations drew a connection")
