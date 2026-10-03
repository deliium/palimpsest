extends RefCounted

## Presentation-only safety checks for V2 researcher overlays.

const Effects := preload("res://scripts/view/effects_layer.gd")
const MetricOverlay := preload("res://scripts/view/metric_overlay.gd")
const NarrativeOverlay := preload("res://scripts/view/narrative_overlay.gd")
const CommFlows := preload("res://scripts/view/communication_flow_overlay.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")
const Fixture := preload("res://scripts/net/fixture_player.gd")
const SessionScript := preload("res://scripts/net/session.gd")


func run() -> Array:
	var failures: Array = []
	_assert_research_speech_gate(failures)
	_assert_analytical_badge(failures)
	_assert_narrative_hops_not_from_aggregate(failures)
	_assert_metric_catalog_miss(failures)
	_assert_v2_fixture_pack(failures)
	_assert_comm_flows_objective(failures)
	_assert_coalesce_budget(failures)
	return failures


func _assert_research_speech_gate(failures: Array) -> void:
	var effects := Effects.new()
	effects.set_strategy_audit({
		"layer": "research_strategy_audit",
		"entries": [{"event_id": "evt-agent-talked", "category": "deliberate_deception"}],
	})
	effects.set_research_speech_enabled(false)
	var agents := Node2D.new()
	agents.set_script(load("res://scripts/view/agent_layer.gd"))
	# Minimal stub: token_position via meta helper if layer needs world.
	# Use a lightweight stand-in that implements token_position.
	var stub := _AgentStub.new()
	effects._show_bubble(stub, "body-ada", "AGENT_TALKED body-bo", 2.0, "AGENT_TALKED", "evt-agent-talked")
	if effects._bubbles.is_empty():
		failures.append("ordinary speech should still create a bubble")
	else:
		var bubble: Dictionary = effects._bubbles[0]
		if str(bubble.get("research_category", "")) != "":
			failures.append("ordinary view must not attach deception from loaded audit")
		if "deliberate" in str(bubble.get("text", "")).to_lower():
			failures.append("ordinary bubble text must not name deception")
	effects.set_research_speech_enabled(true)
	effects._bubbles.clear()
	effects._show_bubble(stub, "body-ada", "AGENT_TALKED body-bo", 2.0, "AGENT_TALKED", "evt-agent-talked")
	if effects._bubbles.is_empty() or str(effects._bubbles[0].get("research_category", "")) != "deliberate_deception":
		failures.append("research mode should expose per-event audit category")
	effects.free()
	stub.free()


func _assert_analytical_badge(failures: Array) -> void:
	var overlay := MetricOverlay.new()
	overlay.overlay_kind = "emergent_group_formation"
	overlay.set_centers({"loc-1": Vector2(10, 10)})
	overlay.apply_payload({
		"values": {"location_ids": ["loc-1"]},
	})
	overlay.set_enabled(true)
	if overlay.get_child_count() != 1:
		failures.append("group overlay should paint one analytical marker")
	else:
		var marker := overlay.get_child(0)
		if str(marker.get_meta("evidence_class")) != EvidenceClass.ANALYTICAL:
			failures.append("group overlay marker must carry ANALYTICAL evidence class")
		if not str(marker.get_meta("copy")).begins_with("ANALYTICAL"):
			failures.append("group overlay copy must not look like objective ownership")
		if str(marker.get_meta("style")) != "dashed":
			failures.append("analytical markers must use non-solid style")
	overlay.free()


