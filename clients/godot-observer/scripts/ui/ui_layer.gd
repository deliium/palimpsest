extends CanvasLayer

const ObserverLog := preload("res://scripts/log.gd")

signal connect_requested(run_id: String)
signal zoom_in_requested
signal zoom_out_requested
signal reset_requested
signal focus_requested
signal speed_changed(speed: float)
signal speed_selected(speed: float)
signal control_pressed(action: String)
signal event_seek_requested(tick: int, sequence: int)
signal timeline_seek_requested(tick: int, sequence: int)
signal play_fixture_requested
signal perspective_requested(agent_id: String)
signal labels_cleared
signal overlay_toggled(kind: String, evidence_class: String, enabled: bool)
signal narrative_variant_selected(variant_id: String)
signal explain_requested(tick: int, sequence: int, event_id: String)
signal debugger_focus_requested(tick: int, sequence: int, event_id: String)
signal debugger_provenance_requested(lineage_kind: String, subject_id: String, owner_id: String)

var _live_tick := 0
var _selected_id := ""


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)
	$StatusBar.connect_requested.connect(func(run_id: String) -> void:
		connect_requested.emit(run_id)
	)
	$PerspectiveControl.perspective_requested.connect(func(agent_id: String) -> void:
		perspective_requested.emit(agent_id)
	)
	$PerspectiveControl.labels_cleared.connect(func() -> void:
		labels_cleared.emit()
	)
	$OverlayLegend.overlay_toggled.connect(func(kind: String, evidence_class: String, enabled: bool) -> void:
		overlay_toggled.emit(kind, evidence_class, enabled)
	)
	$NarrativeSelector.variant_selected.connect(func(variant_id: String) -> void:
		narrative_variant_selected.emit(variant_id)
	)
	$Controls/ZoomIn.pressed.connect(func() -> void: zoom_in_requested.emit())
	$Controls/ZoomOut.pressed.connect(func() -> void: zoom_out_requested.emit())
	$Controls/Reset.pressed.connect(func() -> void: reset_requested.emit())
	$Controls/Focus.pressed.connect(func() -> void: focus_requested.emit())
	$Controls/Speed1.pressed.connect(func() -> void: _select_speed(1.0))
	$Controls/Speed2.pressed.connect(func() -> void: _select_speed(2.0))
	$Controls/Speed4.pressed.connect(func() -> void: _select_speed(4.0))
	$Controls/Speed8.pressed.connect(func() -> void: _select_speed(8.0))
	$Controls/PlayFixture.pressed.connect(func() -> void: play_fixture_requested.emit())
	$Playback/Play.pressed.connect(func() -> void: _press("play"))
	$Playback/Pause.pressed.connect(func() -> void: _press("pause"))
	$Playback/PreviousEvent.pressed.connect(func() -> void: _press("previous_event"))
	$Playback/NextEvent.pressed.connect(func() -> void: _press("next_event"))
	$Playback/PreviousTick.pressed.connect(func() -> void: _press("previous_tick"))
	$Playback/NextTick.pressed.connect(func() -> void: _press("next_tick"))
	$Playback/JumpToTick.pressed.connect(func() -> void: _press("jump_tick"))
	$Playback/JumpToEvent.pressed.connect(func() -> void: _press("jump_event"))
	$Playback/ReturnToLive.pressed.connect(func() -> void: _press("return_live"))
	$Playback/SpeedQuarter.pressed.connect(func() -> void: _select_speed(0.25))
	$Playback/SpeedHalf.pressed.connect(func() -> void: _select_speed(0.5))
	$Playback/Speed1.pressed.connect(func() -> void: _select_speed(1.0))
	$Playback/Speed2.pressed.connect(func() -> void: _select_speed(2.0))
	$Playback/Speed4.pressed.connect(func() -> void: _select_speed(4.0))
	$Playback/Speed8.pressed.connect(func() -> void: _select_speed(8.0))
	$Playback/Speed16.pressed.connect(func() -> void: _select_speed(16.0))
	$EventLog.seek_requested.connect(func(tick: int, sequence: int) -> void:
		event_seek_requested.emit(tick, sequence)
	)
	$EventLog.explain_requested.connect(func(tick: int, sequence: int, event_id: String) -> void:
		explain_requested.emit(tick, sequence, event_id)
	)
	$Timeline.seek_requested.connect(func(tick: int, sequence: int) -> void:
		timeline_seek_requested.emit(tick, sequence)
	)
	var debugger = $DebuggerPanel
	if debugger != null and debugger.has_signal("focus_requested"):
		debugger.focus_requested.connect(func(tick: int, sequence: int, event_id: String) -> void:
			debugger_focus_requested.emit(tick, sequence, event_id)
		)
	if debugger != null and debugger.has_signal("provenance_requested"):
		debugger.provenance_requested.connect(
			func(lineage_kind: String, subject_id: String, owner_id: String) -> void:
				debugger_provenance_requested.emit(lineage_kind, subject_id, owner_id)
		)


func jump_tick_value() -> int:
	return int($Playback/JumpTick.value)


func jump_sequence_value() -> int:
	return int($Playback/JumpSequence.value)


func _press(action: String) -> void:
	ObserverLog.debug("ui", "control_pressed action=%s" % action)
	control_pressed.emit(action)


func _select_speed(speed: float) -> void:
	ObserverLog.debug("ui", "speed_selected speed=%s" % speed)
	speed_changed.emit(speed)
	speed_selected.emit(speed)


func set_run_id(value: String) -> void:
	$StatusBar.set_run_id(value)


func show_status(code: String, detail: String) -> void:
	$StatusBar.show_state(code, detail)


func append_event(event: Variant) -> void:
	$EventLog.append_event(event)


func replace_events(events: Array, focus_tick: int, focus_sequence: int, world: Variant) -> void:
	$EventLog.set_world(world)
	$EventLog.replace_window(events, focus_tick, focus_sequence)
	$Timeline.set_window(events, focus_tick, _live_tick, _selected_id)


func note_live_tick(live_tick: int) -> void:
	_live_tick = live_tick
	$Timeline.set_live_tick(live_tick)


func note_selection(entity_id: String) -> void:
	_selected_id = entity_id
	$Timeline.set_selected(entity_id)


func show_inspector(snapshot: Dictionary) -> void:
	$Inspector.show_agent(snapshot)


func clear_inspector() -> void:
	$Inspector.clear_agent()


func is_overlay_enabled(kind: String) -> bool:
	return $OverlayLegend.is_overlay_enabled(kind)


func set_overlay_enabled(kind: String, enabled: bool) -> void:
	$OverlayLegend.set_overlay_enabled(kind, enabled)


func set_narrative_variants(ids: Array) -> void:
	$NarrativeSelector.set_variants(ids)


func clear_narrative_variants() -> void:
	$NarrativeSelector.clear_variants()
	$EventLog.clear_event_focus()


func focus_narrative_event_ids(event_ids: Array) -> void:
	$EventLog.focus_event_ids(event_ids)


func open_debugger_payload(payload: Dictionary) -> void:
	$DebuggerPanel.open_payload(payload)


func open_debugger_lineage(payload: Dictionary) -> void:
	$DebuggerPanel.open_lineage_payload(payload)


func show_debugger_unavailable(reason_code: String) -> void:
	$DebuggerPanel.show_unavailable(reason_code)


func show_debugger_lineage_unavailable(reason_code: String) -> void:
	$DebuggerPanel.show_lineage_unavailable(reason_code)


func close_debugger() -> void:
	$DebuggerPanel.close_panel()
