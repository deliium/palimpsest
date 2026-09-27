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
	_body.text = "agent_id %s\nentity_id %s\nlocation %s\nlife_status %s\ninventory %s\nlatest %s" % [
		str(snapshot.get("agent_id", "")),
		entity_id,
		str(snapshot.get("location_name", "")),
		str(snapshot.get("life_status", "")),
		inventory_text,
		str(snapshot.get("latest_event", "")),
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


func clear_agent() -> void:
	visible = false
	if _body != null:
		_body.text = ""
	if _measures != null:
		_measures.text = ""
		_measures.visible = false
