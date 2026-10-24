extends RefCounted

const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")
const TokenScript := preload("res://scripts/view/agent_token.gd")
const OverlayScript := preload("res://scripts/view/generational_overlay.gd")
const Demographics := preload("res://scripts/protocol/demographics.gd")
const BASE := "res://fixtures/protocol/generational/"


class AgentStub:
	extends RefCounted
	var entity_id: String = "body-founder"
	var agent_id: Variant = "agent-founder"
	var life_status: String = "alive"
	var inventory_ids: Array = []
	var presentation: Variant = null


func run() -> Array:
	var failures: Array = []
	_expect(failures, _evidence_registry(), "evidence registry")
	_expect(failures, _token_badges(), "token badges")
	_expect(failures, _care_overlay(), "care overlay")
	return failures


func _evidence_registry() -> String:
	for kind in ["population", "generation", "cohort", "age_stage", "kinship", "caregiving"]:
		if EvidenceClass.for_overlay(kind) != EvidenceClass.OBJECTIVE:
			return "%s is not objective" % kind
	if EvidenceClass.for_overlay("mentorship_subjective") != EvidenceClass.SUBJECTIVE:
		return "subjective mentorship mislabeled"
	if EvidenceClass.for_overlay("mentorship_analytical") != EvidenceClass.ANALYTICAL:
		return "analytical mentorship mislabeled"
	if EvidenceClass.from_wire("objective") != EvidenceClass.OBJECTIVE:
		return "objective wire mapping"
	if EvidenceClass.from_wire("subjective") != EvidenceClass.SUBJECTIVE:
		return "subjective wire mapping"
	if EvidenceClass.from_wire("analytical") != EvidenceClass.ANALYTICAL:
		return "analytical wire mapping"
	if EvidenceClass.from_wire("bogus") != "":
		return "unknown wire class accepted"
	return ""


func _token_badges() -> String:
	var token: Node2D = TokenScript.new()
	var agent := AgentStub.new()
	token.setup(agent, "founder")
	token.position = Vector2(40, 50)
	token.set_demographic_badge("adult g1")
	if token.demographic_badge != "adult g1":
		return "stage/generation badge missing"
	if token.position != Vector2(40, 50):
		return "badge moved the location-based token"
	token.set_selected(true)
	token.set_dead(true)
	if not token.selected or not token.dead:
		return "badge replaced identity/death/selection state"
	token.free()
	return ""


func _care_overlay() -> String:
	var overlay: Node2D = OverlayScript.new()
	overlay.set_enabled(true)
	overlay.set_positions({"body-a": Vector2(10, 10), "body-b": Vector2(30, 30)})
	var events: Array = [
		{"event_id": "e1", "type": "AGENT_FED", "actor_id": "body-a", "target_id": "body-b", "tick": 3, "origin_location_id": "loc-1"},
		{"event_id": "e1", "type": "AGENT_FED", "actor_id": "body-a", "target_id": "body-b", "tick": 3, "origin_location_id": "loc-1"},
		{"event_id": "e2", "type": "AGENT_TRANSPORTED", "actor_id": "body-b", "target_id": "body-c", "tick": 4, "origin_location_id": "loc-1"},
	]
	overlay.apply_care_events(events)
	if overlay.care_count() != 2:
		return "care events were not deduplicated"
	overlay.apply_arrival_events([
		{"event_id": "a1", "type": "AGENT_CREATED", "target_id": "body-b", "actor_id": null, "tick": 2},
		{"event_id": "a2", "type": "AGENT_INITIALIZED", "target_id": "body-b", "actor_id": null, "tick": 2},
	])
	if overlay.arrival_count() != 1:
		return "arrival siblings were not deduplicated per body/tick"
	overlay.set_links([{"from": "body-a", "to": "body-b", "evidence": "objective"}])
	if overlay.link_count() != 1:
		return "kinship link missing"
	overlay.clear()
	if overlay.care_count() != 0 or overlay.link_count() != 0 or overlay.arrival_count() != 0:
		return "care/links/arrivals did not clear"
	overlay.set_enabled(false)
	overlay.apply_care_events(events)
	if overlay.care_count() != 0:
		return "disabled care overlay rendered events"
	overlay.free()
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
