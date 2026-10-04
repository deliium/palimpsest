extends PanelContainer

signal return_requested
signal open_parent_requested
signal open_child_requested(child_run_id: String, fork_tick: int)
signal load_more_children_requested

const ObserverLog := preload("res://scripts/log.gd")

@onready var _summary: Label = $Column/Summary
@onready var _empty: Label = $Column/Empty
@onready var _children: ItemList = $Column/Children
@onready var _return_btn: Button = $Column/Actions/ReturnPrevious
@onready var _parent_btn: Button = $Column/Actions/OpenParent
@onready var _open_child_btn: Button = $Column/Actions/OpenChild
@onready var _more_btn: Button = $Column/Actions/LoadMore

var _child_rows: Array = []
var _nav_depth := 0
var _busy := false


func _ready() -> void:
	_return_btn.pressed.connect(func() -> void: return_requested.emit())
	_parent_btn.pressed.connect(func() -> void: open_parent_requested.emit())
	_open_child_btn.pressed.connect(_on_open_child)
	_more_btn.pressed.connect(func() -> void: load_more_children_requested.emit())
	_children.item_activated.connect(func(_index: int) -> void: _on_open_child())
	show_lineage({}, [], null, "", 0)


func set_busy(busy: bool) -> void:
	_busy = busy
	_return_btn.disabled = busy or _nav_depth <= 0
	_parent_btn.disabled = busy or not _parent_btn.visible
	_open_child_btn.disabled = busy or _child_rows.is_empty()
	_more_btn.disabled = busy or not _more_btn.visible


func set_nav_depth(depth: int) -> void:
	_nav_depth = depth
	_return_btn.disabled = _busy or depth <= 0
	ObserverLog.debug("branch_ui", "nav_depth=%s" % depth)


func show_lineage(
	lineage: Dictionary,
	children: Array,
	next_cursor: Variant,
	reason_code: String,
	nav_depth: int,
) -> void:
	_nav_depth = nav_depth
	_child_rows = children.duplicate()
	var run_id := str(lineage.get("run_id", ""))
	var parent_id := str(lineage.get("parent_run_id", ""))
	var fork_tick := int(lineage.get("fork_tick", -1))
	var summary := str(lineage.get("intervention_summary", ""))
	var branch_id := str(lineage.get("branch_id", ""))
	var lines: PackedStringArray = []
	if run_id != "":
		lines.append("run %s" % run_id)
	if parent_id != "":
		lines.append("parent %s @%s" % [parent_id, fork_tick])
	else:
		lines.append("root run (no parent)")
	if branch_id != "":
		lines.append("branch %s" % branch_id)
	if summary != "":
		lines.append(summary)
	_summary.text = "\n".join(lines)
	_parent_btn.visible = parent_id != ""
	_parent_btn.disabled = _busy or parent_id == ""
	_return_btn.disabled = _busy or nav_depth <= 0
	_children.clear()
	for child in children:
		if typeof(child) != TYPE_DICTIONARY:
			continue
		var child_id := str(child.get("child_run_id", ""))
		if child_id.is_empty():
			continue
		var label := "%s @%s" % [child_id, int(child.get("fork_tick", 0))]
		var child_summary := str(child.get("intervention_summary", ""))
		if child_summary != "":
			label += " — %s" % child_summary
		_children.add_item(label)
	_more_btn.visible = next_cursor != null and str(next_cursor) != ""
	_more_btn.disabled = _busy or not _more_btn.visible
	_open_child_btn.disabled = _busy or _children.item_count == 0
	if reason_code != "" and reason_code != "branch_root":
		_empty.text = "Branch unavailable (%s)" % reason_code
		_empty.visible = true
	elif children.is_empty() and parent_id == "" and reason_code == "":
		_empty.text = "No child branches"
		_empty.visible = true
	elif children.is_empty() and reason_code == "":
		_empty.text = "No child branches"
		_empty.visible = true
	else:
		_empty.visible = false
	ObserverLog.debug(
		"branch_ui",
		"branch_panel_updated children=%s nav_depth=%s reason_code=%s" % [
			children.size(), nav_depth, reason_code if reason_code != "" else "-",
		],
	)


func _on_open_child() -> void:
	var selected := _children.get_selected_items()
	if selected.is_empty():
		if _child_rows.is_empty():
			return
		selected = PackedInt32Array([0])
		_children.select(0)
	var index := int(selected[0])
	if index < 0 or index >= _child_rows.size():
		return
	var row: Dictionary = _child_rows[index]
	var child_id := str(row.get("child_run_id", ""))
	if child_id.is_empty():
		return
	open_child_requested.emit(child_id, int(row.get("fork_tick", 0)))
