extends RefCounted

const Protocol := preload("res://scripts/protocol/models.gd")

const EXPORT_ENGINE := "4.7.2-stable"
const BUILD_INFO_PATH := "res://build-info.json"


static func local_lines() -> Dictionary:
	var application := "unknown"
	if FileAccess.file_exists(BUILD_INFO_PATH):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(BUILD_INFO_PATH))
		if typeof(parsed) == TYPE_DICTIONARY:
			var raw := str(parsed.get("application_version", "")).strip_edges()
			if not raw.is_empty():
				application = raw
	return {
		"application_version": application,
		"protocol_version": Protocol.PROTOCOL_VERSION,
		"export_engine": EXPORT_ENGINE,
		"revision": "unknown",
		"supported_observer_protocols": [Protocol.PROTOCOL_VERSION],
		"observer_capabilities": [],
		"observer_reserved_capabilities": [],
		"observer_layout_version": Protocol.LAYOUT_SCHEMA_VERSION,
	}


static func _string_array(value: Variant, fallback: Array) -> Array:
	if typeof(value) != TYPE_ARRAY:
		return fallback.duplicate()
	var parsed: Array = []
	for item in value:
		if typeof(item) != TYPE_STRING:
			continue
		var text := str(item).strip_edges()
		if not text.is_empty() and not parsed.has(text):
			parsed.append(text)
	return parsed


static func lines_from_body(body: Variant) -> Dictionary:
	if typeof(body) != TYPE_DICTIONARY:
		return {"ok": false, "reason_code": "invalid_json"}
	var fallback := local_lines()
	var application := str(body.get("application_version", "")).strip_edges()
	var protocol := str(body.get("protocol_version", "")).strip_edges()
	var export_engine := str(body.get("export_engine", "")).strip_edges()
	var revision := str(body.get("revision", "")).strip_edges()
	if application.is_empty():
		application = str(fallback["application_version"])
	if protocol.is_empty():
		protocol = str(fallback["protocol_version"])
	if export_engine.is_empty():
		export_engine = str(fallback["export_engine"])
	if revision.is_empty():
		revision = "unknown"
	var supported := _string_array(
		body.get("supported_observer_protocols"),
		[Protocol.PROTOCOL_VERSION],
	)
	if supported.is_empty():
		supported = [Protocol.PROTOCOL_VERSION]
	var capabilities := _string_array(body.get("observer_capabilities"), [])
	var reserved := _string_array(body.get("observer_reserved_capabilities"), [])
	var layout := str(body.get("observer_layout_version", "")).strip_edges()
	if layout.is_empty():
		layout = Protocol.LAYOUT_SCHEMA_VERSION
	return {
		"ok": true,
		"application_version": application,
		"protocol_version": protocol,
		"export_engine": export_engine,
		"revision": revision,
		"supported_observer_protocols": supported,
		"observer_capabilities": capabilities,
		"observer_reserved_capabilities": reserved,
		"observer_layout_version": layout,
	}
