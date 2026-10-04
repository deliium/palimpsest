extends RefCounted

const StatusBar := preload("res://scripts/ui/status_bar.gd")
const EventLog := preload("res://scripts/ui/event_log.gd")


func run() -> Array:
	var failures: Array = []
	var bar := StatusBar.new()
	var column := VBoxContainer.new()
	column.name = "Column"
	bar.add_child(column)
	var row := HBoxContainer.new()
	row.name = "Row"
	column.add_child(row)
	var run_id := LineEdit.new()
	run_id.name = "RunId"
	row.add_child(run_id)
	var connect_btn := Button.new()
	connect_btn.name = "Connect"
	row.add_child(connect_btn)
	var state := Label.new()
	state.name = "State"
	row.add_child(state)
	var versions := Label.new()
	versions.name = "Versions"
	column.add_child(versions)
	bar._ready()
	bar.show_state("unsupported_observer_protocol", "unsupported_observer_protocol")
	if "observer-protocol-v1" not in bar.status_text():
		failures.append("protocol mismatch should name observer-protocol-v1")
	bar.show_state("switching_run", "Switching run")
	if "Switching" not in bar.status_text():
		failures.append("switching_run status copy missing")
	var log := EventLog.new()
	var weather := log._describe("WEATHER_CHANGED", "", "", "", "Camp", "")
	if "Camp" not in weather:
		failures.append("weather describe should include location")
	var structure := log._describe("STRUCTURE_BUILT", "Alice", "Alice", "", "Camp", "")
	if "structure" not in structure.to_lower() or "Camp" not in structure:
		failures.append("structure describe should mention structure and location")
	return failures
