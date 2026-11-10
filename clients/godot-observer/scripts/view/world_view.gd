extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
const Playback := preload("res://scripts/protocol/playback.gd")
const ReducerScript := preload("res://scripts/protocol/reducer.gd")
const Router := preload("res://scripts/protocol/event_router.gd")
const CivilizationPlan := preload("res://scripts/presentation/civilization_plan.gd")
const BorderOverlay := preload("res://scripts/view/border_overlay.gd")
const MigrationOverlay := preload("res://scripts/view/migration_overlay.gd")
const InfrastructureOverlay := preload("res://scripts/view/infrastructure_overlay.gd")
const TradeOverlay := preload("res://scripts/view/trade_overlay.gd")

var playback_speed := 1.0

var _world_state: Variant = null
var _centers := {}
var _reducer = ReducerScript.new()
var _civilization_states := {}
var _civilization_cursor := {}
var _civilization_warning := ""
var _civilization_anchor_warning := ""
var _civilization_plan: Dictionary = {}
var presentation_detail := "full"

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
@onready var _generational: Node2D = get_node_or_null("GenerationalOverlay")
@onready var _civilization: Node2D = get_node_or_null("CivilizationFacilities")
@onready var _civilization_flows: Node2D = get_node_or_null("CivilizationFlows")
@onready var _civilization_beliefs: Node2D = get_node_or_null("CivilizationBeliefs")
const BORDER_OVERLAY_KINDS := [
	"border_physical",
	"border_claims",
	"border_agreements",
	"border_patterns",
]
const MIGRATION_OVERLAY_KINDS := [
	"migration_route",
	"migration_cause",
	"migration_wave",
	"migration_integration",
]
const INFRASTRUCTURE_OVERLAY_KINDS := [
	"infrastructure_node",
	"infrastructure_edge",
	"infrastructure_damaged",
	"infrastructure_destroyed",
]
const TRADE_OVERLAY_KINDS := [
	"trade_corridors",
	"trade_major_locations",
	"trade_cross_society",
	"trade_coverage",
]
var _borders: Dictionary = {}
var _migrations: Dictionary = {}
var _infrastructure: Dictionary = {}
var _trade: Dictionary = {}
var trade_summary: Variant = null

signal inspect_requested(snapshot: Dictionary)
signal inspect_cleared
signal location_selected(location_id: String)
signal civilization_inspect_requested(summary: Dictionary)

