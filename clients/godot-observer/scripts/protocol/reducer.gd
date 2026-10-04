extends RefCounted
class_name ObserverReducer

const MOVE_TYPES: Array[String] = ["AGENT_MOVED", "AGENT_FLED"]
const TARGET_BODY: Array[String] = ["AGENT_DIED", "NEEDS_APPLIED", "EXPOSURE_APPLIED"]

var activity := {}
var _event_fields := {}


func adopt_frame(frame: Variant) -> Dictionary:
	return {"world": frame.world, "animations": []}


func clear() -> void:
	activity = {}
	_event_fields = {}


func apply_event(world: Variant, event: Variant) -> Dictionary:
	var body: Variant = event.affected_entity_id()
	var agent = _agent(world, body)
	var origin := "" if agent == null else str(agent.location_id)
	var destination := "" if event.destination_location_id == null else str(event.destination_location_id)
	var moved := false
	if event.known and event.type in MOVE_TYPES and destination != "" and agent != null:
		agent.location_id = destination
		moved = true
	if event.known and event.type == "AGENT_DIED" and agent != null:
		agent.life_status = "dead"
	if event.known and body != null:
		activity[str(body)] = str(event.type)
		_event_fields[str(body)] = {
			"recipe_id": "" if event.recipe_id == null else str(event.recipe_id),
			"structure_id": "" if event.structure_id == null else str(event.structure_id),
			"resource_id": "" if event.resource_id == null else str(event.resource_id),
			"item_id": "" if event.item_id == null else str(event.item_id),
		}
	_move_item(world, event, agent)
	return {
		"known": bool(event.known),
		"type": str(event.type),
		"event_id": str(event.event_id),
		"entity_id": "" if body == null else str(body),
		"origin": origin,
		"destination": destination,
		"moved": moved,
		"dead": event.known and event.type == "AGENT_DIED",
		"activity": "" if body == null else str(activity.get(str(body), "")),
	}


func activity_for(entity_id: String) -> String:
	return str(activity.get(entity_id, ""))


func event_fields_for(entity_id: String) -> Dictionary:
	var fields: Variant = _event_fields.get(entity_id, {})
	if typeof(fields) != TYPE_DICTIONARY:
		return {}
	return fields


func _agent(world: Variant, entity_id: Variant) -> Variant:
	if entity_id == null or world == null:
		return null
	for agent in world.agents:
		if str(agent.entity_id) == str(entity_id):
			return agent
	return null


func _move_item(world: Variant, event: Variant, actor: Variant) -> void:
	if not event.known or event.item_id == null or world == null:
		return
	var item = null
	for candidate in world.items:
		if str(candidate.item_id) == str(event.item_id):
			item = candidate
			break
	if item == null:
		return
	if event.type == "AGENT_TOOK_ITEM" and event.actor_id != null:
		item.holder_id = str(event.actor_id)
		item.location_id = null
	elif event.type == "AGENT_DROPPED_ITEM":
		item.holder_id = null
		if event.destination_location_id != null:
			item.location_id = str(event.destination_location_id)
		elif actor != null:
			item.location_id = str(actor.location_id)
	elif event.type == "AGENT_GAVE_ITEM" and event.target_id != null:
		item.holder_id = str(event.target_id)
		item.location_id = null
	elif event.type == "AGENT_ATE_ITEM" and actor != null:
		item.holder_id = null
		item.location_id = null
		var kept: Array[String] = []
		for item_id in actor.inventory_ids:
			if str(item_id) != str(event.item_id):
				kept.append(str(item_id))
		actor.inventory_ids = kept
