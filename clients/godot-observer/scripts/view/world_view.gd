extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
const Playback := preload("res://scripts/protocol/playback.gd")
const ReducerScript := preload("res://scripts/protocol/reducer.gd")
const Router := preload("res://scripts/protocol/event_router.gd")

var playback_speed := 1.0

var _world_state: Variant = null
var _centers := {}
var _reducer = ReducerScript.new()

@onready var _locations: Node2D = $LocationLayer
@onready var _claims: Node2D = $ClaimOverlay
@onready var _analytics: Node2D = $AnalyticsOverlay
@onready var _labels: Node2D = $LabelOverlay
@onready var _relationships: Node2D = get_node_or_null("RelationshipOverlay")
@onready var _comm_flows: Node2D = get_node_or_null("CommunicationFlowOverlay")
@onready var _groups: Node2D = get_node_or_null("GroupOverlay")
@onready var _norms: Node2D = get_node_or_null("NormOverlay")
@onready var _conventions: Node2D = get_node_or_null("ConventionOverlay")
@onready var _reputation: Node2D = get_node_or_null("ReputationOverlay")
@onready var _teaching: Node2D = get_node_or_null("TeachingOverlay")
@onready var _skills: Node2D = get_node_or_null("SkillOverlay")
@onready var _narrative: Node2D = get_node_or_null("NarrativeOverlay")
@onready var _connections: Node2D = $ConnectionLayer
@onready var _objects: Node2D = $ObjectLayer
@onready var _agents: Node2D = $AgentLayer
@onready var _effects: Node2D = $EffectsLayer
@onready var _camera: Camera2D = $Camera2D

signal inspect_requested(snapshot: Dictionary)
signal inspect_cleared
signal location_selected(location_id: String)


func _ready() -> void:
	_agents.agent_selected.connect(_on_agent_selected)
	_agents.selection_cleared.connect(func() -> void: inspect_cleared.emit())
	if _locations != null and _locations.has_signal("location_selected"):
		_locations.location_selected.connect(func(location_id: String) -> void:
			location_selected.emit(location_id)
		)


func replace_sought_frame(frame: Variant, event: Variant, forward: bool) -> void:
	var prior: Dictionary = _agents.capture_positions()
	var selected: String = _agents.selected_entity_id
	_agents.clear_motions()
	_effects.clear_motions()
	ObserverLog.debug("view", "motions_cleared")
	show_world(frame.world)
	if selected == "":
		_maybe_tween(event, forward, prior)
		return
	var choice: Dictionary = _agents.selection_for(selected, frame.world.agents)
	if not bool(choice.get("keep", false)) or not _agents.highlight(selected):
		inspect_cleared.emit()
		_maybe_tween(event, forward, prior)
		return
	_on_agent_selected(selected)
	_maybe_tween(event, forward, prior)


func show_world(world: Variant) -> void:
	_world_state = world
	_locations.show_world(world)
	_centers = {}
	for location in world.locations:
		_centers[location.location_id] = _locations.zone_center(location.location_id)
	_connections.show_world(world, _centers)
	_objects.show_world(world, _centers)
	_agents.show_world(world, _centers, _reducer.activity)
	if _claims != null:
		_claims.set_centers(_centers)
	if _analytics != null:
		_analytics.set_centers(_centers)
	if _labels != null:
		var names := {}
		for location in world.locations:
			var caption := str(location.display_name)
			if caption == "":
				caption = str(location.name)
			names[location.location_id] = caption
		_labels.set_objective_names(names)
		_labels.set_centers(_centers)
	var agent_points := {}
	if _agents != null and _agents.has_method("capture_positions"):
		agent_points = _agents.capture_positions()
	if _relationships != null:
		_relationships.set_agent_points(agent_points)
	if _comm_flows != null:
		_comm_flows.set_agent_points(agent_points)
	for layer in [_groups, _norms, _conventions, _reputation, _teaching, _skills]:
		if layer != null:
			layer.set_centers(_centers)
	if _narrative != null:
		_narrative.set_centers(_centers)
		_narrative.set_agent_points(agent_points)


func set_claim_overlay_enabled(enabled: bool) -> void:
	if _claims != null:
		_claims.set_enabled(enabled)


func apply_subjective_claims(payload: Variant) -> void:
	if _claims != null:
		_claims.apply_payload(payload)


func set_analytics_overlay_enabled(enabled: bool) -> void:
	if _analytics != null:
		_analytics.set_enabled(enabled)


func apply_research_analytics(payload: Variant) -> void:
	if _analytics != null:
		_analytics.apply_payload(payload)


func set_label_overlay_enabled(enabled: bool) -> void:
	if _labels != null:
		_labels.set_enabled(enabled)


