extends RefCounted
class_name ObserverIdentity


static func label_for(agent: Variant) -> String:
	if agent.agent_id != null and str(agent.agent_id) != "":
		return str(agent.agent_id)
	return str(agent.entity_id)


static func color_key(agent: Variant) -> String:
	return label_for(agent)


static func color_for(agent: Variant) -> Color:
	var hash_value := _hash(color_key(agent))
	return Color.from_hsv(float(hash_value % 360) / 360.0, 0.62, 0.92)


static func is_dead(agent: Variant) -> bool:
	return str(agent.life_status) == "dead"


static func _hash(text: String) -> int:
	var hash_value := 2166136261
	for index in text.length():
		hash_value = hash_value ^ text.unicode_at(index)
		hash_value = (hash_value * 16777619) & 0x7fffffff
	return hash_value
