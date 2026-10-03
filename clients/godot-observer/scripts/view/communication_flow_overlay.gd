extends Node2D

## OBJECTIVE delivery edges from Talk/Ask/Told structure only.
## Strategy categories stay off this layer.

const ObserverLog := preload("res://scripts/log.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")

const _EDGE_CAP := 24

var enabled := false
var _agent_points := {}
var _edges: Array = []


func set_agent_points(points: Dictionary) -> void:
	_agent_points = points
	queue_redraw()


func set_enabled(value: bool) -> void:
	enabled = value
	if not enabled:
		_edges.clear()
	ObserverLog.debug(
		"view",
		"overlay_toggled kind=communication_flows evidence_class=%s enabled=%s" % [
			EvidenceClass.OBJECTIVE,
			enabled,
		],
	)
	queue_redraw()


func record_delivery(actor_id: String, other_id: String, speech_type: String) -> void:
	if not enabled:
		return
	if actor_id == "" or other_id == "":
		return
	_edges.append({
		"actor_id": actor_id,
		"other_id": other_id,
		"speech_type": speech_type,
	})
	while _edges.size() > _EDGE_CAP:
		_edges.pop_front()
	ObserverLog.debug(
		"view",
		"overlay_markers kind=communication_flows count=%s evidence_class=%s" % [
			_edges.size(),
			EvidenceClass.OBJECTIVE,
		],
	)
	queue_redraw()


func clear_edges() -> void:
	_edges.clear()
	queue_redraw()


func _draw() -> void:
	if not enabled:
		return
	for edge in _edges:
		var from_id := str(edge.get("actor_id", ""))
		var to_id := str(edge.get("other_id", ""))
		if not _agent_points.has(from_id) or not _agent_points.has(to_id):
			continue
		var start: Vector2 = _agent_points[from_id]
		var finish: Vector2 = _agent_points[to_id]
		draw_line(start, finish, Themes.evidence_color(EvidenceClass.OBJECTIVE), 1.5)
		var mid := start.lerp(finish, 0.5)
		var font := ThemeDB.fallback_font
		draw_string(
			font,
			mid + Vector2(4, -4),
			"OBJECTIVE %s" % str(edge.get("speech_type", "")),
			HORIZONTAL_ALIGNMENT_LEFT,
			-1,
			10,
			Themes.evidence_color(EvidenceClass.OBJECTIVE),
		)
