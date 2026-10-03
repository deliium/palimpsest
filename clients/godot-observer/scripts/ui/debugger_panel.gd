extends PanelContainer

## Read-only research causal debugger panel.
## Compact Why? inspector — server chain only; no local causal assembly.

const ObserverLog := preload("res://scripts/log.gd")
const DebuggerLabels := preload("res://scripts/presentation/debugger_labels.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")

signal focus_requested(tick: int, sequence: int, event_id: String)
signal closed

var _header: Label
var _legend: Label
var _close: Button
var _expand: Button
var _seek: Button
var _compact_list: ItemList
var _expanded_list: ItemList
var _supporting_list: ItemList

var _payload: Dictionary = {}
var _focus_rows: Array = []
var _expanded_rows: Array = []
var _expanded := false
var _open := false
var _selected_expanded := -1


func _ready() -> void:
	visible = false
	_ensure_children()
	_close.pressed.connect(func() -> void:
		close_panel()
	)
	_expand.pressed.connect(_toggle_expanded)
	_seek.pressed.connect(_on_seek_pressed)
	_compact_list.item_activated.connect(_on_compact_activated)
	_expanded_list.item_activated.connect(_on_expanded_activated)
	_expanded_list.item_selected.connect(_on_expanded_selected)


func _ensure_children() -> void:
	if _header != null:
		return
	var column := VBoxContainer.new()
	column.name = "Column"
	add_child(column)

	var title_row := HBoxContainer.new()
	column.add_child(title_row)
	var title := Label.new()
	title.text = "Why?"
	title_row.add_child(title)
	_expand = Button.new()
	_expand.text = "Expand"
	title_row.add_child(_expand)
	_seek = Button.new()
	_seek.text = "Seek"
	_seek.name = "SeekButton"
	_seek.disabled = true
	title_row.add_child(_seek)
	_close = Button.new()
	_close.text = "Close"
	title_row.add_child(_close)

	_header = Label.new()
	_header.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_header)

	_legend = Label.new()
	_legend.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_legend.text = "Structured artifacts only — not chain-of-thought or ground truth."
	column.add_child(_legend)

	var compact_label := Label.new()
	compact_label.text = "Compact"
	column.add_child(compact_label)
	_compact_list = ItemList.new()
	_compact_list.custom_minimum_size = Vector2(320, 140)
	_compact_list.name = "CompactStrip"
	column.add_child(_compact_list)

	_expanded_list = ItemList.new()
	_expanded_list.custom_minimum_size = Vector2(320, 180)
	_expanded_list.name = "ExpandedArtifacts"
	_expanded_list.visible = false
	column.add_child(_expanded_list)

	var support_label := Label.new()
	support_label.text = "Supporting (secondary)"
	column.add_child(support_label)
	_supporting_list = ItemList.new()
	_supporting_list.custom_minimum_size = Vector2(320, 48)
	_supporting_list.name = "SupportingNodes"
	column.add_child(_supporting_list)


func open_payload(payload: Dictionary) -> void:
	## Render a server causal-trace projection already fetched.
	_ensure_children()
	visible = true
	_open = true
	_payload = payload.duplicate(true)
	_render_primary()
	var availability := str(payload.get("availability", ""))
	var nodes: Array = payload.get("nodes", [])
	ObserverLog.info(
		"observer.debugger",
		"debugger_opened availability=%s node_count=%s" % [availability, nodes.size()],
	)
	ObserverLog.debug(
		"observer.debugger",
		"debugger_payload_rendered node_count=%s expanded=%s" % [nodes.size(), _expanded],
	)


func show_unavailable(reason_code: String) -> void:
	_ensure_children()
	visible = true
	_open = true
	_payload = {}
	_focus_rows.clear()
	_expanded_rows.clear()
	_selected_expanded = -1
	_compact_list.clear()
	_expanded_list.clear()
	_supporting_list.clear()
	_refresh_affordance_buttons()
	_header.text = "debugger unavailable reason_code=%s" % reason_code
	_legend.text = "Capability or projection unavailable — not an empty cognition chain."
	ObserverLog.warn(
		"observer.debugger",
		"debugger_unavailable reason_code=%s" % reason_code,
	)


func close_panel() -> void:
	visible = false
	_open = false
	_expanded = false
	_payload = {}
	_focus_rows.clear()
	_expanded_rows.clear()
	if _compact_list != null:
		_compact_list.clear()
	if _expanded_list != null:
		_expanded_list.clear()
		_expanded_list.visible = false
	if _supporting_list != null:
		_supporting_list.clear()
	if _header != null:
		_header.text = ""
	if _expand != null:
		_expand.text = "Expand"
	ObserverLog.info("observer.debugger", "debugger_closed")
	closed.emit()


