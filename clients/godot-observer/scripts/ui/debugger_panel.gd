extends PanelContainer

## Read-only research causal debugger panel.
## Compact Why? inspector — server chain only; no local causal assembly.

const ObserverLog := preload("res://scripts/log.gd")
const DebuggerLabels := preload("res://scripts/presentation/debugger_labels.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")

const NAV_STACK_MAX := 8

signal focus_requested(tick: int, sequence: int, event_id: String)
signal provenance_requested(lineage_kind: String, subject_id: String, owner_id: String)
signal closed

var _header: Label
var _legend: Label
var _close: Button
var _back: Button
var _expand: Button
var _seek: Button
var _provenance: Button
var _compact_list: ItemList
var _expanded_list: ItemList
var _supporting_list: ItemList
var _secondary_header: Label
var _secondary_list: ItemList

var _payload: Dictionary = {}
var _primary_payload: Dictionary = {}
var _focus_rows: Array = []
var _expanded_rows: Array = []
var _provenance_rows: Array = []
var _nav_stack: Array = []
var _expanded := false
var _open := false
var _secondary_open := false
var _selected_expanded := -1


func _ready() -> void:
	visible = false
	_ensure_children()
	_close.pressed.connect(func() -> void:
		close_panel()
	)
	_back.pressed.connect(_on_back_pressed)
	_expand.pressed.connect(_toggle_expanded)
	_seek.pressed.connect(_on_seek_pressed)
	_provenance.pressed.connect(_on_provenance_pressed)
	_compact_list.item_activated.connect(_on_compact_activated)
	_expanded_list.item_activated.connect(_on_expanded_activated)
	_expanded_list.item_clicked.connect(_on_expanded_clicked)
	_expanded_list.item_selected.connect(_on_expanded_selected)
	_secondary_list.item_activated.connect(_on_secondary_activated)


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
	_back = Button.new()
	_back.text = "Back"
	_back.visible = false
	title_row.add_child(_back)
	_expand = Button.new()
	_expand.text = "Expand"
	title_row.add_child(_expand)
	_seek = Button.new()
	_seek.text = "Seek"
	_seek.name = "SeekButton"
	_seek.disabled = true
	title_row.add_child(_seek)
	_provenance = Button.new()
	_provenance.text = "Provenance"
	_provenance.name = "ProvenanceButton"
	_provenance.disabled = true
	title_row.add_child(_provenance)
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

	_secondary_header = Label.new()
	_secondary_header.text = "Provenance"
	_secondary_header.visible = false
	column.add_child(_secondary_header)
	_secondary_list = ItemList.new()
	_secondary_list.custom_minimum_size = Vector2(320, 100)
	_secondary_list.name = "SecondaryProvenance"
	_secondary_list.visible = false
	column.add_child(_secondary_list)


func open_payload(payload: Dictionary) -> void:
	## Render a server causal-trace projection already fetched.
	_ensure_children()
	visible = true
	_open = true
	_payload = payload.duplicate(true)
	# Fresh Why? entry replaces the decision root and clears provenance nav.
	_primary_payload = payload.duplicate(true)
	_nav_stack.clear()
	_back.visible = false
	_clear_secondary()
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
	_primary_payload = {}
	_nav_stack.clear()
	_focus_rows.clear()
	_expanded_rows.clear()
	_selected_expanded = -1
	_compact_list.clear()
	_expanded_list.clear()
	_supporting_list.clear()
	_clear_secondary()
	_back.visible = false
	_refresh_affordance_buttons()
	_header.text = "debugger unavailable reason_code=%s" % reason_code
	_legend.text = "Capability or projection unavailable — not an empty cognition chain."
	ObserverLog.warn(
		"observer.debugger",
		"debugger_unavailable reason_code=%s" % reason_code,
	)


func open_lineage_payload(payload: Dictionary) -> void:
	## Secondary provenance pane only — does not replace the primary causal strip.
	_ensure_children()
	if not _open:
		visible = true
		_open = true
	_secondary_open = true
	_secondary_header.visible = true
	_secondary_list.visible = true
	_secondary_list.clear()
	_provenance_rows.clear()
	var entries: Array = payload.get("entries", [])
	if entries.is_empty() and payload.has("entry_id"):
		entries = [payload]
	var entry_count := 0
	for entry in entries:
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		entry_count += 1
		var entry_id := str(entry.get("entry_id", entry.get("subject_id", "")))
		var status := str(entry.get("status", ""))
		var reason := str(entry.get("reason_code", ""))
		var line := "%s [%s]" % [entry_id, status]
		if reason != "":
			line += " (%s)" % reason
		_secondary_list.add_item(line)
		var focus_tick := 0
		var focus_sequence := -1
		var focus_event := ""
		var focuses: Array = entry.get("observer_focus", [])
		if not focuses.is_empty() and typeof(focuses[0]) == TYPE_DICTIONARY:
			var focus: Dictionary = focuses[0]
			focus_tick = int(focus.get("tick", 0))
			if focus.get("sequence", null) != null:
				focus_sequence = int(focus.get("sequence"))
			focus_event = str(focus.get("event_id", ""))
		_provenance_rows.append({
			"tick": focus_tick,
			"sequence": focus_sequence,
			"event_id": focus_event,
			"has_focus": not focuses.is_empty(),
		})
	ObserverLog.info(
		"observer.debugger",
		"lineage_opened entry_count=%s" % entry_count,
	)


