extends CanvasLayer

const ObserverLog := preload("res://scripts/log.gd")

signal credentials_apply_requested(inspection_token: String, debug_token: String)
signal credentials_forget_requested
signal population_toggled(enabled: bool)
signal demographic_section_selected(section: String)
signal demographic_load_more_requested
signal generational_agent_selected(agent_id: String)
signal lineage_tab_selected(tab: String)
signal lineage_entry_selected(kind: String, native_kind: String, ref_id: String)
signal lineage_back_requested
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
signal return_previous_run_requested
signal open_parent_branch_requested
signal open_child_branch_requested(child_run_id: String, fork_tick: int)
signal load_more_branches_requested
signal location_focus_requested(location_id: String)
signal follow_agent_requested(enabled: bool)
signal follow_location_requested(enabled: bool)
signal focused_prev_requested
signal focused_next_requested
signal bookmark_add_requested(note: String)
signal bookmark_jump_requested(tick: int, sequence: Variant)
signal bookmark_delete_requested(index: int)
signal bookmark_edit_requested(index: int, note: String)

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
	var perspective = $PerspectiveControl
	if perspective.has_signal("location_focus_requested"):
		perspective.location_focus_requested.connect(func(location_id: String) -> void:
			location_focus_requested.emit(location_id)
		)
	if perspective.has_signal("follow_agent_requested"):
		perspective.follow_agent_requested.connect(func(enabled: bool) -> void:
			follow_agent_requested.emit(enabled)
		)
	if perspective.has_signal("follow_location_requested"):
		perspective.follow_location_requested.connect(func(enabled: bool) -> void:
			follow_location_requested.emit(enabled)
		)
	if perspective.has_signal("focused_prev_requested"):
		perspective.focused_prev_requested.connect(func() -> void: focused_prev_requested.emit())
	if perspective.has_signal("focused_next_requested"):
		perspective.focused_next_requested.connect(func() -> void: focused_next_requested.emit())
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
	var branch = $BranchPanel
	if branch != null:
		branch.return_requested.connect(func() -> void: return_previous_run_requested.emit())
		branch.open_parent_requested.connect(func() -> void: open_parent_branch_requested.emit())
		branch.open_child_requested.connect(
			func(child_run_id: String, fork_tick: int) -> void:
				open_child_branch_requested.emit(child_run_id, fork_tick)
		)
		branch.load_more_children_requested.connect(func() -> void: load_more_branches_requested.emit())
	var generational = get_node_or_null("GenerationalPanel")
	if generational != null:
		generational.population_toggled.connect(
			func(enabled: bool) -> void: population_toggled.emit(enabled)
		)
		generational.section_selected.connect(
			func(section: String) -> void: demographic_section_selected.emit(section)
		)
		generational.load_more_requested.connect(
			func() -> void: demographic_load_more_requested.emit()
		)
		generational.agent_selected.connect(
			func(agent_id: String) -> void: generational_agent_selected.emit(agent_id)
		)
		generational.lineage_tab_selected.connect(
			func(tab: String) -> void: lineage_tab_selected.emit(tab)
		)
		generational.lineage_entry_selected.connect(
			func(kind: String, native_kind: String, ref_id: String) -> void:
				lineage_entry_selected.emit(kind, native_kind, ref_id)
		)
		generational.back_requested.connect(
			func() -> void: lineage_back_requested.emit()
		)
	var credentials = get_node_or_null("CredentialsPanel")
	if credentials != null:
		credentials.apply_requested.connect(
			func(inspection_token: String, debug_token: String) -> void:
				credentials_apply_requested.emit(inspection_token, debug_token)
		)
		credentials.forget_requested.connect(
			func() -> void: credentials_forget_requested.emit()
		)
	var bookmarks = $BookmarksPanel
	if bookmarks != null:
		bookmarks.add_requested.connect(func(note: String) -> void: bookmark_add_requested.emit(note))
		bookmarks.jump_requested.connect(func(tick: int, sequence: Variant) -> void:
			bookmark_jump_requested.emit(tick, sequence)
		)
		bookmarks.delete_requested.connect(func(index: int) -> void: bookmark_delete_requested.emit(index))
		bookmarks.edit_requested.connect(func(index: int, note: String) -> void:
			bookmark_edit_requested.emit(index, note)
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


func set_filters_from_focus(agent_id: String, location_id: String) -> void:
	$EventLog.set_filters(agent_id, "", location_id)


func replace_events(events: Array, focus_tick: int, focus_sequence: int, world: Variant) -> void:
	$EventLog.set_world(world)
	$EventLog.replace_window(events, focus_tick, focus_sequence)
	$Timeline.set_window(events, focus_tick, _live_tick, _selected_id)


func set_marker_enrichment(events: Array) -> void:
	$Timeline.set_enriched_events(events)


func set_branch_marks(ticks: Array) -> void:
	$Timeline.set_branch_points(ticks)


func marker_enrichment_types(budget: int = 3) -> Array:
	return $Timeline.enabled_enrichment_types(budget)


func note_live_tick(live_tick: int) -> void:
	_live_tick = live_tick
	$Timeline.set_live_tick(live_tick)


func note_selection(entity_id: String) -> void:
	_selected_id = entity_id
	$Timeline.set_selected(entity_id)
	var perspective = $PerspectiveControl
	if perspective != null and perspective.has_method("set_agent_id"):
		perspective.set_agent_id(entity_id)


func note_location_focus(location_id: String) -> void:
	var perspective = $PerspectiveControl
	if perspective != null and perspective.has_method("set_location_id"):
		perspective.set_location_id(location_id)


func note_follow(mode: String) -> void:
	var perspective = $PerspectiveControl
	if perspective == null:
		return
	if perspective.has_method("set_follow_agent"):
		perspective.set_follow_agent(mode == "agent")
	if perspective.has_method("set_follow_location"):
		perspective.set_follow_location(mode == "location")


func show_inspector(snapshot: Dictionary) -> void:
	$Inspector.show_agent(snapshot)


func clear_inspector() -> void:
	$Inspector.clear_agent()


func clear_for_source_switch() -> void:
	## Clear presentation chrome for a new ObserverSource. Bookmark files stay.
	$EventLog.replace_window([], 0, 0)
	$Timeline.clear_marks()
	clear_inspector()
	clear_narrative_variants()
	note_selection("")
	close_debugger()
	var branch = $BranchPanel
	if branch != null:
		branch.set_busy(true)
	ObserverLog.debug("ui", "source_cleared")


func show_branch_panel(
	run_id: String,
	lineage: Dictionary,
	children: Array,
	next_cursor: Variant,
	reason_code: String,
	nav_depth: int,
) -> void:
	var branch = $BranchPanel
	if branch == null:
		return
	var payload := lineage.duplicate(true)
	payload["run_id"] = run_id
	branch.show_lineage(payload, children, next_cursor, reason_code, nav_depth)
	branch.set_busy(false)


func set_nav_depth(depth: int) -> void:
	var branch = $BranchPanel
	if branch != null:
		branch.set_nav_depth(depth)


func show_bookmarks(items: Array) -> void:
	var bookmarks = $BookmarksPanel
	if bookmarks != null:
		bookmarks.show_bookmarks(items)


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


func note_credentials_result(ok: bool, reason_code: String) -> void:
	var credentials = get_node_or_null("CredentialsPanel")
	if credentials != null:
		credentials.note_result(ok, reason_code)


func set_credential_state(inspection_present: bool, debug_present: bool) -> void:
	var credentials = get_node_or_null("CredentialsPanel")
	if credentials != null:
		credentials.set_present(inspection_present, debug_present)


func apply_demographics(model: Variant) -> void:
	var panel = get_node_or_null("GenerationalPanel")
	if panel != null:
		panel.apply_demographics(model)


func apply_demographic_selection(row: Variant, state: String) -> void:
	var panel = get_node_or_null("GenerationalPanel")
	if panel != null:
		panel.apply_selection(row, state)


func apply_lineage_panel(panel_name: String, data: Dictionary) -> void:
	var panel = get_node_or_null("GenerationalPanel")
	if panel != null:
		panel.apply_lineage(panel_name, data)


func set_generational_agent(agent_id: String) -> void:
	var panel = get_node_or_null("GenerationalPanel")
	if panel != null:
		panel.set_selected_agent(agent_id)


func set_generation_markers(markers: Array, run_id: String = "") -> void:
	var timeline = get_node_or_null("Timeline")
	if timeline != null and timeline.has_method("set_generation_markers"):
		timeline.set_generation_markers(markers, run_id)


func set_generational_panel_visible(value: bool) -> void:
	var panel = get_node_or_null("GenerationalPanel")
	if panel != null:
		panel.visible = value


func generational_panel_visible() -> bool:
	var panel = get_node_or_null("GenerationalPanel")
	return panel != null and panel.visible


func is_generational_overlay_enabled(kind: String) -> bool:
	var legend = get_node_or_null("OverlayLegend")
	return legend != null and bool(legend.is_overlay_enabled(kind))


func show_demographic_inspector(row: Variant) -> void:
	var inspector = get_node_or_null("Inspector")
	if inspector != null and inspector.has_method("show_demographics"):
		inspector.show_demographics(row)
