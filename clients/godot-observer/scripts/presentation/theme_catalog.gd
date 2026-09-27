extends RefCounted
class_name ObserverThemes

const ObserverLog := preload("res://scripts/log.gd")

const _COLORS := {
	"camp": Color(0.78, 0.64, 0.42, 1.0),
	"spring": Color(0.45, 0.72, 0.84, 1.0),
	"grove": Color(0.40, 0.62, 0.34, 1.0),
	"ridge": Color(0.62, 0.55, 0.48, 1.0),
}

const FALLBACK := Color(0.45, 0.48, 0.52, 1.0)

const _WEATHER := {
	"clear": Color(1, 1, 1, 0),
	"rain": Color(0.35, 0.5, 0.75, 0.35),
	"storm": Color(0.22, 0.25, 0.38, 0.5),
	"cold": Color(0.65, 0.8, 0.9, 0.28),
	"heat": Color(0.9, 0.5, 0.25, 0.28),
	"snow": Color(0.92, 0.95, 1.0, 0.35),
	"fog": Color(0.75, 0.75, 0.78, 0.32),
}


static func zone_color(theme: Variant) -> Color:
	var key := "" if theme == null else str(theme)
	if _COLORS.has(key):
		return _COLORS[key]
	if not key.is_empty():
		ObserverLog.debug("locations", "theme_unknown theme=%s" % key)
	return FALLBACK


static func weather_tint(condition: Variant) -> Color:
	var key := "" if condition == null else str(condition)
	if _WEATHER.has(key):
		return _WEATHER[key]
	return Color(1, 1, 1, 0)
