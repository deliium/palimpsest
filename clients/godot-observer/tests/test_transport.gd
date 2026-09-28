extends RefCounted

const Transport := preload("res://scripts/protocol/transport.gd")


func run() -> Array:
	var failures: Array = []
	var cursor := Transport.new()
	cursor.run_id = "run-1"
	cursor.set_cursor(Transport.MODE_REPLAY, 4, 2, 1.0, false)
	if cursor.tick != 4 or cursor.sequence != 2:
		failures.append("viewed pair should be the event, not the engine tick")
	cursor.view_event(7, 1)
	if cursor.tick != 7 or int(cursor.sequence) != 1:
		failures.append("view_event should store after_tick and after_sequence")
	var inside: Dictionary = Transport.next_event(4, 1, 3, 5, 0)
	if not inside["found"] or inside["tick"] != 4 or inside["sequence"] != 2:
		failures.append("next event inside a tick is sequence + 1")
	var back: Dictionary = Transport.previous_event(4, 2, 3, 4)
	if not back["found"] or back["tick"] != 4 or back["sequence"] != 1:
		failures.append("previous event above sequence 0 is sequence - 1")
	var boundary: Dictionary = Transport.previous_event(4, 0, 3, 4)
	if not boundary["found"] or boundary["tick"] != 3 or boundary["sequence"] != 4:
		failures.append("sequence 0 uses the previous tick last_sequence")
	var first: Dictionary = Transport.previous_event(0, 0, null, null)
	if first["found"]:
		failures.append("previous event at the first event must not wrap")
	var last: Dictionary = Transport.next_event(9, 2, 2, null, null)
	if last["found"]:
		failures.append("next event at the latest event must not be invented")
	var next_tick: Dictionary = Transport.next_tick(5, 3)
	if not next_tick["found"] or next_tick["tick"] != 5 or next_tick["sequence"] != 3:
		failures.append("next tick lands on the last event")
	var previous_tick: Dictionary = Transport.previous_tick(2, 1)
	if not previous_tick["found"] or previous_tick["sequence"] != 1:
		failures.append("previous tick lands on the last event")
	var head: Dictionary = Transport.live_head(8, 0)
	if not head["found"] or head["tick"] != 8 or head["sequence"] != 0:
		failures.append("live head is the latest event pair")
	var one: Dictionary = Transport.step_target(1.0, 4, 1, 3, 5, 0, 2)
	if one["tick"] != 4 or one["sequence"] != 2:
		failures.append("speed below 8 steps one event")
	var whole: Dictionary = Transport.step_target(8.0, 4, 1, 3, 5, 0, 2)
	if whole["tick"] != 5 or whole["sequence"] != 2:
		failures.append("speed 8 steps to the last event of the next tick")
	var sixteen: Dictionary = Transport.step_target(16.0, 4, 1, 3, 5, 0, 2)
	if sixteen["tick"] != 5 or sixteen["sequence"] != 2:
		failures.append("speed 16 uses the same whole-tick step")
	if not Transport.accepts_speed(0.25) or not Transport.accepts_speed(0.5):
		failures.append("speed table should accept 0.25 and 0.5")
	if cursor.set_speed(3.0):
		failures.append("unknown speed should be rejected")
	if not cursor.set_speed(0.5) or not is_equal_approx(cursor.speed, 0.5):
		failures.append("known speed should be stored locally")
	cursor.note_run_head(9, 8, 1)
	cursor.view_event(8, 0)
	if not cursor.behind_live:
		failures.append("a viewed event behind the latest pair is behind live")
	cursor.view_event(8, 1)
	if cursor.behind_live:
		failures.append("the latest event is not behind live")
	return failures
