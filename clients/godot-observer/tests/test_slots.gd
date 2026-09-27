extends RefCounted

const Slots := preload("res://scripts/protocol/slots.gd")


func run() -> Array:
	var failures: Array = []
	var placed: Dictionary = Slots.display_position(
		{"local_x": -8.0, "local_y": -80.0},
		{"x": -24.0, "y": -96.0, "width": 48.0, "height": 32.0, "screen_position_x": 99.0},
		0,
	)
	if not is_equal_approx(float(placed["x"]), -8.0) or not is_equal_approx(float(placed["y"]), -80.0):
		failures.append("slot coordinates were shifted or Y was negated")
	if bool(placed["fallback"]):
		failures.append("coordinates were treated as missing")
	var bounds := {"x": -40.0, "y": -30.0, "width": 80.0, "height": 60.0}
	var fallback: Dictionary = Slots.display_position({"slot_index": 1}, bounds, 1)
	var radius := minf(80.0, 60.0) * 0.25
	var angle := 2.399963
	var expected_x := 0.0 + radius * cos(angle)
	var expected_y := 0.0 + radius * sin(angle)
	if not bool(fallback["fallback"]):
		failures.append("missing coordinates should use the fallback")
	if not is_equal_approx(float(fallback["x"]), expected_x):
		failures.append("fallback x")
	if not is_equal_approx(float(fallback["y"]), expected_y):
		failures.append("fallback y was negated")
	if is_equal_approx(float(fallback["y"]), -expected_y) and not is_equal_approx(expected_y, 0.0):
		failures.append("fallback negated Y")
	var request: Dictionary = fallback["request"]
	if not request.is_empty() or request.has("local_x") or request.has("local_y") or request.has("x"):
		failures.append("fallback coordinates entered a request dictionary")
	var ordered: Array = Slots.ordered_entity_ids(["body-b", "body-a"])
	if ordered[0] != "body-a" or ordered[1] != "body-b":
		failures.append("occupants were not ordered by entity_id")
	return failures
