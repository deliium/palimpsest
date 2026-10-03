extends HBoxContainer

## SUBJECTIVE narrative variant picker. Populated from ledger hops only.

signal variant_selected(variant_id: String)

const ObserverLog := preload("res://scripts/log.gd")
const EvidenceClass := preload("res://scripts/presentation/evidence_class.gd")

var _ids: Array[String] = []
var _updating := false

@onready var _label: Label = $Label
@onready var _options: OptionButton = $Variants


func _ready() -> void:
	_label.text = "Narrative [%s]" % EvidenceClass.LABEL_SUBJECTIVE
	_options.item_selected.connect(_on_item_selected)
	clear_variants()


func clear_variants() -> void:
	_updating = true
	_ids.clear()
	_options.clear()
	_options.add_item("(none)")
	_options.disabled = true
	_updating = false


func set_variants(ids: Array) -> void:
	_updating = true
	_ids.clear()
	_options.clear()
	for item in ids:
		var variant_id := str(item)
		if variant_id == "":
			continue
		_ids.append(variant_id)
		# Short opaque id for display — never content tokens.
		var short_id := variant_id
		if short_id.length() > 12:
			short_id = short_id.substr(0, 12)
		_options.add_item(short_id)
	_options.disabled = _ids.is_empty()
	if _ids.is_empty():
		_options.add_item("(none)")
		ObserverLog.warn("ui", "narrative_overlay_unavailable reason_code=empty_selector")
	else:
		_options.select(0)
		ObserverLog.debug("ui", "narrative_selector_populated count=%s" % _ids.size())
	_updating = false
	if not _ids.is_empty():
		variant_selected.emit(_ids[0])


func selected_variant_id() -> String:
	var index := _options.selected
	if index < 0 or index >= _ids.size():
		return ""
	return _ids[index]


func _on_item_selected(index: int) -> void:
	if _updating:
		return
	if index < 0 or index >= _ids.size():
		return
	var variant_id := _ids[index]
	ObserverLog.info("ui", "narrative_selected id=%s" % variant_id)
	variant_selected.emit(variant_id)
