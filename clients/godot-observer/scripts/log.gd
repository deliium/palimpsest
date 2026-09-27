extends RefCounted
class_name ObserverLog

const _LEVELS := {
	"DEBUG": 10,
	"INFO": 20,
	"WARN": 30,
	"ERROR": 40,
}

static var _threshold: int = 10
static var _started: bool = false


static func start() -> void:
	if _started:
		return
	_started = true
	var raw := str(ProjectSettings.get_setting("palimpsest/log_level", "DEBUG")).to_upper()
	if _LEVELS.has(raw):
		_threshold = int(_LEVELS[raw])
	else:
		_threshold = 10
		raw = "DEBUG"
	_write(20, "log", "level_set level=%s" % raw)


static func debug(area: String, message: String) -> void:
	_write(10, area, message)


static func info(area: String, message: String) -> void:
	_write(20, area, message)


static func warn(area: String, message: String) -> void:
	_write(30, area, message)


static func error(area: String, message: String) -> void:
	_write(40, area, message)


static func _write(level: int, area: String, message: String) -> void:
	if not _started:
		start()
	if level < _threshold:
		return
	print("[observer.%s] %s" % [area, message])
