extends PanelContainer

signal connect_requested(run_id: String)

@onready var _run_id: LineEdit = $Row/RunId
@onready var _state: Label = $Row/State


func _ready() -> void:
	var configured := str(ProjectSettings.get_setting("palimpsest/run_id", "")).strip_edges()
	if not configured.is_empty():
		_run_id.text = configured
	$Row/Connect.pressed.connect(_on_connect)
	show_state("loading", "Loading")


func show_state(code: String, detail: String) -> void:
	_state.text = detail if detail != "" else code


func _on_connect() -> void:
	connect_requested.emit(_run_id.text)
