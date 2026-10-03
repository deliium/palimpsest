extends Node2D

const ObserverLog := preload("res://scripts/log.gd")
const Scale := preload("res://scripts/presentation/scale.gd")
const Themes := preload("res://scripts/presentation/theme_catalog.gd")

var _locations: Array = []
var _weather := {}
var _bands := {}
var _hazards := {}
var _depleted := {}
var _scarce := {}
var _season: Variant = null
var _rings := {}


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)


func show_world(world: Variant) -> void:
	_locations = world.locations
	_weather = {}
	_bands = {}
	_hazards = {}
	_depleted = {}
	_scarce = {}
	_season = world.get("season")
	for item in world.weather:
		_weather[item.location_id] = item.condition
	var bands: Variant = world.get("temperature_bands")
	if bands is Array:
		for item in bands:
			_bands[str(item.location_id)] = str(item.band)
	var hazards: Variant = world.get("hazards")
	if hazards is Array:
		for item in hazards:
			var location_id := str(item.location_id)
			if not _hazards.has(location_id):
				_hazards[location_id] = []
			_hazards[location_id].append(str(item.hazard_kind))
	var resources: Variant = world.get("resources")
	if resources is Array:
		for item in resources:
			var quantity := float(item.quantity)
			var location_id := str(item.location_id)
			if quantity == 0.0:
				_depleted[location_id] = true
				_scarce.erase(location_id)
			elif (
				quantity > 0.0
				and quantity <= Themes.SCARCE_QUANTITY_MAX
				and not _depleted.has(location_id)
			):
				_scarce[location_id] = true
	var hazard_count := 0
	for kinds in _hazards.values():
		hazard_count += kinds.size()
	var season_token := "-" if _season == null else str(_season)
	ObserverLog.debug(
		"locations",
		"environment_painted tick=%s season=%s hazard_count=%s depleted_count=%s scarce_count=%s" % [
			world.tick,
			season_token,
			hazard_count,
			_depleted.size(),
			_scarce.size(),
		],
	)
	_rings = _ring_positions()
	var connections := 0
	for location in _locations:
		connections += location.neighbor_ids.size()
	ObserverLog.debug(
		"locations",
		"map_built location_count=%s connection_count=%s" % [_locations.size(), connections],
	)
	queue_redraw()


# Sibling overlays paint claims and analytics. This layer stays on the objective snapshot.


func zone_rect(location_id: String) -> Rect2:
	for location in _locations:
		if location.location_id == location_id:
			return _rect_for(location)
	return Rect2()


func zone_center(location_id: String) -> Vector2:
	var rect := zone_rect(location_id)
	return rect.position + rect.size * 0.5


func _draw() -> void:
	var font := ThemeDB.fallback_font
	var font_size := ThemeDB.fallback_font_size
	for location in _locations:
		var rect := _rect_for(location)
		var theme = null if location.presentation == null else location.presentation.theme
		var color: Color = Themes.zone_color(theme)
		draw_rect(rect, Color(color.r, color.g, color.b, 0.35), true)
		if _season != null:
			draw_rect(rect, Themes.season_color(_season), true)
		var condition: Variant = _weather.get(location.location_id, null)
		if condition != null:
			draw_rect(rect, Themes.weather_tint(condition), true)
		var band: Variant = _bands.get(location.location_id, null)
		if band != null:
			draw_rect(rect, Themes.band_color(band), true)
		var kinds: Variant = _hazards.get(location.location_id, [])
		for kind in kinds:
			draw_rect(rect, Themes.hazard_color(kind), true)
		if _depleted.has(location.location_id):
			draw_rect(rect, Themes.DEPLETED, false, 3.0)
		elif _scarce.has(location.location_id):
			draw_rect(rect, Themes.SCARCE, false, 2.0)
		draw_rect(rect, color, false, 2.0)
		var label := str(location.display_name) if str(location.display_name) != "" else str(location.name)
		var text_size := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
		var text_pos := rect.position + Vector2(
			maxf(8.0, (rect.size.x - text_size.x) * 0.5),
			18.0,
		)
		draw_string(font, text_pos, label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0.96, 0.95, 0.92))


func _rect_for(location: Variant) -> Rect2:
	var presentation = location.presentation
	if presentation != null and presentation.visual_bounds != null:
		var bounds = presentation.visual_bounds
		var origin := Scale.to_pixels(bounds.x, bounds.y)
		var size := Scale.to_pixels(bounds.width, bounds.height)
		return Rect2(origin, size)
	var center := _fallback_center(location)
	var size := Scale.to_pixels(48.0, 32.0)
	return Rect2(center - size * 0.5, size)


func _fallback_center(location: Variant) -> Vector2:
	var presentation = location.presentation
	if presentation != null and presentation.screen_position != null:
		var point = presentation.screen_position
		return Scale.to_pixels(point.x, point.y)
	var layout: Vector2 = _rings.get(location.location_id, Vector2.ZERO)
	return Scale.to_pixels(layout.x, layout.y)


func _ring_positions() -> Dictionary:
	var missing: Array[String] = []
	for location in _locations:
		var presentation = location.presentation
		var has_bounds := presentation != null and presentation.visual_bounds != null
		var has_screen := presentation != null and presentation.screen_position != null
		if not has_bounds and not has_screen:
			missing.append(location.location_id)
			ObserverLog.warn(
				"locations",
				"layout_position_missing location_id=%s" % location.location_id,
			)
	missing.sort()
	var rings := {}
	if missing.is_empty():
		return rings
	for index in missing.size():
		var angle := TAU * float(index) / float(missing.size())
		rings[missing[index]] = Vector2(cos(angle), sin(angle)) * 160.0
	return rings
