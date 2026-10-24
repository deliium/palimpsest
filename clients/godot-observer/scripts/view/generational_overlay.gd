extends Node2D

## Presentation-only care/kinship/mentorship chrome. Positions come from the
## existing location-based token layer; no body is created or moved here.

const MAX_EVENTS := 100
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")

var enabled := false
var _care: Array = []
var _seen := {}
var _positions: Dictionary = {}
var _links: Array = []
var _arrivals: Array = []
var _arrival_seen := {}


func set_enabled(value: bool) -> void:
	enabled = value
	queue_redraw()


func set_positions(positions: Dictionary) -> void:
	_positions = positions.duplicate()
	queue_redraw()


func apply_care_events(events: Array) -> void:
	if not enabled:
		return
	for event in events:
		var event_id := str(_field(event, "event_id"))
		if event_id.is_empty() or _seen.has(event_id):
			continue
		var type_name := str(_field(event, "type"))
		if type_name not in ["AGENT_FED", "AGENT_TRANSPORTED"]:
			continue
		_seen[event_id] = true
		_care.append({
			"event_id": event_id,
			"type": type_name,
			"actor_id": _nullable_str(_field(event, "actor_id")),
			"target_id": _nullable_str(_field(event, "target_id")),
			"tick": int(_field(event, "tick")),
			"location_id": _nullable_str(_field(event, "origin_location_id")),
		})
		while _care.size() > MAX_EVENTS:
			_care.pop_front()
	queue_redraw()


func set_links(links: Array) -> void:
	_links = []
	for link in links:
		_links.append(link)
	queue_redraw()


func apply_arrival_events(events: Array) -> void:
	if not enabled:
		return
	for event in events:
		var type_name := str(_field(event, "type"))
		if type_name not in ["AGENT_CREATED", "AGENT_ENTERED_WORLD", "AGENT_INITIALIZED"]:
			continue
		var target := _nullable_str(_field(event, "target_id"))
		if target.is_empty():
			target = _nullable_str(_field(event, "actor_id"))
		if target.is_empty():
			continue
		var key := "%s|%s" % [target, int(_field(event, "tick"))]
		if _arrival_seen.has(key):
			continue
		_arrival_seen[key] = true
		_arrivals.append({"target_id": target, "tick": int(_field(event, "tick")), "type": type_name})
		while _arrivals.size() > MAX_EVENTS:
			_arrivals.pop_front()
	queue_redraw()


func arrival_count() -> int:
	return _arrivals.size()


func care_count() -> int:
	return _care.size()


func link_count() -> int:
	return _links.size()


func clear() -> void:
	_care.clear()
	_seen.clear()
	_links.clear()
	_arrivals.clear()
	_arrival_seen.clear()
	_positions.clear()
	queue_redraw()


func _draw() -> void:
	if not enabled:
		return
	var font := ThemeDB.fallback_font
	for link in _links:
		var from_id := str(link.get("from", ""))
		var to_id := str(link.get("to", ""))
		if _positions.has(from_id) and _positions.has(to_id):
			draw_line(_positions[from_id], _positions[to_id], Color(0.9, 0.8, 0.35), 1.5)
	var row := 0
	for arrival in _arrivals.slice(maxi(0, _arrivals.size() - 4)):
		draw_string(font, Vector2(16, 276 + row * 14), "arrival/admitted %s @%s" % [arrival["target_id"], arrival["tick"]], HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.7, 0.9, 0.8))
		row += 1
	row = 0
	for care in _care.slice(maxi(0, _care.size() - 8)):
		var label := "%s %s -> %s @%s" % [
			care["type"], str(care["actor_id"]), str(care["target_id"]), care["tick"]
		]
		draw_string(font, Vector2(16, 300 + row * 14), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.9, 0.9, 0.82))
		if _positions.has(str(care["actor_id"])) and _positions.has(str(care["target_id"])):
			draw_line(
				_positions[str(care["actor_id"])],
				_positions[str(care["target_id"])],
				Color(0.55, 0.8, 0.55),
				1.0,
			)
		row += 1


func _field(value: Variant, key: String) -> Variant:
	if typeof(value) == TYPE_DICTIONARY:
		return value.get(key, null)
	return value.get(key)


func _nullable_str(value: Variant) -> String:
	return "" if value == null else str(value)
