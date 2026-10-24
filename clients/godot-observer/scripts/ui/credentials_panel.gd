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
	call_deferred("_log_acceptance_controls")


func _on_apply() -> void:
	ObserverLog.debug(
		"acceptance",
		"credentials_lengths inspection=%s debug=%s" % [
			_inspection.text.length(), _debug.text.length(),
		],
	)
	apply_requested.emit(_inspection.text, _debug.text)
	_inspection.text = ""
	_debug.text = ""
	ObserverLog.debug("acceptance", "credentials_inputs_cleared")


func note_result(ok: bool, reason_code: String) -> void:
	_status.text = "Applied. Memory-only credentials active." if ok else "Rejected: %s" % reason_code


func set_present(inspection_present: bool, debug_present: bool) -> void:
	_status.text = "Inspection: %s | Debug: %s" % [
		"set" if inspection_present else "none",
		"set" if debug_present else "none",
	]


func _log_acceptance_controls() -> void:
	for entry in [
		["credentials_inspection", _inspection],
		["credentials_debug", _debug],
		["credentials_apply", _apply],
		["credentials_forget", _forget],
	]:
		var rect := (entry[1] as Control).get_global_rect()
		ObserverLog.debug(
			"acceptance",
			"control id=%s x=%s y=%s w=%s h=%s" % [
				entry[0], rect.position.x, rect.position.y, rect.size.x, rect.size.y,
			],
		)
	ObserverLog.debug("acceptance", "credentials_ready")
