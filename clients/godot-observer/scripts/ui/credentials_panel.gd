extends PanelContainer

signal apply_requested(inspection_token: String, debug_token: String)
signal forget_requested

@onready var _inspection: LineEdit = $Column/Inspection
@onready var _debug: LineEdit = $Column/Debug
@onready var _apply: Button = $Column/Actions/Apply
@onready var _forget: Button = $Column/Actions/Forget
@onready var _status: Label = $Column/Status


func _ready() -> void:
	_inspection.secret = true
	_debug.secret = true
	_apply.pressed.connect(_on_apply)
	_forget.pressed.connect(func() -> void: forget_requested.emit())
	_status.text = "Credentials are memory-only."


func _on_apply() -> void:
	apply_requested.emit(_inspection.text, _debug.text)
	_inspection.text = ""
	_debug.text = ""


func note_result(ok: bool, reason_code: String) -> void:
	_status.text = "Applied. Memory-only credentials active." if ok else "Rejected: %s" % reason_code


func set_present(inspection_present: bool, debug_present: bool) -> void:
	_status.text = "Inspection: %s | Debug: %s" % [
		"set" if inspection_present else "none",
		"set" if debug_present else "none",
	]
