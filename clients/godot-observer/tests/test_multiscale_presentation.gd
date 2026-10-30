extends RefCounted

const Protocol := preload("res://scripts/protocol/models.gd")
const VersionClient := preload("res://scripts/net/version_client.gd")
const Scale := preload("res://scripts/presentation/scale.gd")
const StatusBar := preload("res://scripts/ui/status_bar.gd")


func _status_bar() -> PanelContainer:
	var bar: PanelContainer = StatusBar.new()
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
	return bar


func run() -> Array:
	var failures: Array = []
	var thresholds := {
		0: "agent",
		23: "agent",
		24: "cohort",
		199: "cohort",
		200: "settlement",
		1999: "settlement",
		2000: "region",
		19999: "region",
		20000: "civilization",
	}
	for population in thresholds:
		var level: String = Scale.level_for_population(population)
		if level != thresholds[population]:
			failures.append(
				"scale level for %d should be %s, got %s"
				% [population, thresholds[population], level]
			)
	if Scale.level_for_population(-5) != "agent":
		failures.append("negative population should clamp to agent")
	if Scale.SCALE_LEVELS.size() != 5:
		failures.append("scale levels should be five")
	if Scale.SCALE_CONTRACT_VERSION != "observer-scale-v1":
		failures.append("scale contract version drift")

	if not Protocol.SUPPORTED_PROTOCOLS.has("observer-protocol-v1"):
		failures.append("supported protocols should include v1")
	if Protocol.SUPPORTED_PROTOCOLS.has(Protocol.RESERVED_PROTOCOL_VERSION):
		failures.append("reserved protocol must not be supported")
	if not Protocol._protocol_matches({"protocol_version": "observer-protocol-v1"}):
		failures.append("v1 payload should match")
	if Protocol._protocol_matches({"protocol_version": "observer-protocol-v2"}):
		failures.append("v2 payload must not match")
	if Protocol._protocol_matches({}):
		failures.append("missing protocol must not match")

	var payload := {
		"application_version": "0.1.0",
		"protocol_version": "observer-protocol-v1",
		"export_engine": "4.7.2-stable",
		"revision": "abc123",
		"supported_observer_protocols": ["observer-protocol-v1"],
		"observer_capabilities": ["structured_manifest", "replay_cursors"],
		"observer_reserved_capabilities": ["network_rows"],
		"observer_layout_version": "observer-layout-v1",
	}
	var lines := VersionClient.lines_from_body(payload)
	if not bool(lines.get("ok", false)):
		failures.append("additive version payload should parse")
	if (lines["supported_observer_protocols"] as Array).size() != 1:
		failures.append("supported protocols should parse")
	if (lines["observer_capabilities"] as Array).size() != 2:
		failures.append("capabilities should parse")
	if (lines["observer_reserved_capabilities"] as Array).size() != 1:
		failures.append("reserved capabilities should parse")
	if str(lines["observer_layout_version"]) != "observer-layout-v1":
		failures.append("layout version should parse")

	var legacy := VersionClient.lines_from_body({
		"protocol_version": "observer-protocol-v1",
		"application_version": "0.1.0",
		"export_engine": "4.7.2-stable",
		"revision": "abc123",
	})
	if (legacy["supported_observer_protocols"] as Array) != ["observer-protocol-v1"]:
		failures.append("legacy payload should default supported protocols to v1")
	if (legacy["observer_capabilities"] as Array).size() != 0:
		failures.append("legacy payload should default capabilities to empty")
	if str(legacy["observer_layout_version"]) != Protocol.LAYOUT_SCHEMA_VERSION:
		failures.append("legacy payload should default layout version")

	var bar := _status_bar()
	bar.show_versions("0.1.0", "observer-protocol-v1", "4.7.2-stable", "abc123")
	if "capabilities" in bar.status_text():
		failures.append("legacy status output should stay four lines")
	bar.show_versions("0.1.0", "observer-protocol-v1", "4.7.2-stable", "abc123", true, "", 4, 6, 1)
	var status: String = bar.status_text()
	if "capabilities 4 (+6 reserved), protocols 1" not in status:
		failures.append("capability summary line missing")
	bar.free()
	return failures