func is_open() -> bool:
	return _open


func is_expanded() -> bool:
	return _expanded


func _render_primary() -> void:
	_focus_rows.clear()
	_expanded_rows.clear()
	_selected_expanded = -1
	_compact_list.clear()
	_expanded_list.clear()
	_supporting_list.clear()

	var availability := str(_payload.get("availability", ""))
	var ambiguity := bool(_payload.get("ambiguity", false))
	var reason := str(_payload.get("reason_code", ""))
	var address: Variant = _payload.get("address", {})
	var tick := 0
	var sequence := -1
	var event_id := ""
	var agent_id := ""
	if typeof(address) == TYPE_DICTIONARY:
		tick = int(address.get("tick", 0))
		if address.get("sequence", null) != null:
			sequence = int(address.get("sequence"))
		event_id = str(address.get("event_id", ""))
		agent_id = str(address.get("agent_id", ""))
	_header.text = "availability=%s ambiguity=%s agent_id=%s tick=%s sequence=%s event_id=%s" % [
		availability, ambiguity, agent_id, tick, sequence, event_id,
	]
	if reason != "":
		_header.text += " reason=%s" % reason

	var nodes: Array = _payload.get("nodes", [])
	var supporting: Array = _payload.get("supporting_nodes", [])
	if supporting.is_empty():
		supporting = DebuggerLabels.supporting_nodes(nodes)

	_render_compact(nodes, tick, sequence, event_id)
	_render_expanded(nodes, tick, sequence, event_id)
	_render_supporting(supporting)
	_expanded_list.visible = _expanded
	_expand.text = "Collapse" if _expanded else "Expand"
	_refresh_affordance_buttons()


func _render_compact(nodes: Array, tick: int, sequence: int, event_id: String) -> void:
	var groups: Dictionary = DebuggerLabels.group_nodes_by_compact(nodes)
	for label in DebuggerLabels.COMPACT_SEQUENCE:
		var children: Array = groups.get(label, [])
		var rollup: Dictionary = DebuggerLabels.rollup_status(children)
		var status := str(rollup.get("status", "unavailable"))
		var reason_code := str(rollup.get("reason_code", ""))
		var kind := DebuggerLabels.KIND_ANALYTICAL
		if label == "Expected":
			kind = DebuggerLabels.expected_artifact_kind(children)
		elif not children.is_empty():
			kind = DebuggerLabels.artifact_kind_for_stage(str(children[0].get("stage_code", "")))
		elif label == "Acted":
			kind = DebuggerLabels.KIND_OBJECTIVE_EVENT
		elif label == "Observed":
			kind = DebuggerLabels.KIND_OBSERVATION
		var line := "%s [%s]" % [label, status]
		if status != "available" and reason_code != "":
			line += " (%s)" % reason_code
		line += " · %s" % kind
		var index := _compact_list.add_item(line)
		_compact_list.set_item_custom_fg_color(index, Themes.debugger_artifact_color(kind))
		_focus_rows.append({
			"kind": "compact",
			"label": label,
			"artifact_kind": kind,
			"children": children,
			"tick": tick,
			"sequence": sequence,
			"event_id": event_id,
		})
	_legend.text = (
		"Structured artifacts only — not chain-of-thought or ground truth. "
		+ DebuggerLabels.legend_for_kind(DebuggerLabels.KIND_IMAGINATION)
	)