func show_lineage_unavailable(reason_code: String) -> void:
	_ensure_children()
	_secondary_open = true
	_secondary_header.visible = true
	_secondary_list.visible = true
	_secondary_list.clear()
	_provenance_rows.clear()
	_secondary_list.add_item("provenance unavailable reason_code=%s" % reason_code)
	ObserverLog.warn(
		"observer.debugger",
		"lineage_unavailable reason_code=%s" % reason_code,
	)


func close_panel() -> void:
	visible = false
	_open = false
	_expanded = false
	_payload = {}
	_primary_payload = {}
	_nav_stack.clear()
	_focus_rows.clear()
	_expanded_rows.clear()
	_clear_secondary()
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
	if _back != null:
		_back.visible = false
	ObserverLog.info("observer.debugger", "debugger_closed")
	closed.emit()


func is_open() -> bool:
	return _open


func is_expanded() -> bool:
	return _expanded


func primary_payload() -> Dictionary:
	return _primary_payload.duplicate(true)


func nav_depth() -> int:
	return _nav_stack.size()


func push_nav_frame(kind: String, meta: Dictionary = {}) -> void:
	## Bound stack ≤8; drop oldest with WARN on overflow.
	var frame := {
		"kind": kind,
		"primary": _primary_payload.duplicate(true),
		"payload": _payload.duplicate(true),
		"expanded": _expanded,
		"meta": meta.duplicate(true),
	}
	_nav_stack.append(frame)
	while _nav_stack.size() > NAV_STACK_MAX:
		_nav_stack.pop_front()
		ObserverLog.warn(
			"observer.debugger",
			"debugger_nav_overflow reason_code=stack_overflow depth=%s" % _nav_stack.size(),
		)
	_back.visible = _nav_stack.size() > 0
	ObserverLog.info(
		"observer.debugger",
		"debugger_nav_push kind=%s depth=%s" % [kind, _nav_stack.size()],
	)


func return_to_decision() -> void:
	## Restore stashed primary causal-trace payload and clear secondary pane.
	_clear_secondary()
	if not _primary_payload.is_empty():
		_payload = _primary_payload.duplicate(true)
		_render_primary()
	_nav_stack.clear()
	_back.visible = false
	ObserverLog.info(
		"observer.debugger",
		"debugger_return_to_decision depth=0",
	)


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
	_back.visible = _nav_stack.size() > 0
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
		if stage == "imagined_futures" or stage == "counterfactuals":
			# Expected chrome rule applies to the Expected compact cell; wire rows keep stage kinds.
			pass
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
	## Seek only — never silently combine Seek + Provenance.
	_selected_expanded = index
	_refresh_affordance_buttons()
	_seek_expanded_row(index)


func _on_expanded_clicked(index: int, _at_position: Vector2, mouse_button_index: int) -> void:
	_selected_expanded = index
	_refresh_affordance_buttons()
	## Right-click remains a Provenance shortcut; primary path is the Provenance button.
	if mouse_button_index != MOUSE_BUTTON_RIGHT:
		return
	_request_provenance_for_row(index)


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


func _on_provenance_pressed() -> void:
	if not _expanded:
		_toggle_expanded()
	var index := _selected_or_first_mapped()
	if index < 0:
		ObserverLog.debug(
			"observer.debugger",
			"provenance_skipped reason_code=no_selection",
		)
		return
	_request_provenance_for_row(index)


func request_provenance_at_expanded(index: int) -> void:
	## Test/helper entry for Provenance without requiring a right-click.
	_selected_expanded = index
	_refresh_affordance_buttons()
	_request_provenance_for_row(index)


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


func _selected_or_first_mapped() -> int:
	if _selected_expanded >= 0 and _selected_expanded < _expanded_rows.size():
		return _selected_expanded
	for index in _expanded_rows.size():
		if _row_has_mapped_ref(_expanded_rows[index] as Dictionary):
			return index
	return -1