func apply_subjective_labels(payload: Variant) -> void:
	if _labels != null:
		_labels.apply_payload(payload)
		_labels.set_enabled(payload != null)


func set_relationship_overlay_enabled(enabled: bool) -> void:
	if _relationships != null:
		_relationships.set_enabled(enabled)


func apply_relationships(payload: Variant) -> void:
	if _relationships != null:
		_relationships.apply_payload(payload)


func set_communication_flows_enabled(enabled: bool) -> void:
	if _comm_flows != null:
		_comm_flows.set_enabled(enabled)


func set_metric_overlay_enabled(kind: String, enabled: bool) -> void:
	var layer := _metric_layer(kind)
	if layer != null:
		layer.set_enabled(enabled)


func apply_metric_overlay(kind: String, payload: Variant) -> void:
	var layer := _metric_layer(kind)
	if layer != null:
		layer.apply_payload(payload)


func clear_subjective_overlays() -> void:
	apply_subjective_labels(null)
	apply_subjective_claims(null)
	apply_relationships(null)
	apply_narrative_hops(null)
	set_claim_overlay_enabled(false)
	set_relationship_overlay_enabled(false)
	set_narrative_overlay_enabled(false)
	if _labels != null:
		_labels.set_enabled(false)


func clear_world() -> void:
	## Drop occupancy/overlays for the prior ObserverSource. Bookmarks stay on disk.
	_agents.clear_motions()
	_effects.clear_motions()
	_agents.clear_tokens()
	_locations.clear_world()
	_objects.clear_world()
	_connections.clear_world()
	if _comm_flows != null and _comm_flows.has_method("clear_edges"):
		_comm_flows.clear_edges()
	clear_subjective_overlays()
	apply_research_analytics(null)
	apply_strategy_audit(null)
	for kind in [
		"emergent_group_formation",
		"emergent_social_norms",
		"persistent_social_conventions",
		"distributed_reputation",
		"cultural_transmission",
		"skill_learning",
	]:
		apply_metric_overlay(kind, null)
		set_metric_overlay_enabled(kind, false)
	_centers = {}
	_world_state = null
	_reducer.clear()
	inspect_cleared.emit()
	ObserverLog.debug("view", "world_cleared")


func set_narrative_overlay_enabled(enabled: bool) -> void:
	if _narrative != null:
		_narrative.set_enabled(enabled)


func apply_narrative_hops(payload: Variant) -> void:
	if _narrative != null:
		_narrative.apply_payload(payload)


func select_narrative_variant(variant_id: String) -> void:
	if _narrative != null:
		_narrative.select_variant(variant_id)


func narrative_variant_ids() -> Array:
	if _narrative != null:
		return _narrative.variant_ids()
	return []


func narrative_opaque_event_ids() -> Array:
	if _narrative != null and _narrative.has_method("selected_opaque_event_ids"):
		return _narrative.selected_opaque_event_ids()
	return []


func apply_strategy_audit(payload: Variant) -> void:
	if _effects != null and _effects.has_method("set_strategy_audit"):
		_effects.set_strategy_audit(payload)


func set_research_speech_enabled(enabled: bool) -> void:
	if _effects != null and _effects.has_method("set_research_speech_enabled"):
		_effects.set_research_speech_enabled(enabled)


func _metric_layer(kind: String) -> Node2D:
	match kind:
		"emergent_group_formation":
			return _groups
		"emergent_social_norms":
			return _norms
		"persistent_social_conventions":
			return _conventions
		"distributed_reputation":
			return _reputation
		"cultural_transmission":
			return _teaching
		"skill_learning":
			return _skills
		_:
			return null


func play_event(event: Variant) -> void:
	if _world_state == null or not bool(event.known):
		if event != null and not bool(event.known):
			_effects.play({"action": "unknown", "type": str(event.type), "event_id": str(event.event_id)}, _agents, _locations)
		return
	var pending: int = _agents.active_motions() + _effects.active_count()
	var policy: Dictionary = Playback.policy(playback_speed, pending)
	var ground: Vector2 = _item_ground(event)
	var logical: Dictionary = _reducer.apply_event(_world_state, event)
	var command: Dictionary = Router.route(event, policy, logical)
	command["ground"] = ground
	_effects.play(command, _agents, _locations, _connections, _objects)
	if str(command.get("action", "")) == "speech" and _comm_flows != null:
		_comm_flows.record_delivery(
			str(command.get("entity_id", "")),
			str(command.get("other_id", "")),
			str(command.get("type", "")),
		)


func set_playback_speed(speed: float) -> void:
	playback_speed = speed


func zoom_in() -> void:
	_camera.zoom_step(1.1)


func zoom_out() -> void:
	_camera.zoom_step(0.9)


func reset_view() -> void:
	var selected: Variant = _agents.selected_position()
	var target: Vector2 = _centroid() if selected == null else selected
	_camera.reset_to(target)


