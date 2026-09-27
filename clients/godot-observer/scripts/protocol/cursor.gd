extends RefCounted
class_name ObserverCursor

const ObserverLog := preload("res://scripts/log.gd")

## Resume order is (tick, sequence) with a strict greater-than check.


static func is_strictly_after(tick: int, sequence: int, after_tick: Variant, after_sequence: Variant) -> bool:
	if after_tick == null or after_sequence == null:
		return true
	var cursor_tick := int(after_tick)
	var cursor_sequence := int(after_sequence)
	if tick > cursor_tick:
		return true
	if tick == cursor_tick and sequence > cursor_sequence:
		return true
	return false


static func consider(tick: int, sequence: int, after_tick: Variant, after_sequence: Variant) -> Dictionary:
	if not is_strictly_after(tick, sequence, after_tick, after_sequence):
		ObserverLog.debug("protocol", "event_skipped reason_code=stale_cursor")
		return {
			"applied": false,
			"reason_code": "stale_cursor",
			"after_tick": after_tick,
			"after_sequence": after_sequence,
		}
	ObserverLog.debug("protocol", "cursor_applied tick=%s sequence=%s" % [tick, sequence])
	return {
		"applied": true,
		"reason_code": "",
		"after_tick": tick,
		"after_sequence": sequence,
	}