func _render_expanded(nodes: Array, tick: int, sequence: int, event_id: String) -> void:
	var ordered: Array = DebuggerLabels.chain_nodes_ordered(nodes)
	for node in ordered:
		var stage := str(node.get("stage_code", ""))
		var status := str(node.get("status", ""))
		var reason_code := str(node.get("reason_code", ""))
		var label := DebuggerLabels.expanded_label(stage)
		var kind := DebuggerLabels.artifact_kind_for_stage(stage)
		var line := "%s [%s]" % [label, status]
		if status != "available" and reason_code != "":
			line += " (%s)" % reason_code
		var counts: Variant = node.get("counts", null)
		if typeof(counts) == TYPE_DICTIONARY and not (counts as Dictionary).is_empty():
			line += " counts=%s" % str(counts)
		var command_kind := str(node.get("command_kind", ""))
		if command_kind != "":
			line += " command=%s" % command_kind
		var intention_code := str(node.get("intention_code", ""))
		if intention_code != "":
			line += " intention=%s" % intention_code
		var refs := DebuggerLabels.parse_id_refs(node.get("id_refs", []))
		if not refs.is_empty():
			line += " refs=%s" % refs.size()
		line += " · %s" % kind
		var index := _expanded_list.add_item(line)
		_expanded_list.set_item_custom_fg_color(index, Themes.debugger_artifact_color(kind))
		var focus_tick := tick
		var focus_sequence := sequence
		var focus_event := event_id
		var has_focus := false
		var focuses: Array = node.get("observer_focus", [])
		if not focuses.is_empty() and typeof(focuses[0]) == TYPE_DICTIONARY:
			var focus: Dictionary = focuses[0]
			focus_tick = int(focus.get("tick", focus_tick))
			if focus.get("sequence", null) != null:
				focus_sequence = int(focus.get("sequence"))
			focus_event = str(focus.get("event_id", focus_event))
			has_focus = true
		_expanded_rows.append({
			"stage_code": stage,
			"artifact_kind": kind,
			"tick": focus_tick,
			"sequence": focus_sequence,
			"event_id": focus_event,
			"has_focus": has_focus,
			"id_refs": refs,
			"node": node,
		})


func _render_supporting(supporting: Array) -> void:
	for node in supporting:
		if typeof(node) != TYPE_DICTIONARY:
			continue
		var stage := str(node.get("stage_code", ""))
		var status := str(node.get("status", ""))
		var reason_code := str(node.get("reason_code", ""))
		var line := "%s [%s]" % [stage, status]
		if reason_code != "":
			line += " (%s)" % reason_code
		var index := _supporting_list.add_item(line)
		_supporting_list.set_item_custom_fg_color(
			index,
			Themes.debugger_artifact_color(DebuggerLabels.KIND_ANALYTICAL),
		)


func _toggle_expanded() -> void:
	_expanded = not _expanded
	_expanded_list.visible = _expanded
	_expand.text = "Collapse" if _expanded else "Expand"
	_refresh_affordance_buttons()
	ObserverLog.debug(
		"observer.debugger",
		"debugger_expand_toggled expanded=%s" % _expanded,
	)


func _on_compact_activated(index: int) -> void:
	## Expanding a compact cell reveals the full chain (server order).
	if not _expanded:
		_toggle_expanded()
	if index < 0 or index >= _focus_rows.size():
		return
	var row: Dictionary = _focus_rows[index]
	ObserverLog.debug(
		"observer.debugger",
		"compact_activated label=%s artifact_kind=%s" % [
			str(row.get("label", "")),
			str(row.get("artifact_kind", "")),
		],
	)


func _on_expanded_selected(index: int) -> void:
	_selected_expanded = index
	_refresh_affordance_buttons()


func _on_expanded_activated(index: int) -> void:
	_selected_expanded = index
	_refresh_affordance_buttons()
	_seek_expanded_row(index)


func _on_seek_pressed() -> void:
	if not _expanded:
		_toggle_expanded()
	var index := _selected_or_first_seekable()
	if index < 0:
		ObserverLog.debug(
			"observer.debugger",
			"seek_skipped reason_code=no_selection",
		)
		return
	_seek_expanded_row(index)


func seek_at_expanded(index: int) -> void:
	_selected_expanded = index
	_refresh_affordance_buttons()
	_seek_expanded_row(index)


func _selected_or_first_seekable() -> int:
	if _selected_expanded >= 0 and _selected_expanded < _expanded_rows.size():
		return _selected_expanded
	for index in _expanded_rows.size():
		if bool((_expanded_rows[index] as Dictionary).get("has_focus", false)):
			return index
	return -1


func _refresh_affordance_buttons() -> void:
	if _seek == null:
		return
	var seekable := false
	if _selected_expanded >= 0 and _selected_expanded < _expanded_rows.size():
		var row: Dictionary = _expanded_rows[_selected_expanded]
		seekable = bool(row.get("has_focus", false))
	else:
		seekable = _selected_or_first_seekable() >= 0
	_seek.disabled = not seekable


func _seek_expanded_row(index: int) -> void:
	if index < 0 or index >= _expanded_rows.size():
		return
	var row: Dictionary = _expanded_rows[index]
	if not bool(row.get("has_focus", false)):
		ObserverLog.debug(
			"observer.debugger",
			"seek_skipped reason_code=no_observer_focus stage_code=%s" % str(row.get("stage_code", "")),
		)
		return
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


## Compatibility shim for older tests that call node activation by index.
func _on_node_activated(index: int) -> void:
	if not _expanded:
		_toggle_expanded()
	_seek_expanded_row(index)