func focus_selected() -> void:
	var selected: Variant = _agents.selected_position()
	if selected == null:
		return
	_camera.focus_on(selected)


func focus_agent(entity_id: String) -> void:
	var point: Variant = _agents.token_position(entity_id)
	if point == null:
		return
	_camera.focus_on(point)
	ObserverLog.debug("view", "follow_camera entity_id=%s" % entity_id)


func focus_location(location_id: String) -> void:
	if location_id.is_empty() or not _centers.has(location_id):
		return
	_camera.focus_on(_centers[location_id])
	ObserverLog.debug("view", "follow_camera location_id=%s" % location_id)

func _maybe_tween(event: Variant, forward: bool, prior: Dictionary) -> void:
	if event == null or not forward or not bool(event.known):
		return
	var pending: int = _agents.active_motions() + _effects.active_count()
	var policy: Dictionary = Playback.policy(playback_speed, pending)
	if bool(policy.get("skip", false)):
		return
	var body := ""
	if event.has_method("affected_entity_id"):
		var affected: Variant = event.affected_entity_id()
		body = "" if affected == null else str(affected)
	var logical := {
		"entity_id": body,
		"origin": "" if event.origin_location_id == null else str(event.origin_location_id),
		"destination": "" if event.destination_location_id == null else str(event.destination_location_id),
		"moved": str(event.type) == "AGENT_MOVED" or str(event.type) == "AGENT_FLED",
	}
	var command: Dictionary = Router.route(event, policy, logical)
	command["ground"] = _item_ground(event)
	if str(command.get("action", "")) == "move" and body != "" and prior.has(body):
		_agents.restore_position(body, prior[body])
	_effects.play(command, _agents, _locations, _connections, _objects)


func _on_agent_selected(entity_id: String) -> void:
	if _world_state == null:
		return
	var agent = null
	for candidate in _world_state.agents:
		if str(candidate.entity_id) == entity_id:
			agent = candidate
			break
	if agent == null:
		return
	var location_name := entity_id
	for location in _world_state.locations:
		if str(location.location_id) == str(agent.location_id):
			location_name = str(location.display_name) if str(location.display_name) != "" else str(location.name)
			break
	var inventory: Array[String] = []
	for item_id in agent.inventory_ids:
		var summary := str(item_id)
		for item in _world_state.items:
			if str(item.item_id) == str(item_id):
				summary = "%s (%s)" % [item.name, item.kind]
				break
		inventory.append(summary)
	var fields: Dictionary = _reducer.event_fields_for(entity_id)
	var structure_snapshot = null
	var at_location := _objects.structure_at(str(agent.location_id))
	if at_location != null:
		structure_snapshot = {
			"structure_id": str(at_location.structure_id),
			"kind": str(at_location.kind),
			"integrity": float(at_location.integrity),
			"stored_quantity": int(at_location.stored_quantity),
		}
	inspect_requested.emit({
		"entity_id": str(agent.entity_id),
		"agent_id": "" if agent.agent_id == null else str(agent.agent_id),
		"location_name": location_name,
		"life_status": str(agent.life_status),
		"inventory": inventory,
		"latest_event": _reducer.activity_for(entity_id),
		"recipe_id": str(fields.get("recipe_id", "")),
		"structure_id": str(fields.get("structure_id", "")),
		"resource_id": str(fields.get("resource_id", "")),
		"item_id": str(fields.get("item_id", "")),
		"structure": structure_snapshot,
		"measures": agent.measures,
	})


func _item_ground(event: Variant) -> Vector2:
	var type_name := str(event.type)
	if type_name != "AGENT_TOOK_ITEM" and type_name != "AGENT_DROPPED_ITEM":
		return Vector2.ZERO
	var location_id := ""
	if type_name == "AGENT_TOOK_ITEM":
		location_id = _item_location(event.item_id)
		if location_id == "" and event.origin_location_id != null:
			location_id = str(event.origin_location_id)
	elif event.destination_location_id != null:
		location_id = str(event.destination_location_id)
	elif event.origin_location_id != null:
		location_id = str(event.origin_location_id)
	if location_id == "":
		return Vector2.ZERO
	var item_id := "" if event.item_id == null else str(event.item_id)
	return _objects.ground_point(location_id, item_id)


func _item_location(item_id: Variant) -> String:
	if item_id == null or _world_state == null:
		return ""
	for item in _world_state.items:
		if str(item.item_id) == str(item_id) and item.location_id != null:
			return str(item.location_id)
	return ""


func _centroid() -> Vector2:
	if _centers.is_empty():
		return Vector2.ZERO
	var total := Vector2.ZERO
	for location_id in _centers.keys():
		total += _centers[location_id]
	return total / float(_centers.size())
