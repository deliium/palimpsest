extends PanelContainer

const ObserverLog := preload("res://scripts/log.gd")

@onready var _body: Label = $Margin/Body
@onready var _measures: Label = $Margin/Measures


func _ready() -> void:
	visible = false


func show_agent(snapshot: Dictionary) -> void:
	visible = true
	var entity_id := str(snapshot.get("entity_id", ""))
	var inventory: Array = snapshot.get("inventory", [])
	var inventory_text := "(empty)" if inventory.is_empty() else ", ".join(inventory)
	var extras := _optional_ids(snapshot)
	var follow := "off"
	if bool(snapshot.get("follow", false)):
		follow = "on"
	_body.text = (
		"agent_id %s\nentity_id %s\nlocation %s\nlife_status %s\ninventory %s\n"
		+ "latest %s\nfollow %s%s"
	) % [
		str(snapshot.get("agent_id", "")),
		entity_id,
		str(snapshot.get("location_name", "")),
		str(snapshot.get("life_status", "")),
		inventory_text,
		str(snapshot.get("latest_event", "")),
		follow,
		extras,
	]
	var measures: Variant = snapshot.get("measures", null)
	if measures == null:
		_measures.visible = false
		_measures.text = ""
		ObserverLog.debug(
			"inspector",
			"measures_hidden entity_id=%s reason_code=measures_absent" % entity_id,
		)
	else:
		_measures.visible = true
		_measures.text = "health %s\nhunger %s\nthirst %s\nfatigue %s\ntemperature %s" % [
			measures.health, measures.hunger, measures.thirst, measures.fatigue, measures.temperature,
		]
	ObserverLog.debug("inspector", "opened entity_id=%s" % entity_id)


func _optional_ids(snapshot: Dictionary) -> String:
	var lines: Array[String] = []
	for key in ["recipe_id", "structure_id", "resource_id", "item_id"]:
		var value := str(snapshot.get(key, ""))
		if value != "":
			lines.append("%s %s" % [key, value])
	var structure: Variant = snapshot.get("structure", null)
	if typeof(structure) == TYPE_DICTIONARY:
		lines.append(
			"structure %s kind=%s integrity=%s stored=%s" % [
				str(structure.get("structure_id", "")),
				str(structure.get("kind", "")),
				str(structure.get("integrity", "")),
				str(structure.get("stored_quantity", "")),
			]
		)
	if lines.is_empty():
		return ""
	return "\n" + "\n".join(lines)


func clear_agent() -> void:
	visible = false
	if _body != null:
		_body.text = ""
	if _measures != null:
		_measures.text = ""
		_measures.visible = false