func _assert_narrative_hops_not_from_aggregate(failures: Array) -> void:
	var overlay := NarrativeOverlay.new()
	overlay.set_enabled(true)
	# Aggregate lineage-shaped document must not invent hops.
	overlay.apply_payload({
		"layer": "research_analytics",
		"values": {"persistence_rate": 0.9, "spread_rate": 0.4},
	})
	if overlay.get_child_count() != 0:
		failures.append("narrative hops must ignore aggregate lineage documents")
	overlay.apply_payload({
		"layer": "subjective_narrative_hops",
		"variants": [{
			"variant_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
			"carrier_agent_ids": ["ada", "bo"],
			"location_ids": ["loc-1"],
			"source_event_id": "evt-source",
			"last_communication_id": "evt-agent-talked",
		}],
	})
	overlay.set_agent_points({"ada": Vector2(1, 1), "bo": Vector2(2, 2)})
	overlay.set_centers({"loc-1": Vector2(3, 3)})
	overlay.select_variant("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	if overlay.get_child_count() < 2:
		failures.append("ledger hops should highlight carriers from SUBJECTIVE projection")
	var opaque: Array = overlay.selected_opaque_event_ids()
	if opaque.size() != 2 or not opaque.has("evt-source") or not opaque.has("evt-agent-talked"):
		failures.append("selected variant should expose opaque event ids for log focus")
	overlay.free()


func _assert_metric_catalog_miss(failures: Array) -> void:
	var missing := SessionScript.resolve_metric_set_id({"items": []}, "emergent_group_formation")
	if missing != "":
		failures.append("empty catalog must not invent a metric_set_id")


func _assert_v2_fixture_pack(failures: Array) -> void:
	var result: Dictionary = Fixture.playback_result(8.0, null, Fixture.V2_PATH)
	if str(result.get("pack", "")) != "v2_mechanics":
		failures.append("v2 fixture pack id missing")
	var types: Array = result.get("types", [])
	for needed in [
		"RESOURCE_HARVESTED",
		"STRUCTURE_BUILT",
		"ITEM_STORED",
		"AGENT_TALKED",
	]:
		if not types.has(needed):
			failures.append("v2 fixture missing type %s" % needed)
	var overlays: Variant = result.get("overlays", {})
	if typeof(overlays) != TYPE_DICTIONARY:
		failures.append("v2 fixture should include overlay stubs")
		return
	if not overlays.has("metric_catalog_miss") or not overlays.has("narrative_hops"):
		failures.append("v2 fixture overlay stubs incomplete")
	if not overlays.has("strategy_audit"):
		failures.append("v2 fixture should stub strategy audit")


func _assert_comm_flows_objective(failures: Array) -> void:
	var flows := CommFlows.new()
	flows.set_agent_points({"body-ada": Vector2(0, 0), "body-bo": Vector2(10, 0)})
	flows.record_delivery("body-ada", "body-bo", "AGENT_TALKED")
	if flows._edges.size() != 0:
		failures.append("disabled communication flows must not record edges")
	flows.set_enabled(true)
	flows.record_delivery("body-ada", "body-bo", "AGENT_TALKED")
	if flows._edges.size() != 1:
		failures.append("enabled communication flows should record OBJECTIVE delivery edges")
	flows.free()


func _assert_coalesce_budget(failures: Array) -> void:
	var effects := Effects.new()
	var stub := _AgentStub.new()
	var locations := _LocationStub.new()
	var cmd := {
		"action": "harvest",
		"type": "RESOURCE_HARVESTED",
		"event_id": "e1",
		"entity_id": "body-ada",
		"origin": "loc-camp",
		"location_id": "loc-camp",
		"skip": false,
		"duration": 0.3,
	}
	effects.play(cmd, stub, locations)
	effects.play(cmd, stub, locations)
	if effects.effects_coalesced < 1:
		failures.append("trivial same-entity activity should coalesce")
	for i in range(12):
		effects._show_bubble(stub, "body-ada", "AGENT_TALKED body-bo", 2.0, "AGENT_TALKED", "e%s" % i)
	if effects.speech_dropped < 1:
		failures.append("speech bubble cap should drop oldest bubbles")
	effects.free()
	stub.free()
	locations.free()


class _AgentStub extends Node2D:
	func token_position(_entity_id: String) -> Vector2:
		return Vector2(4, 4)

	func set_activity(_entity_id: String, _type_name: String) -> void:
		pass

	func set_dead(_entity_id: String) -> void:
		pass

	func slot_for(_entity_id: String) -> Vector2:
		return Vector2(4, 4)

	func move_token(
		_entity_id: String,
		_destination: Vector2,
		_duration: float,
		_skip: bool,
		_speed: float,
		_origin: String,
		_destination_id: String,
		_path: PackedVector2Array,
	) -> void:
		pass

	func active_motions() -> int:
		return 0


class _LocationStub extends Node2D:
	func zone_center(_location_id: String) -> Vector2:
		return Vector2(8, 8)
