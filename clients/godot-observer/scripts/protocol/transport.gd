extends RefCounted
class_name ObserverTransport

const ObserverLog := preload("res://scripts/log.gd")

const MODE_LIVE := "LIVE"
const MODE_REPLAY := "REPLAY"
const SPEEDS: Array[float] = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
const WHOLE_TICK_SPEED := 8.0

var run_id: String = ""
var tick: int = 0
var sequence: Variant = null
var mode: String = MODE_LIVE
var speed: float = 1.0
var paused: bool = false
var live_tick: int = 0
var latest_tick: Variant = null
var latest_sequence: Variant = null
var behind_live: bool = false
var buffer_dropped: bool = false


func set_cursor(
	next_mode: String,
	next_tick: int,
	next_sequence: Variant,
	next_speed: float,
	next_paused: bool,
) -> void:
	mode = next_mode
	tick = next_tick
	sequence = next_sequence
	if accepts_speed(next_speed):
		speed = next_speed
	paused = next_paused
	sync_behind()
	_log_cursor()


func view_event(after_tick: Variant, after_sequence: Variant) -> void:
	if after_tick == null:
		sequence = null
	else:
		tick = int(after_tick)
		sequence = null if after_sequence == null else int(after_sequence)
	sync_behind()
	_log_cursor()


func set_speed(next_speed: float) -> bool:
	if not accepts_speed(next_speed):
		return false
	speed = next_speed
	_log_cursor()
	return true


func set_paused(next_paused: bool) -> void:
	paused = next_paused
	_log_cursor()


func set_mode(next_mode: String) -> void:
	mode = next_mode
	_log_cursor()


func note_run_head(head_tick: int, head_latest_tick: Variant, head_latest_sequence: Variant) -> void:
	live_tick = head_tick
	latest_tick = head_latest_tick
	latest_sequence = head_latest_sequence
	sync_behind()


func mark_buffer_dropped() -> void:
	buffer_dropped = true
	behind_live = true


func clear_behind() -> void:
	buffer_dropped = false
	behind_live = false


func sync_behind() -> void:
	behind_live = buffer_dropped or is_behind(tick, sequence, latest_tick, latest_sequence)


static func accepts_speed(value: float) -> bool:
	for known in SPEEDS:
		if is_equal_approx(value, known):
			return true
	return false


static func is_behind(
	view_tick: int,
	view_sequence: Variant,
	head_tick: Variant,
	head_sequence: Variant,
) -> bool:
	if head_tick == null or head_sequence == null:
		return false
	if view_sequence == null:
		return true
	if view_tick < int(head_tick):
		return true
	if view_tick == int(head_tick) and int(view_sequence) < int(head_sequence):
		return true
	return false


static func previous_event(
	view_tick: int,
	view_sequence: Variant,
	previous_tick: Variant,
	previous_last_sequence: Variant,
) -> Dictionary:
	if view_sequence == null:
		return _missing()
	if int(view_sequence) > 0:
		return _found(view_tick, int(view_sequence) - 1)
	if previous_tick == null or previous_last_sequence == null:
		return _missing()
	return _found(int(previous_tick), int(previous_last_sequence))


static func next_event(
	view_tick: int,
	view_sequence: Variant,
	tick_last_sequence: Variant,
	next_tick: Variant,
	next_first_sequence: Variant,
) -> Dictionary:
	if view_sequence == null:
		if next_tick == null or next_first_sequence == null:
			return _missing()
		return _found(int(next_tick), int(next_first_sequence))
	if tick_last_sequence != null and int(view_sequence) < int(tick_last_sequence):
		return _found(view_tick, int(view_sequence) + 1)
	if next_tick == null or next_first_sequence == null:
		return _missing()
	return _found(int(next_tick), int(next_first_sequence))


static func previous_tick(previous_tick_value: Variant, previous_last_sequence: Variant) -> Dictionary:
	if previous_tick_value == null or previous_last_sequence == null:
		return _missing()
	return _found(int(previous_tick_value), int(previous_last_sequence))


static func next_tick(next_tick_value: Variant, next_last_sequence: Variant) -> Dictionary:
	if next_tick_value == null or next_last_sequence == null:
		return _missing()
	return _found(int(next_tick_value), int(next_last_sequence))


static func live_head(head_tick: Variant, head_sequence: Variant) -> Dictionary:
	if head_tick == null or head_sequence == null:
		return _missing()
	return _found(int(head_tick), int(head_sequence))


static func step_target(
	play_speed: float,
	view_tick: int,
	view_sequence: Variant,
	tick_last_sequence: Variant,
	next_tick_value: Variant,
	next_first_sequence: Variant,
	next_last_sequence: Variant,
) -> Dictionary:
	if play_speed >= WHOLE_TICK_SPEED:
		return next_tick(next_tick_value, next_last_sequence)
	return next_event(
		view_tick,
		view_sequence,
		tick_last_sequence,
		next_tick_value,
		next_first_sequence,
	)


func _log_cursor() -> void:
	var sequence_text := "null" if sequence == null else str(int(sequence))
	ObserverLog.debug(
		"transport",
		"cursor_set mode=%s tick=%s sequence=%s speed=%s paused=%s"
		% [mode, tick, sequence_text, speed, paused],
	)


static func _found(event_tick: int, event_sequence: int) -> Dictionary:
	return {"found": true, "tick": event_tick, "sequence": event_sequence}


static func _missing() -> Dictionary:
	return {"found": false, "tick": null, "sequence": null}
