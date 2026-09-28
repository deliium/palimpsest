extends RefCounted

const Playback := preload("res://scripts/protocol/playback.gd")


func run() -> Array:
	var failures: Array = []
	var normal: Dictionary = Playback.policy(1.0, 0)
	if normal["skip"] or not is_equal_approx(float(normal["duration"]), 0.6):
		failures.append("speed 1 motion duration")
	if not is_equal_approx(float(normal["speech_duration"]), 2.0):
		failures.append("speed 1 speech duration")
	var faster: Dictionary = Playback.policy(2.0, 1)
	if faster["skip"] or not is_equal_approx(float(faster["duration"]), 0.3):
		failures.append("higher speed should shorten the tween")
	var snapped: Dictionary = Playback.policy(8.0, 0)
	if not snapped["skip"]:
		failures.append("speed 8 should skip")
	var crowded: Dictionary = Playback.policy(1.0, 4)
	if not crowded["skip"]:
		failures.append("pending above 3 should skip")
	var held: Dictionary = Playback.policy(1.0, 3)
	if held["skip"]:
		failures.append("three pending motions should still play")
	var slow: Dictionary = Playback.policy(0.25, 0)
	if slow["skip"] or not is_equal_approx(float(slow["duration"]), 2.4):
		failures.append("speed 0.25 should lengthen the tween")
	if not is_equal_approx(float(slow["speech_duration"]), 8.0):
		failures.append("speed 0.25 should lengthen speech")
	var half: Dictionary = Playback.policy(0.5, 0)
	if half["skip"] or not is_equal_approx(float(half["duration"]), 1.2):
		failures.append("speed 0.5 should lengthen the tween")
	var sixteen: Dictionary = Playback.policy(16.0, 0)
	if not sixteen["skip"] or float(sixteen["duration"]) != 0.0:
		failures.append("speed 16 should skip")
	return failures
