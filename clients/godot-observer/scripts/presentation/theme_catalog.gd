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


const _SEASONS := {
	"spring": Color(0.55, 0.78, 0.45, 0.22),
	"summer": Color(0.93, 0.78, 0.35, 0.22),
	"autumn": Color(0.78, 0.48, 0.24, 0.22),
	"winter": Color(0.70, 0.82, 0.92, 0.28),
}

const _BANDS := {
	"cold": Color(0.55, 0.75, 0.95, 0.30),
	"mild": Color(0.85, 0.85, 0.78, 0.12),
	"hot": Color(0.95, 0.45, 0.28, 0.30),
}

const _HAZARDS := {
	"cold_snap": Color(0.75, 0.90, 1.0, 0.35),
	"heat": Color(0.95, 0.35, 0.15, 0.35),
}

const DEPLETED := Color(0.35, 0.32, 0.30, 0.55)

const _ARTIFACT_COLORS := {
	"mark": Color(0.72, 0.58, 0.38, 1.0),
	"sign": Color(0.55, 0.68, 0.42, 1.0),
	"note": Color(0.86, 0.78, 0.52, 1.0),
	"map": Color(0.42, 0.62, 0.72, 1.0),
	"record": Color(0.62, 0.48, 0.68, 1.0),
	"memorial": Color(0.58, 0.58, 0.62, 1.0),
}

const ARTIFACT_FALLBACK := Color(0.70, 0.66, 0.58, 1.0)


static func artifact_color(kind: Variant) -> Color:
	var key := "" if kind == null else str(kind)
	if _ARTIFACT_COLORS.has(key):
		return _ARTIFACT_COLORS[key]
	if not key.is_empty():
		ObserverLog.debug("artifacts", "theme_unknown kind=%s" % key)
	return ARTIFACT_FALLBACK


static func artifact_icon(kind: Variant) -> String:
	var key := "" if kind == null else str(kind)
	if key.is_empty():
		return "artifact_unknown"
	return "artifact_%s" % key


static func season_color(token: Variant) -> Color:
	return _token_color(_SEASONS, token)


static func band_color(token: Variant) -> Color:
	return _token_color(_BANDS, token)


static func hazard_color(token: Variant) -> Color:
	return _token_color(_HAZARDS, token)


static func _token_color(table: Dictionary, token: Variant) -> Color:
	var key := "" if token == null else str(token)
	if table.has(key):
		return table[key]
	return Color(1, 1, 1, 0)


static func weather_tint(condition: Variant) -> Color:
	var key := "" if condition == null else str(condition)
	if _WEATHER.has(key):
		return _WEATHER[key]
	return Color(1, 1, 1, 0)
