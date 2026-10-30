extends RefCounted
class_name ObserverScale


const SCALE_CONTRACT_VERSION := "observer-scale-v1"
const SCALE_LEVELS: Array[String] = [
	"agent",
	"cohort",
	"settlement",
	"region",
	"civilization",
]

# Presentation-only thresholds; mirror src/observer/scale.py exactly.
const AGENT_MAX_POPULATION := 23
const COHORT_MIN_POPULATION := 24
const COHORT_MAX_POPULATION := 199
const SETTLEMENT_MIN_POPULATION := 200
const SETTLEMENT_MAX_POPULATION := 1999
const REGION_MIN_POPULATION := 2000
const REGION_MAX_POPULATION := 19999
const CIVILIZATION_MIN_POPULATION := 20000


static func pixels_per_unit() -> float:
	var raw: Variant = ProjectSettings.get_setting("palimpsest/pixels_per_unit", 8)
	var value := float(raw)
	if value <= 0.0:
		return 8.0
	return value


static func to_pixels(x: float, y: float) -> Vector2:
	var scale := pixels_per_unit()
	return Vector2(x * scale, y * scale)


static func level_for_population(population: int) -> String:
	if population < 0:
		return "agent"
	if population <= AGENT_MAX_POPULATION:
		return "agent"
	if population <= COHORT_MAX_POPULATION:
		return "cohort"
	if population <= SETTLEMENT_MAX_POPULATION:
		return "settlement"
	if population <= REGION_MAX_POPULATION:
		return "region"
	return "civilization"
