extends RefCounted


static func endpoints(type_name: String, actor: Vector2, target: Vector2, ground: Vector2) -> Dictionary:
	if type_name == "AGENT_TOOK_ITEM":
		return {"from": ground, "to": actor}
	if type_name == "AGENT_DROPPED_ITEM":
		return {"from": actor, "to": ground}
	if type_name == "AGENT_GAVE_ITEM":
		return {"from": actor, "to": target}
	return {"from": actor, "to": actor}