func _row_has_mapped_ref(row: Dictionary) -> bool:
	var refs: Array = row.get("id_refs", [])
	for ref in refs:
		if DebuggerLabels.can_request_lineage(
			str(ref.get("kind", "")),
			str(ref.get("value", "")),
		):
			return true
	return false


func _refresh_affordance_buttons() -> void:
	if _seek == null or _provenance == null:
		return
	var seekable := false
	var mappable := false
	if _selected_expanded >= 0 and _selected_expanded < _expanded_rows.size():
		var row: Dictionary = _expanded_rows[_selected_expanded]
		seekable = bool(row.get("has_focus", false))
		mappable = _row_has_mapped_ref(row)
	else:
		seekable = _selected_or_first_seekable() >= 0
		mappable = _selected_or_first_mapped() >= 0
	_seek.disabled = not seekable
	_provenance.disabled = not mappable or _owner_id_from_payload() == ""
	ObserverLog.debug(
		"observer.debugger",
		"debugger_affordances seek_enabled=%s provenance_enabled=%s selected=%s" % [
			str(not _seek.disabled),
			str(not _provenance.disabled),
			_selected_expanded,
		],
	)


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
	ObserverLog.debug(
		"observer.debugger",
		"debugger_nav_choice action=seek",
	)
	# Keep panel open; primary payload remains stashed.
	focus_requested.emit(tick, sequence, event_id)


func _request_provenance_for_row(index: int) -> void:
	if index < 0 or index >= _expanded_rows.size():
		return
	var row: Dictionary = _expanded_rows[index]
	var refs: Array = row.get("id_refs", [])
	var mapped_kind := ""
	var subject_id := ""
	for ref in refs:
		var ref_kind := str(ref.get("kind", ""))
		var ref_value := str(ref.get("value", ""))
		var lineage := DebuggerLabels.mapped_lineage_kind(ref_kind, ref_value)
		if lineage != "":
			mapped_kind = lineage
			subject_id = ref_value
			break
	if mapped_kind == "" or subject_id == "":
		# Emit the WARN path once when the researcher explicitly requests Provenance.
		for ref in refs:
			DebuggerLabels.lineage_kind_for_id_ref(str(ref.get("kind", "")), str(ref.get("value", "")))
			break
		ObserverLog.debug(
			"observer.debugger",
			"provenance_skipped reason_code=no_mapped_id_ref stage_code=%s" % str(row.get("stage_code", "")),
		)
		return
	var owner_id := _owner_id_from_payload()
	if owner_id == "":
		ObserverLog.warn(
			"observer.debugger",
			"owner_id_missing reason_code=owner_id_missing",
		)
		return
	ObserverLog.debug(
		"observer.debugger",
		"debugger_nav_choice action=provenance lineage_kind=%s subject_id=%s" % [
			mapped_kind, subject_id,
		],
	)
	push_nav_frame("provenance", {
		"lineage_kind": mapped_kind,
		"subject_id": subject_id,
		"owner_id": owner_id,
	})
	provenance_requested.emit(mapped_kind, subject_id, owner_id)


func _owner_id_from_payload() -> String:
	var address: Variant = _payload.get("address", {})
	if typeof(address) != TYPE_DICTIONARY:
		return ""
	return str(address.get("agent_id", "")).strip_edges()


func _on_secondary_activated(index: int) -> void:
	if index < 0 or index >= _provenance_rows.size():
		return
	var row: Dictionary = _provenance_rows[index]
	if not bool(row.get("has_focus", false)):
		return
	focus_requested.emit(int(row.get("tick", 0)), int(row.get("sequence", -1)), str(row.get("event_id", "")))


func _on_back_pressed() -> void:
	if _nav_stack.is_empty():
		return_to_decision()
		return
	var frame: Dictionary = _nav_stack.pop_back()
	ObserverLog.info(
		"observer.debugger",
		"debugger_nav_pop depth=%s" % _nav_stack.size(),
	)
	_clear_secondary()
	var primary: Variant = frame.get("primary", {})
	if typeof(primary) == TYPE_DICTIONARY and not (primary as Dictionary).is_empty():
		_primary_payload = (primary as Dictionary).duplicate(true)
		_payload = _primary_payload.duplicate(true)
		_expanded = bool(frame.get("expanded", _expanded))
		_render_primary()
	else:
		return_to_decision()
	_back.visible = _nav_stack.size() > 0


func _clear_secondary() -> void:
	_secondary_open = false
	_provenance_rows.clear()
	if _secondary_header != null:
		_secondary_header.visible = false
	if _secondary_list != null:
		_secondary_list.visible = false
		_secondary_list.clear()


## Compatibility shim for older tests that call node activation by index.
func _on_node_activated(index: int) -> void:
	if not _expanded:
		_toggle_expanded()
	_seek_expanded_row(index)
