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
	if str(normal.get("lod", "")) != "full" or not bool(normal.get("trails", false)):
		failures.append("speed 1 should keep full detail and trails")
	var reduced: Dictionary = Playback.policy(4.0, 0)
	if str(reduced.get("lod", "")) != "reduced" or reduced["skip"]:
		failures.append("speed 4 should reduce detail without snapping")
	if bool(reduced.get("trails", true)) or int(reduced.get("transient_cap", 0)) != 32:
		failures.append("speed 4 should drop trails and cap transients")
	var snap: Dictionary = Playback.policy(8.0, 0)
	if str(snap.get("lod", "")) != "snap" or int(snap.get("transient_cap", -1)) != 0:
		failures.append("speed 8 should snap transitions")
	if str(sixteen.get("lod", "")) != "aggregate" or not bool(sixteen.get("aggregate_labels", false)):
		failures.append("speed 16 should aggregate labels")
	if bool(sixteen.get("individual_labels", true)):
		failures.append("speed 16 should hide individual labels")
	var kept: Array = Playback.coalesce_tick_envelopes([1, 2, 3, 4], 8.0, 0)
	if kept.size() != 1 or kept[0] != 4:
		failures.append("high-speed should coalesce to latest tick envelope")
	var full: Array = Playback.coalesce_tick_envelopes([1, 2, 3], 1.0, 0)
	if full.size() != 3:
		failures.append("normal speed should keep all tick envelopes")
	return failures
