extends RefCounted
class_name ObserverPlayback

const ObserverLog := preload("res://scripts/log.gd")

const MOTION_SECONDS := 0.6
const SPEECH_SECONDS := 2.0
const REDUCED_SPEED := 4.0
const SNAP_SPEED := 8.0
const AGGREGATE_SPEED := 16.0
const SNAP_PENDING := 3
const REDUCED_TRANSIENT_CAP := 32


static func level_of_detail(speed: float) -> String:
	if speed >= AGGREGATE_SPEED:
		return "aggregate"
	if speed >= SNAP_SPEED:
		return "snap"
	if speed >= REDUCED_SPEED:
		return "reduced"
	return "full"


static func policy(speed: float, pending: int) -> Dictionary:
	var lod := level_of_detail(speed)
	var skip := speed >= SNAP_SPEED or pending > SNAP_PENDING
	if skip:
		ObserverLog.debug(
			"playback",
			"motion_skipped speed=%s pending=%s lod=%s" % [speed, pending, lod],
		)
	var divisor := speed if speed > 0.0 else 1.0
	return {
		"skip": skip,
		"duration": 0.0 if skip else MOTION_SECONDS / divisor,
		"speech_duration": 0.0 if skip else SPEECH_SECONDS / divisor,
		"speed": speed,
		"pending": pending,
		"lod": lod,
		"trails": lod == "full",
		"transient_cap": 0 if skip else REDUCED_TRANSIENT_CAP,
		"individual_labels": lod != "aggregate",
		"aggregate_labels": lod == "aggregate",
		"effects": not skip,
	}


## Presentation-only: drop intermediate tick envelopes when high-speed skip is on.
## Scientific event pages / WS journal stay complete and uncoalesced.
static func coalesce_tick_envelopes(ticks: Array, speed: float, pending: int) -> Array:
	var rules: Dictionary = policy(speed, pending)
	if not bool(rules.get("skip", false)) or ticks.size() <= 1:
		return ticks
	var kept: Array = [ticks[ticks.size() - 1]]
	var skipped := ticks.size() - 1
	ObserverLog.debug(
		"playback",
		"[observer.playback] presentation_coalesced skipped=%s" % skipped,
	)
	return kept
