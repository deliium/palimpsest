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
	}


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
	return {
		"ok": true,
		"application_version": application,
		"protocol_version": protocol,
		"export_engine": export_engine,
		"revision": revision,
	}
