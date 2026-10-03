extends RefCounted
class_name ObserverEventRouter

const _SPEECH: Array[String] = ["AGENT_TALKED", "AGENT_ASKED", "AGENT_TOLD"]


static func route(event: Variant, policy: Dictionary, logical: Dictionary) -> Dictionary:
	var action := "activity"
	if not bool(event.known):
		action = "unknown"
	else:
		match str(event.type):
			"AGENT_MOVED":
				action = "move"
			"AGENT_FLED":
				action = "move" if str(logical.get("destination", "")) != "" else "activity"
			"AGENT_SEARCHED":
				action = "search"
			"RESOURCE_REGENERATED":
				action = "resource"
			"AGENT_TOOK_ITEM", "AGENT_DROPPED_ITEM", "AGENT_GAVE_ITEM":
				action = "item"
			"AGENT_ATE_ITEM":
				action = "consume"
			"AGENT_DRANK":
				action = "drink"
			"AGENT_SLEPT":
				action = "rest"
			"AGENT_ATTACKED":
				action = "strike"
			"AGENT_HELPED":
				action = "link"
			"AGENT_DIED":
				action = "died"
			"AGENT_TALKED", "AGENT_ASKED", "AGENT_TOLD":
				action = "speech"
			"WEATHER_CHANGED":
				action = "weather"
			"SEASON_CHANGED":
				action = "season"
			"TEMPERATURE_BAND_CHANGED":
				action = "temperature"
			"RESOURCE_NODE_DEPLETED", "RESOURCE_NODE_RECOVERED":
				action = "resource"
			"ENVIRONMENTAL_HAZARD_STARTED", "ENVIRONMENTAL_HAZARD_ENDED":
				action = "hazard"
			"ARTIFACT_CREATED", "ARTIFACT_MODIFIED", "ARTIFACT_MOVED", "ARTIFACT_DESTROYED":
				action = "artifact"
			_:
				action = "activity"
	var other := ""
	if str(event.type) in _SPEECH or action in ["strike", "link", "item"]:
		other = "" if event.target_id == null else str(event.target_id)
	return {
		"action": action,
		"skip": bool(policy.get("skip", false)),
		"duration": float(policy.get("duration", 0.0)),
		"speech_duration": float(policy.get("speech_duration", 0.0)),
		"speed": float(policy.get("speed", 1.0)),
		"type": str(event.type),
		"event_id": str(event.event_id),
		"entity_id": str(logical.get("entity_id", "")),
		"origin": str(logical.get("origin", "")),
		"destination": str(logical.get("destination", "")),
		"other_id": other,
		"item_id": "" if event.item_id == null else str(event.item_id),
		"location_id": "" if event.origin_location_id == null else str(event.origin_location_id),
		"moves_location": action == "move" and bool(logical.get("moved", false)),
	}
