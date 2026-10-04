extends PanelContainer

signal connect_requested(run_id: String)

const ObserverLog := preload("res://scripts/log.gd")
const Origin := preload("res://scripts/net/origin.gd")
const VersionClient := preload("res://scripts/net/version_client.gd")

@onready var _run_id: LineEdit = $Column/Row/RunId
@onready var _state: Label = $Column/Row/State
@onready var _versions: Label = $Column/Versions

var _version_http: HTTPRequest


func _ready() -> void:
	var configured := str(ProjectSettings.get_setting("palimpsest/run_id", "")).strip_edges()
	if not configured.is_empty():
		_run_id.text = configured
	$Column/Row/Connect.pressed.connect(_on_connect)
	show_state("loading", "Loading")
	_load_versions()


func set_run_id(value: String) -> void:
	_run_id.text = value


func show_versions(
	application: String,
	protocol: String,
	export_engine: String,
	revision: String,
	loaded: bool = true,
	reason_code: String = "",
) -> void:
	_versions.text = "application %s\nprotocol %s\nexport %s\nrevision %s" % [
		application, protocol, export_engine, revision,
	]
	if loaded:
		ObserverLog.info(
			"version",
			"version_loaded application=%s protocol=%s export_engine=%s revision=%s" % [
				application, protocol, export_engine, revision,
			],
		)
	else:
		ObserverLog.error("version", "version_failed reason_code=%s" % reason_code)


func status_text() -> String:
	return "%s\n%s" % [_versions.text, _state.text]


func show_state(code: String, detail: String) -> void:
	var copy := detail if detail != "" else code
	match code:
		"unsupported_observer_protocol":
			copy = "Unsupported protocol — expected observer-protocol-v1 (unsupported_observer_protocol)"
		"loading":
			copy = "Loading"
		"seeking":
			copy = "Seeking…"
		"switching_run":
			copy = "Switching run…"
		"behind_live":
			copy = "REPLAY (behind live)"
		"ready":
			if detail != "" and not detail.begins_with("LIVE") and not detail.begins_with("REPLAY"):
				copy = detail
		"nav_stack_empty":
			copy = "No previous run"
		"branch_root":
			copy = "No parent branch"
		"unauthorized":
			copy = "Capability denied"
	_state.text = copy


func show_transport(mode: String, paused: bool, behind_live: bool, detail: String = "") -> void:
	var badge := mode
	if paused:
		badge += " paused"
	if behind_live:
		badge += " behind live"
	if detail != "":
		badge += " — %s" % detail
	_state.text = badge


func _on_connect() -> void:
	connect_requested.emit(_run_id.text)


func _load_versions() -> void:
	var web := OS.has_feature("web")
	var origin := Origin.resolve()
	if web or not origin.is_empty():
		_request_version(origin)
		return
	var lines := VersionClient.local_lines()
	show_versions(
		str(lines["application_version"]),
		str(lines["protocol_version"]),
		str(lines["export_engine"]),
		str(lines["revision"]),
	)


func _request_version(origin: String) -> void:
	if origin.strip_edges().is_empty():
		_show_local(false, "origin_missing")
		return
	_version_http = HTTPRequest.new()
	_version_http.timeout = 20.0
	add_child(_version_http)
	_version_http.request_completed.connect(_on_version)
	var err := _version_http.request(
		"%s/version" % origin.strip_edges().trim_suffix("/"),
		PackedStringArray(["Accept: application/json"]),
		HTTPClient.METHOD_GET,
	)
	if err != OK:
		_show_local(false, "request_failed")


func _on_version(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray,
) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		var reason := "request_failed"
		if result == HTTPRequest.RESULT_SUCCESS:
			reason = "http_%s" % response_code
		_show_local(false, reason)
		return
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	var lines := VersionClient.lines_from_body(parsed)
	if not bool(lines.get("ok", false)):
		_show_local(false, str(lines.get("reason_code", "invalid_json")))
		return
	show_versions(
		str(lines["application_version"]),
		str(lines["protocol_version"]),
		str(lines["export_engine"]),
		str(lines["revision"]),
	)


func _show_local(loaded: bool, reason_code: String) -> void:
	var lines := VersionClient.local_lines()
	show_versions(
		str(lines["application_version"]),
		str(lines["protocol_version"]),
		str(lines["export_engine"]),
		str(lines["revision"]),
		loaded,
		reason_code,
	)
