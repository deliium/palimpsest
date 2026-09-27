extends RefCounted

const Cursor := preload("res://scripts/protocol/cursor.gd")


func run() -> Array:
	var failures: Array = []
	var opened: Dictionary = Cursor.consider(1, 0, null, null)
	if not opened["applied"] or opened["after_tick"] != 1 or opened["after_sequence"] != 0:
		failures.append("null cursor should accept the first event")
	var duplicate: Dictionary = Cursor.consider(1, 0, 1, 0)
	if duplicate["applied"] or duplicate["reason_code"] != "stale_cursor":
		failures.append("duplicate cursor should be skipped")
	var older: Dictionary = Cursor.consider(0, 9, 1, 0)
	if older["applied"]:
		failures.append("older cursor should be skipped")
	var next: Dictionary = Cursor.consider(1, 1, 1, 0)
	if not next["applied"] or next["after_sequence"] != 1:
		failures.append("strictly greater sequence should apply")
	var later_tick: Dictionary = Cursor.consider(2, 0, 1, 8)
	if not later_tick["applied"] or later_tick["after_tick"] != 2:
		failures.append("later tick should apply")
	return failures
