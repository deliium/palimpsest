extends PanelContainer

const ObserverLog := preload("res://scripts/log.gd")

var lines: Array = []

@onready var _items: ItemList = $Items


func append_event(event: Variant) -> void:
	lines.append({
		"tick": int(event.tick),
		"sequence": int(event.sequence),
		"type": str(event.type),
	})
	ObserverLog.debug(
		"log_view",
		"line_appended tick=%s sequence=%s type=%s" % [int(event.tick), int(event.sequence), str(event.type)],
	)
	lines.sort_custom(func(left: Dictionary, right: Dictionary) -> bool:
		if int(left["tick"]) == int(right["tick"]):
			return int(left["sequence"]) < int(right["sequence"])
		return int(left["tick"]) < int(right["tick"])
	)
	_render()


func contains_type(type_name: String) -> bool:
	for line in lines:
		if str(line["type"]) == type_name:
			return true
	return false


func _render() -> void:
	if _items == null:
		return
	_items.clear()
	for line in lines:
		_items.add_item("%s:%s %s" % [line["tick"], line["sequence"], line["type"]])
