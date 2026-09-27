extends RefCounted
class_name ObserverPlayback

const ObserverLog := preload("res://scripts/log.gd")

const MOTION_SECONDS := 0.6
const SPEECH_SECONDS := 2.0
const SNAP_SPEED := 8.0
const SNAP_PENDING := 3


static func policy(speed: float, pending: int) -> Dictionary:
	var skip := speed >= SNAP_SPEED or pending > SNAP_PENDING
	if skip:
		ObserverLog.debug(
			"playback",
			"motion_skipped speed=%s pending=%s" % [speed, pending],
		)
	var divisor := speed if speed > 0.0 else 1.0
	return {
		"skip": skip,
		"duration": 0.0 if skip else MOTION_SECONDS / divisor,
		"speech_duration": 0.0 if skip else SPEECH_SECONDS / divisor,
		"speed": speed,
		"pending": pending,
	}