func _ready() -> void:
	for kind in BORDER_OVERLAY_KINDS:
		var node_name := "BorderOverlay_%s" % kind
		var overlay: Node2D = get_node_or_null(node_name)
		if overlay == null:
			overlay = BorderOverlay.new()
			overlay.name = node_name
			add_child(overlay)
		_borders[kind] = overlay
	for kind in MIGRATION_OVERLAY_KINDS:
		var migration_name := "MigrationOverlay_%s" % kind
		var migration: Node2D = get_node_or_null(migration_name)
		if migration == null:
			migration = MigrationOverlay.new()
			migration.name = migration_name
			add_child(migration)
		_migrations[kind] = migration
	for kind in INFRASTRUCTURE_OVERLAY_KINDS:
		var infra_name := "InfrastructureOverlay_%s" % kind
		var infra: Node2D = get_node_or_null(infra_name)
		if infra == null:
			infra = InfrastructureOverlay.new()
			infra.name = infra_name
			add_child(infra)
		_infrastructure[kind] = infra
	for kind in TRADE_OVERLAY_KINDS:
		var trade_name := "TradeOverlay_%s" % kind
		var trade: Node2D = get_node_or_null(trade_name)
		if trade == null:
			trade = TradeOverlay.new()
			trade.name = trade_name
			add_child(trade)
		_trade[kind] = trade
	_agents.agent_selected.connect(_on_agent_selected)
	_agents.selection_cleared.connect(func() -> void: inspect_cleared.emit())
	if _locations != null and _locations.has_signal("location_selected"):
		_locations.location_selected.connect(func(location_id: String) -> void:
			location_selected.emit(location_id)
		)
	if _civilization != null and _civilization.has_signal("row_inspect_requested"):
		_civilization.row_inspect_requested.connect(func(summary: Dictionary) -> void:
			civilization_inspect_requested.emit(summary)
		)
	if _civilization_flows != null and _civilization_flows.has_signal("row_inspect_requested"):
		_civilization_flows.row_inspect_requested.connect(func(summary: Dictionary) -> void:
			civilization_inspect_requested.emit(summary)
		)
	if _civilization_beliefs != null and _civilization_beliefs.has_signal("row_inspect_requested"):
		_civilization_beliefs.row_inspect_requested.connect(func(summary: Dictionary) -> void:
			civilization_inspect_requested.emit(summary)
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
	for overlay in _borders.values():
		overlay.set_centers(_centers)
	for overlay in _migrations.values():
		overlay.set_centers(_centers)
	for overlay in _infrastructure.values():
		overlay.set_centers(_centers)
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
	if _generational != null:
		_generational.set_positions(agent_points)
	_rebuild_civilization()

func _border_for(kind: String) -> Node2D:
	if _borders.has(kind):
		return _borders[kind]
	return _borders.get("border_physical", null)

func set_border_overlay(data: Variant, enabled_value: bool = true, kind: String = "") -> void:
	var overlay := _border_for(kind)
	if overlay != null:
		overlay.set_enabled(enabled_value)
		overlay.apply_payload(data, kind)

func clear_border_overlay(kind: String = "") -> void:
	if kind == "":
		for overlay in _borders.values():
			overlay.clear()
			overlay.set_enabled(false)
		return
	var overlay := _border_for(kind)
	if overlay != null:
		overlay.clear()
		overlay.set_enabled(false)

func set_border_overlay_enabled(enabled_value: bool, kind: String = "") -> void:
	var overlay := _border_for(kind)
	if overlay != null:
		overlay.set_enabled(enabled_value)
		if not enabled_value:
			overlay.clear()
		elif kind != "":
			overlay.apply_payload(null, kind)

func _migration_for(kind: String) -> Node2D:
	if _migrations.has(kind):
		return _migrations[kind]
	return _migrations.get("migration_route", null)

func set_migration_overlay(data: Variant, enabled_value: bool = true, kind: String = "") -> void:
	var overlay := _migration_for(kind)
	if overlay != null:
		overlay.set_enabled(enabled_value)
		overlay.apply_payload(data, kind)

func clear_migration_overlay(kind: String = "") -> void:
	if kind == "":
		for overlay in _migrations.values():
			overlay.clear()
			overlay.set_enabled(false)
		return
	var overlay := _migration_for(kind)
	if overlay != null:
		overlay.clear()
		overlay.set_enabled(false)

func set_migration_overlay_enabled(enabled_value: bool, kind: String = "") -> void:
	var overlay := _migration_for(kind)
	if overlay != null:
		overlay.set_enabled(enabled_value)
		if not enabled_value:
			overlay.clear()
		elif kind != "":
			overlay.apply_payload(null, kind)

func _infrastructure_for(kind: String) -> Node2D:
	if _infrastructure.has(kind):
		return _infrastructure[kind]
	return _infrastructure.get("infrastructure_node", null)

func set_infrastructure_overlay(data: Variant, enabled_value: bool = true, kind: String = "") -> void:
	var overlay := _infrastructure_for(kind)
	if overlay != null:
		overlay.set_enabled(enabled_value)
		overlay.apply_payload(data, kind)

func clear_infrastructure_overlay(kind: String = "") -> void:
	if kind == "":
		for overlay in _infrastructure.values():
			overlay.clear()
			overlay.set_enabled(false)
		return
	var overlay := _infrastructure_for(kind)
	if overlay != null:
		overlay.clear()
		overlay.set_enabled(false)

func set_infrastructure_overlay_enabled(enabled_value: bool, kind: String = "") -> void:
	var overlay := _infrastructure_for(kind)
	if overlay != null:
		overlay.set_enabled(enabled_value)
		if not enabled_value:
			overlay.clear()
		elif kind != "":
			overlay.apply_payload(null, kind)

func _trade_for(kind: String) -> Node2D:
	if _trade.has(kind):
		return _trade[kind]
	return _trade.get("trade_corridors", null)


func set_trade_overlay(data: Variant, enabled_value: bool = true, kind: String = "") -> void:
	var overlay := _trade_for(kind)
	if overlay != null:
		overlay.set_enabled(enabled_value)
		overlay.apply_payload(data, kind)


func clear_trade_overlay(kind: String = "") -> void:
	if kind == "":
		for overlay in _trade.values():
			overlay.clear()
			overlay.set_enabled(false)
		return
	var overlay := _trade_for(kind)
	if overlay != null:
		overlay.clear()
		overlay.set_enabled(false)


func set_trade_overlay_enabled(enabled_value: bool, kind: String = "") -> void:
	var overlay := _trade_for(kind)
	if overlay != null:
		overlay.set_enabled(enabled_value)
		if not enabled_value:
			overlay.clear()


func apply_trade_summary(payload: Variant) -> void:
	trade_summary = payload


func set_trade_window_index(value: int) -> void:
	for overlay in _trade.values():
		overlay.set_window_index(value)


func trade_overlay_window() -> int:
	var overlay := _trade_for("trade_corridors")
	return -1 if overlay == null else overlay.selected_window()


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
	if _generational != null:
		_generational.clear()
		_generational.set_enabled(false)
	if _agents != null and _agents.has_method("clear_demographic_badges"):
		_agents.clear_demographic_badges()
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
	_civilization_states.clear()
	_civilization_cursor.clear()
	_civilization_plan = {}
	if _civilization != null:
		_civilization.clear_plan()
	if _civilization_flows != null:
		_civilization_flows.clear_plan()
	if _civilization_beliefs != null:
		_civilization_beliefs.clear_plan()
	inspect_cleared.emit()
	ObserverLog.debug("view", "world_cleared")

func apply_civilization_bundle(cursor: Dictionary, states: Dictionary) -> void:
	_civilization_cursor = cursor.duplicate(true)
	_civilization_states = states.duplicate(true)
	_rebuild_civilization()

func apply_civilization_plan(plan: Dictionary) -> void:
	if plan.is_empty() or not bool(plan.get("ok", false)):
		_civilization_plan = {}
		if _civilization != null:
			_civilization.clear_plan()
		if _civilization_flows != null:
			_civilization_flows.clear_plan()
		if _civilization_beliefs != null:
			_civilization_beliefs.clear_plan()
		return
	_civilization_plan = plan.duplicate(true)
	if _civilization != null:
		_civilization.apply_plan(_civilization_plan)
	if _civilization_flows != null:
		_civilization_flows.apply_plan(_civilization_plan)
	if _civilization_beliefs != null:
		_civilization_beliefs.apply_plan(_civilization_plan)

func set_presentation_detail(lod: String) -> void:
	if lod not in ["full", "reduced", "snap", "aggregate"]:
		return
	if lod == presentation_detail:
		return
	presentation_detail = lod
	if _civilization != null:
		_civilization.set_lod(lod)
	if _civilization_flows != null:
		_civilization_flows.set_lod(lod)
	if _civilization_beliefs != null:
		_civilization_beliefs.set_lod(lod)
	if _effects != null and _effects.has_method("set_lod"):
		_effects.set_lod(lod)
	if _agents != null and _agents.has_method("set_presentation_detail"):
		_agents.set_presentation_detail(lod)
	ObserverLog.debug("view", "presentation_detail lod=%s" % lod)

func presentation_lod() -> String:
	return presentation_detail

func semantic_snapshot() -> Dictionary:
	var layers := {}
	var keys: Array = _civilization_states.keys()
	keys.sort()
	var total_rows := 0
	for layer_id in keys:
		var state: Dictionary = _civilization_states[layer_id]
		var rows: Array = state.get("rows", [])
		total_rows += rows.size()
		var identities: Array = []
		for row in rows:
			identities.append(_row_identity(row))
		var publication: Variant = state.get("publication", null)
		layers[str(layer_id)] = {
			"status": str(state.get("status", "")),
			"evidence_class": str(state.get("evidence_class", "")),
			"owner_id": state.get("owner_id", null),
			"coverage": _coverage_identity(state.get("coverage", null)),
			"publication": (
				null if publication == null else {
					"publication_id": publication.get("publication_id", null),
					"digest": publication.get("digest", null),
				}
			),
			"cursor": state.get("cursor", {}),
			"row_count": rows.size(),
			"row_ids": identities,
		}
	return {
		"world": _world_semantics(),
		"cursor": _civilization_cursor.duplicate(true),
		"layers": layers,
		"counts": {"layers": layers.size(), "rows": total_rows},
	}

func semantic_digest() -> String:
	return JSON.stringify(semantic_snapshot()).sha256_text()

func _world_semantics() -> Dictionary:
	if _world_state == null:
		return {}
	var locations: Array = []
	for location in _world_items(_world_state, "locations"):
		locations.append(str(_value(location, "location_id", "")))
	locations.sort()
	var agents: Array = []
	for agent in _world_items(_world_state, "agents"):
		agents.append({
			"entity_id": str(_value(agent, "entity_id", "")),
			"agent_id": _value(agent, "agent_id", null),
			"location_id": _value(agent, "location_id", null),
			"life_status": _value(agent, "life_status", null),
		})
	agents.sort_custom(func(left: Dictionary, right: Dictionary) -> bool:
		return str(left["entity_id"]) < str(right["entity_id"])
	)
	var structures: Array = []
	for structure in _world_items(_world_state, "structures"):
		structures.append(str(_value(structure, "structure_id", "")))
	structures.sort()
	var items: Array = []
	for item in _world_items(_world_state, "items"):
		items.append(str(_value(item, "item_id", "")))
	items.sort()
	return {
		"world_id": _value(_world_state, "world_id", null),
		"tick": _value(_world_state, "tick", null),
		"revision": _value(_world_state, "revision", null),
		"locations": locations,
		"agents": agents,
		"structures": structures,
		"items": items,
	}

func _world_items(source: Variant, key: String) -> Array:
	var value: Variant = _value(source, key, [])
	if value == null or typeof(value) != TYPE_ARRAY:
		return []
	return value

func _coverage_identity(value: Variant) -> Variant:
	if value == null:
		return null
	if typeof(value) == TYPE_DICTIONARY:
		return value.duplicate(true)
	if value is Object:
		return {"state": value.get("state"), "reason": value.get("reason")}
	return null

func _row_identity(row: Variant) -> String:
	if typeof(row) == TYPE_DICTIONARY:
		var context: Variant = row.get("context", null)
		if typeof(context) == TYPE_DICTIONARY and context.get("row_id", null) != null:
			return str(context["row_id"])
		if row.get("row_id", null) != null:
			return str(row["row_id"])
	if row is Object:
		var object_context: Variant = row.get("context")
		if object_context != null:
			var object_row_id: Variant = object_context.get("row_id")
			if object_row_id != null and str(object_row_id) != "":
				return str(object_row_id)
		var direct_row_id: Variant = row.get("row_id")
		if direct_row_id != null and str(direct_row_id) != "":
			return str(direct_row_id)
	return ""

func _value(source: Variant, key: String, fallback: Variant = null) -> Variant:
	if source == null:
		return fallback
	if typeof(source) == TYPE_DICTIONARY:
		return source.get(key, fallback)
	if source is Object:
		var value: Variant = source.get(key)
		return fallback if value == null else value
	return fallback

func apply_civilization_layer(layer_id: String, state: Dictionary) -> void:
	var status := str(state.get("status", "off"))
	if status not in ["available", "partial", "empty"]:
		_civilization_states.erase(layer_id)
		_rebuild_civilization()
		return
	_civilization_states[layer_id] = state.duplicate(true)
	var cursor: Variant = state.get("cursor", null)
	if typeof(cursor) == TYPE_DICTIONARY and not cursor.is_empty():
		_civilization_cursor = cursor.duplicate(true)
	_rebuild_civilization()

func clear_civilization_layer(layer_id: String) -> void:
	if _civilization_states.erase(layer_id):
		_rebuild_civilization()

func clear_civilization_layers() -> void:
	_civilization_states.clear()
	_civilization_cursor.clear()
	_civilization_warning = ""
	_civilization_anchor_warning = ""
	if _civilization != null:
		_civilization.clear_plan()
	if _civilization_flows != null:
		_civilization_flows.clear_plan()
	if _civilization_beliefs != null:
		_civilization_beliefs.clear_plan()

func civilization_plan() -> Dictionary:
	if _civilization == null:
		return {}
	return _civilization.semantic_plan()

func _rebuild_civilization() -> void:
	if _civilization == null:
		return
	if _world_state == null or _civilization_states.is_empty() or _civilization_cursor.is_empty():
		apply_civilization_plan({})
		return
	var plan: Dictionary = CivilizationPlan.build_semantic(
		_world_state,
		_civilization_states,
		_civilization_cursor,
		_centers,
	)
	if not bool(plan.get("ok", false)):
		var reason := str(plan.get("reason_code", "invalid_plan"))
		if reason != _civilization_warning:
			_civilization_warning = reason
			ObserverLog.warn("civilization", "render_plan_rejected reason=%s" % reason)
		apply_civilization_plan({})
		return
	_civilization_warning = ""
	apply_civilization_plan(plan)
	if int(plan.get("unresolved_anchor_count", 0)) > 0:
		var anchor_key := "%s|%s" % [
			str(_civilization_cursor.get("tick", "")),
			str(_civilization_cursor.get("revision", "")),
		]
		if anchor_key != _civilization_anchor_warning:
			_civilization_anchor_warning = anchor_key
			ObserverLog.warn(
				"civilization",
				"unresolved_anchor count=%s code=anchor_unavailable" % str(
					plan.get("unresolved_anchor_count", 0)
				),
			)
	ObserverLog.debug(
		"civilization",
		"render_plan layers=%s rows=%s unplaced=%s" % [
			_civilization_states.size(),
			plan.get("rows", []).size(),
			int(plan.get("unresolved_anchor_count", 0)),
		],
	)
	var rendered_counts: Dictionary = plan.get("counts", {})
	var rendered_format := (
		"civilization_rendered digest=%s layers=%s locations=%s regions=%s routes=%s "
		+ "settlements=%s projects=%s public_acts=%s repositories=%s records=%s "
		+ "migration=%s trade=%s culture=%s technology=%s groups=%s institutions=%s "
		+ "unplaced=%s lod=%s"
	)
	ObserverLog.debug(
		"acceptance",
		rendered_format % [
			semantic_digest(),
			_civilization_states.size(),
			int(rendered_counts.get("locations", 0)),
			int(rendered_counts.get("regions", 0)),
			int(rendered_counts.get("routes", 0)),
			int(rendered_counts.get("settlements", 0)),
			int(rendered_counts.get("projects", 0)),
			int(rendered_counts.get("public_act", 0)),
			int(rendered_counts.get("repositories", 0)),
			int(rendered_counts.get("records", 0)),
			int(rendered_counts.get("migration", 0)),
			int(rendered_counts.get("trade", 0)),
			int(rendered_counts.get("culture", 0)),
			int(rendered_counts.get("technology", 0)),
			int(rendered_counts.get("social_groups", 0)),
			int(rendered_counts.get("institutions", 0)),
			int(plan.get("unresolved_anchor_count", 0)),
			presentation_detail,
		],
	)

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
	set_presentation_detail(Playback.level_of_detail(speed))

func set_playback_paused(paused: bool) -> void:
	set_presentation_detail("full" if paused else Playback.level_of_detail(playback_speed))

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
	var at_location: Variant = _objects.structure_at(str(agent.location_id))
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

func apply_demographics(model: Variant, enabled_kinds: Array = []) -> void:
	if _agents == null or model == null:
		return
	var rows: Dictionary = {}
	if model.availability == "available":
		for row in model.agents:
			var parts: Array[String] = []
			if "age_stage" in enabled_kinds:
				parts.append(str(row.stage))
			if "generation" in enabled_kinds:
				parts.append("g%s" % row.generation_index)
			if "cohort" in enabled_kinds:
				parts.append(str(row.cohort_id))
			if not parts.is_empty():
				rows[row.entity_id] = " ".join(parts)
	_agents.apply_demographic_badges(rows)
	if _generational != null:
		_generational.set_positions(_agents.capture_positions())

func apply_arrival_events(events: Array) -> void:
	if _generational == null:
		return
	_generational.set_positions(_agents.capture_positions())
	_generational.apply_arrival_events(events)

func apply_care_events(events: Array) -> void:
	if _generational == null:
		return
	_generational.set_positions(_agents.capture_positions())
	_generational.apply_care_events(events)

func set_generational_overlay_enabled(kind: String, enabled: bool) -> void:
	if _generational == null:
		return
	if kind == "caregiving" or kind == "kinship" or kind == "mentorship_subjective" or kind == "mentorship_analytical":
		_generational.set_enabled(enabled or _generational.care_count() > 0)

func apply_generational_links(links: Array) -> void:
	if _generational == null:
		return
	_generational.set_positions(_agents.capture_positions())
	_generational.set_links(links)

func generational_care_count() -> int:
	if _generational == null or not _generational.has_method("care_count"):
		return 0
	return int(_generational.care_count())

func generational_link_count() -> int:
	if _generational == null or not _generational.has_method("link_count"):
		return 0
	return int(_generational.link_count())

func clear_generational_transients() -> void:
	if _generational == null:
		return
	_generational.clear()
	_generational.set_positions(_agents.capture_positions())

func agent_entity_for(agent_id: String) -> String:
	if _world_state == null or agent_id.is_empty():
		return ""
	var found := ""
	for agent in _world_state.agents:
		var bound := "" if agent.agent_id == null else str(agent.agent_id)
		if bound == agent_id:
			if found != "" and found != str(agent.entity_id):
				return ""
			found = str(agent.entity_id)
	return found

func demographic_badges_for_test() -> Dictionary:
	var badges := {}
	for child in _agents.get_children():
		if child.has_method("set_demographic_badge"):
			badges[str(child.entity_id)] = str(child.demographic_badge)
	return badges

func highlight_selected(entity_id: String) -> void:
	if _agents != null:
		_agents.highlight(entity_id)
