extends PanelContainer

## Read-only research causal debugger panel. Renders server chain only.

const ObserverLog := preload("res://scripts/log.gd")

signal focus_requested(tick: int, sequence: int, event_id: String)
signal closed

var _body: RichTextLabel
var _close: Button
var _nodes: ItemList
var _focus_rows: Array = []
var _open := false


func _ready() -> void:
	visible = false
	_ensure_children()
	_close.pressed.connect(func() -> void:
		close_panel()
	)
	_nodes.item_activated.connect(_on_node_activated)


func _ensure_children() -> void:
	if _body != null:
		return
	var column := VBoxContainer.new()
	column.name = "Column"
	add_child(column)
	var header := HBoxContainer.new()
	column.add_child(header)
	var title := Label.new()
	title.text = "Causal debugger"
	header.add_child(title)
	_close = Button.new()
	_close.text = "Close"
	header.add_child(_close)
	_body = RichTextLabel.new()
	_body.fit_content = true
	_body.scroll_active = false
	_body.custom_minimum_size = Vector2(0, 48)
	column.add_child(_body)
	_nodes = ItemList.new()
	_nodes.custom_minimum_size = Vector2(320, 220)
	column.add_child(_nodes)


func open_payload(payload: Dictionary) -> void:
	_ensure_children()
	visible = true
	_open = true
	_focus_rows = []
	_nodes.clear()
	var availability := str(payload.get("availability", ""))
	var reason := str(payload.get("reason_code", ""))
	var address: Variant = payload.get("address", {})
	var tick := 0
	var sequence := -1
	var event_id := ""
	if typeof(address) == TYPE_DICTIONARY:
		tick = int(address.get("tick", 0))
		if address.get("sequence", null) != null:
			sequence = int(address.get("sequence"))
		event_id = str(address.get("event_id", ""))
	_body.text = "availability=%s reason=%s tick=%s sequence=%s event_id=%s" % [
		availability, reason, tick, sequence, event_id,
	]
	var nodes: Array = payload.get("nodes", [])
	for node in nodes:
		if typeof(node) != TYPE_DICTIONARY:
			continue
		var stage := str(node.get("stage_code", ""))
		var status := str(node.get("status", ""))
		var node_reason := str(node.get("reason_code", ""))
		var line := "%s [%s]" % [stage, status]
		if node_reason != "":
			line += " (%s)" % node_reason
		var command_kind := str(node.get("command_kind", ""))
		if command_kind != "":
			line += " command=%s" % command_kind
		_nodes.add_item(line)
		var focus_tick := tick
		var focus_sequence := sequence
		var focus_event := event_id
		var focuses: Array = node.get("observer_focus", [])
		if not focuses.is_empty() and typeof(focuses[0]) == TYPE_DICTIONARY:
			var focus: Dictionary = focuses[0]
			focus_tick = int(focus.get("tick", focus_tick))
			if focus.get("sequence", null) != null:
				focus_sequence = int(focus.get("sequence"))
			focus_event = str(focus.get("event_id", focus_event))
		_focus_rows.append({
			"tick": focus_tick,
			"sequence": focus_sequence,
			"event_id": focus_event,
		})
	ObserverLog.info(
		"observer.debugger",
		"debugger_opened availability=%s node_count=%s" % [availability, nodes.size()],
	)
	ObserverLog.debug(
		"observer.debugger",
		"debugger_payload_rendered node_count=%s" % nodes.size(),
	)


func show_unavailable(reason_code: String) -> void:
	_ensure_children()
	visible = true
	_open = true
	_focus_rows = []
	_nodes.clear()
	_body.text = "debugger unavailable reason_code=%s" % reason_code
	ObserverLog.warn(
		"observer.debugger",
		"debugger_unavailable reason_code=%s" % reason_code,
	)


func close_panel() -> void:
	visible = false
	_open = false
	_focus_rows = []
	if _nodes != null:
		_nodes.clear()
	if _body != null:
		_body.text = ""
	ObserverLog.info("observer.debugger", "debugger_closed")
	closed.emit()


func is_open() -> bool:
	return _open


func _on_node_activated(index: int) -> void:
	if index < 0 or index >= _focus_rows.size():
		return
	var row: Dictionary = _focus_rows[index]
	var tick := int(row.get("tick", 0))
	var sequence := int(row.get("sequence", -1))
	var event_id := str(row.get("event_id", ""))
	ObserverLog.debug(
		"observer.debugger",
		"focus_from_debugger tick=%s sequence=%s event_id=%s" % [tick, sequence, event_id],
	)
	ObserverLog.info(
		"observer.debugger",
		"seek_from_debugger tick=%s sequence=%s" % [tick, sequence],
	)
	focus_requested.emit(tick, sequence, event_id)
