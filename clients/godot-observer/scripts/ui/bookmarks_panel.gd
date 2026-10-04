extends PanelContainer

signal add_requested(note: String)
signal jump_requested(tick: int, sequence: Variant)
signal delete_requested(index: int)
signal edit_requested(index: int, note: String)

const ObserverLog := preload("res://scripts/log.gd")

@onready var _list: ItemList = $Column/List
@onready var _empty: Label = $Column/Empty
@onready var _note: LineEdit = $Column/Note
@onready var _add: Button = $Column/Actions/Add
@onready var _jump: Button = $Column/Actions/Jump
@onready var _edit: Button = $Column/Actions/Edit
@onready var _delete: Button = $Column/Actions/Delete

var _items: Array = []


func _ready() -> void:
	_add.pressed.connect(func() -> void: add_requested.emit(_note.text.strip_edges()))
	_jump.pressed.connect(_on_jump)
	_edit.pressed.connect(_on_edit)
	_delete.pressed.connect(_on_delete)
	_list.item_activated.connect(func(_index: int) -> void: _on_jump())
	show_bookmarks([])


func show_bookmarks(items: Array) -> void:
	_items = items.duplicate(true)
	_list.clear()
	for item in _items:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var label := "tick %s" % int(item.get("tick", 0))
		if item.get("sequence", null) != null:
			label += ".%s" % int(item.get("sequence"))
		var note := str(item.get("note", ""))
		if note != "":
			label += " — %s" % note
		_list.add_item(label)
	_empty.visible = _items.is_empty()
	_empty.text = "No bookmarks for this run"
	_jump.disabled = _items.is_empty()
	_edit.disabled = _items.is_empty()
	_delete.disabled = _items.is_empty()
	ObserverLog.debug("bookmarks_ui", "list_updated count=%s" % _items.size())


func _selected_index() -> int:
	var selected := _list.get_selected_items()
	if selected.is_empty():
		return -1
	return int(selected[0])


func _on_jump() -> void:
	var index := _selected_index()
	if index < 0 or index >= _items.size():
		return
	var item: Dictionary = _items[index]
	jump_requested.emit(int(item.get("tick", 0)), item.get("sequence", null))


func _on_edit() -> void:
	var index := _selected_index()
	if index < 0:
		return
	edit_requested.emit(index, _note.text.strip_edges())


func _on_delete() -> void:
	var index := _selected_index()
	if index < 0:
		return
	delete_requested.emit(index)
