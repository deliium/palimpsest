extends PanelContainer

const ObserverLog := preload("res://scripts/log.gd")

@onready var _body: Label = $Margin/Body
@onready var _measures: Label = $Margin/Measures
@onready var _demographics: Label = $Margin/Demographics


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


func show_demographics(row: Variant) -> void:
	if _demographics == null:
		return
	if row == null:
		_demographics.text = ""
		return
	_demographics.text = "generation %s | cohort %s | stage %s | %s | age %s" % [
		row.generation_index,
		row.cohort_id,
		row.stage,
		row.life_status,
		"n/a" if row.age_ticks == null else str(row.age_ticks),
	]


func show_civilization(summary: Dictionary) -> void:
	visible = true
	var lines: Array[String] = []
	lines.append("civilization %s" % str(summary.get("layer", "")))
	lines.append("row %s" % str(summary.get("row_id", "")))
	lines.append("evidence %s" % str(summary.get("evidence_class", "")))
	var values: Dictionary = summary.get("summary", {})
	var keys: Array = values.keys()
	keys.sort()
	for key in keys:
		var value: Variant = values[key]
		if value == null:
			lines.append("%s unknown" % str(key))
		elif typeof(value) in [TYPE_STRING, TYPE_INT, TYPE_FLOAT, TYPE_BOOL]:
			lines.append("%s %s" % [str(key), str(value)])
	for ref in summary.get("source_refs", []):
		lines.append(
			"source %s %s tick=%s" % [
				str(ref.get("source_kind", "")),
				str(ref.get("source_id", "")),
				str(ref.get("tick", "")),
			]
		)
	for ref in summary.get("lineage_refs", []):
		lines.append("lineage source %s tick=%s" % [str(ref.get("source_id", "")), str(ref.get("tick", ""))])
	_body.text = "\n".join(lines)
	if _measures != null:
		_measures.text = ""
		_measures.visible = false
	if _demographics != null:
		_demographics.text = ""
	ObserverLog.debug("inspector", "civilization_opened layer=%s" % str(summary.get("layer", "")))


func clear_agent() -> void:
	visible = false
	if _body != null:
		_body.text = ""
	if _measures != null:
		_measures.text = ""
		_measures.visible = false
	if _demographics != null:
		_demographics.text = ""
