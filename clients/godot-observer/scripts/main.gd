extends Node

const ObserverLog := preload("res://scripts/log.gd")
const FixturePlayer := preload("res://scripts/net/fixture_player.gd")
const Bookmarks := preload("res://scripts/protocol/bookmarks.gd")

@onready var _world: Node2D = $WorldView
@onready var _ui: CanvasLayer = $UILayer
@onready var _session: Node = $Session


func _ready() -> void:
	ObserverLog.start()
	ObserverLog.info("main", "client_boot renderer=gl_compatibility")
	_ensure_shortcuts()
	_session.status_changed.connect(_ui.show_status)
	_session.status_changed.connect(_on_status_changed)
	_session.world_replaced.connect(_world.show_world)
	_session.frame_sought.connect(_world.replace_sought_frame)
	_session.events_loaded.connect(_on_events_loaded)
	_session.run_loaded.connect(_on_run_loaded)
	_session.live_event.connect(_world.play_event)
	_session.live_event.connect(_ui.append_event)
	_session.source_cleared.connect(_on_source_cleared)
	_session.branch_updated.connect(_on_branch_updated)
	_session.nav_stack_changed.connect(_ui.set_nav_depth)
	_session.marker_enrichment_loaded.connect(_ui.set_marker_enrichment)
	_world.inspect_cleared.connect(_ui.clear_inspector)
	_ui.connect_requested.connect(_session.start_with_run_id)
	_session.run_id_applied.connect(_ui.set_run_id)
	_ui.zoom_in_requested.connect(_world.zoom_in)
	_ui.zoom_out_requested.connect(_world.zoom_out)
	_ui.reset_requested.connect(_world.reset_view)
	_ui.focus_requested.connect(_world.focus_selected)
	_ui.speed_changed.connect(_world.set_playback_speed)
	_ui.speed_selected.connect(_session.set_speed)
	_ui.control_pressed.connect(_on_control)
	_ui.event_seek_requested.connect(_on_event_seek)
	_ui.timeline_seek_requested.connect(_on_event_seek)
	var timeline = _ui.get_node_or_null("Timeline")
	if timeline != null and timeline.has_signal("generation_seek_requested"):
		timeline.generation_seek_requested.connect(_session.seek_tick)
	_ui.play_fixture_requested.connect(_play_fixture)
	_ui.perspective_requested.connect(_on_perspective)
	_ui.labels_cleared.connect(_on_labels_cleared)
	_ui.overlay_toggled.connect(_on_overlay_toggled)
	_ui.narrative_variant_selected.connect(_on_narrative_variant_selected)
	_ui.explain_requested.connect(_on_explain_requested)
	_ui.debugger_focus_requested.connect(_on_debugger_focus)
	_ui.debugger_provenance_requested.connect(_on_debugger_provenance)
	_ui.return_previous_run_requested.connect(_session.return_to_previous_run)
	_ui.open_parent_branch_requested.connect(_session.open_parent_at_fork)
	_ui.open_child_branch_requested.connect(_session.open_child_branch)
	_ui.load_more_branches_requested.connect(_on_load_more_branches)
	_ui.location_focus_requested.connect(_on_location_focus)
	_ui.follow_agent_requested.connect(_on_follow_agent)
	_ui.follow_location_requested.connect(_on_follow_location)
	_ui.focused_prev_requested.connect(_session.previous_focused_event)
	_ui.focused_next_requested.connect(_session.next_focused_event)
	_session.follow_changed.connect(_ui.note_follow)
	_session.follow_changed.connect(_on_follow_changed)
	_session.world_replaced.connect(_on_world_for_follow)
	_session.frame_sought.connect(_on_frame_for_follow)
	_session.live_event.connect(_on_live_for_follow)
	_session.overlay_payload.connect(_on_overlay_payload)
	_session.overlay_unavailable.connect(_on_overlay_unavailable)
	_world.inspect_requested.connect(func(snapshot: Dictionary) -> void:
		var entity_id := str(snapshot.get("entity_id", ""))
		_ui.note_selection(entity_id)
		_session.set_agent_focus(entity_id)
		var logical_agent := _agent_id_for_entity(entity_id)
		if logical_agent != "":
			_selected_agent_id = logical_agent
			_session.set_lineage_enabled(true)
			_session.select_demographic_agent(logical_agent)
			_ui.set_generational_agent(logical_agent)
		_ui.set_filters_from_focus(entity_id, _session.focus_location_id)
		snapshot["follow"] = _session.follow_mode == "agent"
		_ui.show_inspector(snapshot)
	)
	_world.inspect_cleared.connect(func() -> void:
		_ui.note_selection("")
		if _session.follow_mode == "agent":
			_session.set_follow("agent", false)
	)
	_world.location_selected.connect(_on_location_focus)
	_ui.bookmark_add_requested.connect(_on_bookmark_add)
	_ui.bookmark_jump_requested.connect(_on_bookmark_jump)
	_ui.bookmark_delete_requested.connect(_on_bookmark_delete)
	_ui.bookmark_edit_requested.connect(_on_bookmark_edit)
	_ui.credentials_apply_requested.connect(_on_credentials_apply)
	_ui.credentials_forget_requested.connect(_on_credentials_forget)
	_session.credentials_changed.connect(_ui.set_credential_state)
	_session.credentials_changed.connect(func(_inspection: bool, _debug: bool) -> void:
		_refresh_civilization_timeline_context()
		_ui.clear_civilization_timeline_private()
		_ui.refresh_civilization_timeline()
	)
	_session.credentials_error.connect(_on_credentials_error)
	_session.generational_updated.connect(_on_generational_updated)
	_session.lineage_source_updated.connect(_on_lineage_updated)
	_session.civilization_layer_changed.connect(_on_civilization_layer_changed)
	_session.civilization_bundle_ready.connect(_on_civilization_bundle)
	_session.civilization_markers_changed.connect(_on_civilization_markers)
	_session.civilization_catalogue_changed.connect(_on_civilization_catalogue)
	_session.playback_bundle_ready.connect(_on_civilization_playback_bundle)
	_session.playback_target_changed.connect(func(target: int, accepted: int, skipped: int) -> void:
		_ui.note_civilization_playback_state(accepted, target, skipped)
	)
	_session.frame_sought.connect(_on_civilization_frame_sought)
	_world.civilization_inspect_requested.connect(_ui.show_civilization_inspector)
	_ui.population_toggled.connect(_on_population_toggled)
	_ui.civilization_layer_toggled.connect(_on_civilization_layer_toggled)
	_ui.civilization_layer_mode_selected.connect(_on_civilization_mode)
	_ui.civilization_owner_changed.connect(_on_civilization_owner)
	_ui.civilization_filters_changed.connect(_on_civilization_filters)
	_ui.civilization_load_more_requested.connect(_on_civilization_load_more)
	_ui.civilization_restart_requested.connect(_on_civilization_restart)
	_ui.civilization_retry_requested.connect(_on_civilization_restart)
	_ui.civilization_layer_cleared.connect(_on_civilization_layer_cleared)
	_ui.civilization_credentials_help_requested.connect(_on_civilization_credentials_help)
	_ui.civilization_timeline_seek_requested.connect(_on_civilization_timeline_seek)
	_ui.civilization_marker_window_requested.connect(_on_civilization_marker_window)
	_ui.civilization_marker_load_more_requested.connect(_on_civilization_marker_load_more)
	_ui.civilization_catalogue_requested.connect(_on_civilization_catalogue_requested)
	_ui.civilization_catalogue_load_more_requested.connect(_on_civilization_catalogue_load_more)
	_ui.civilization_recorded_mode_changed.connect(_on_civilization_recorded_mode)
	_ui.demographic_section_selected.connect(_on_demographic_section)
	_ui.demographic_load_more_requested.connect(_on_demographic_load_more)
	_ui.generational_agent_selected.connect(_on_generational_agent)
	_ui.lineage_tab_selected.connect(_on_lineage_tab)
	_ui.lineage_entry_selected.connect(_on_lineage_entry)
	_ui.lineage_back_requested.connect(_on_lineage_back)
	if _ui.has_signal("generation_seek_requested"):
		_ui.generation_seek_requested.connect(_session.seek_tick)
	_session.run_id_applied.connect(_reload_bookmarks)
	_session.begin()


var _last_events: Array = []


func _on_events_loaded(events: Array, focus_tick: int, focus_sequence: int) -> void:
	_ui.replace_events(events, focus_tick, focus_sequence, _session.world)
	_last_events = events.duplicate()
	_world.clear_generational_transients()
	_world.apply_arrival_events(events)
	if _ui.is_generational_overlay_enabled("caregiving"):
		_world.apply_care_events(events)
	_refresh_markers()


var _timeline_initialized := false


func _on_status_changed(code: String, _detail: String) -> void:
	if code == "ready" and not _timeline_initialized:
		_timeline_initialized = true
		_refresh_civilization_timeline_context()
		_ui.refresh_civilization_timeline()


func _on_source_cleared() -> void:
	_timeline_initialized = false
	_ui.clear_civilization_timeline()
	_world.clear_world()
	_ui.clear_for_source_switch()
	_lineage_history.clear()
	_selected_agent_id = ""
	ObserverLog.debug("main", "source_cleared")


func _on_branch_updated() -> void:
	_ui.show_branch_panel(
		_session.run_id,
		_session.lineage,
		_session.branch_children,
		_session.branch_next_cursor,
		_session.branch_reason_code,
		_session.nav_stack_depth(),
	)
	_apply_branch_marks()
	_refresh_markers()


func _apply_branch_marks() -> void:
	var ticks: Array = []
	var fork_tick := int(_session.lineage.get("fork_tick", -1))
	if fork_tick >= 0 and str(_session.lineage.get("parent_run_id", "")) != "":
		ticks.append(fork_tick)
	for child in _session.branch_children:
		if typeof(child) != TYPE_DICTIONARY:
			continue
		ticks.append(int(child.get("fork_tick", 0)))
	_ui.set_branch_marks(ticks)


func _refresh_markers() -> void:
	_session.start_marker_enrichment(_ui.marker_enrichment_types(3))


func _on_load_more_branches() -> void:
	_session.fetch_branch_children(_session.branch_next_cursor)


func _on_location_focus(location_id: String) -> void:
	_session.set_location_focus(location_id)
	_ui.note_location_focus(location_id)
	_ui.set_filters_from_focus(_session.focus_agent_id, location_id)


func _on_follow_agent(enabled: bool) -> void:
	_session.set_follow("agent", enabled)
	_apply_follow_camera()


func _on_follow_location(enabled: bool) -> void:
	_session.set_follow("location", enabled)
	_apply_follow_camera()


func _on_follow_changed(_mode: String) -> void:
	_apply_follow_camera()


func _on_world_for_follow(_world_state: Variant) -> void:
	if not _session.civilization_detail.is_empty():
		_world.set_presentation_detail(_session.civilization_detail)
	_apply_follow_camera()


func _on_frame_for_follow(_frame: Variant, _event: Variant, _forward: bool) -> void:
	_apply_follow_camera()


func _on_live_for_follow(event: Variant) -> void:
	_world.apply_arrival_events([event])
	if _ui.is_generational_overlay_enabled("caregiving"):
		_world.apply_care_events([event])
	_apply_follow_camera()


func _apply_follow_camera() -> void:
	if _session.follow_mode == "agent" and _session.focus_agent_id != "":
		_world.focus_agent(_session.focus_agent_id)
	elif _session.follow_mode == "location" and _session.focus_location_id != "":
		_world.focus_location(_session.focus_location_id)


func _reload_bookmarks(_run_id: String = "") -> void:
	if _session.run_id.is_empty():
		_ui.show_bookmarks([])
		return
	_ui.show_bookmarks(Bookmarks.load_for(_session.run_id))


func _on_bookmark_add(note: String) -> void:
	if _session.run_id.is_empty():
		return
	var items := Bookmarks.add(
		_session.run_id,
		_session.transport.tick,
		_session.transport.sequence,
		note,
	)
	_ui.show_bookmarks(items)


func _on_bookmark_jump(tick: int, sequence: Variant) -> void:
	ObserverLog.info("main", "bookmark_jump tick=%s" % tick)
	if sequence == null:
		_session.jump_to_tick(tick)
	else:
		_session.jump_to_event(tick, int(sequence))


func _on_bookmark_delete(index: int) -> void:
	if _session.run_id.is_empty():
		return
	_ui.show_bookmarks(Bookmarks.remove_at(_session.run_id, index))


func _on_bookmark_edit(index: int, note: String) -> void:
	if _session.run_id.is_empty():
		return
	_ui.show_bookmarks(Bookmarks.update_note(_session.run_id, index, note))


func _ensure_shortcuts() -> void:
	_bind_key("observer_play_pause", KEY_SPACE)
	_bind_key("observer_prev_event", KEY_LEFT)
	_bind_key("observer_next_event", KEY_RIGHT)
	_bind_key("observer_prev_tick", KEY_LEFT, true)
	_bind_key("observer_next_tick", KEY_RIGHT, true)
	_bind_key("observer_live", KEY_L)
	_bind_key("observer_follow", KEY_F)
	_bind_key("observer_bookmark", KEY_B)
	_bind_key("observer_focus_prev", KEY_BRACKETLEFT)
	_bind_key("observer_focus_next", KEY_BRACKETRIGHT)
	_bind_key("observer_clear_focus", KEY_ESCAPE)


func _bind_key(action: String, keycode: Key, shift: bool = false) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action)
	var event := InputEventKey.new()
	event.keycode = keycode
	event.shift_pressed = shift
	InputMap.action_add_event(action, event)


func _unhandled_input(event: InputEvent) -> void:
	if _text_field_focused():
		return
	if event.is_action_pressed("observer_play_pause"):
		_shortcut("play_pause")
		if _session.transport.paused:
			_session.play()
		else:
			_session.pause()
	elif event.is_action_pressed("observer_prev_event"):
		_shortcut("previous_event")
		_session.previous_event()
	elif event.is_action_pressed("observer_next_event"):
		_shortcut("next_event")
		_session.next_event()
	elif event.is_action_pressed("observer_prev_tick"):
		_shortcut("previous_tick")
		_session.previous_tick()
	elif event.is_action_pressed("observer_next_tick"):
		_shortcut("next_tick")
		_session.next_tick()
	elif event.is_action_pressed("observer_live"):
		_shortcut("return_live")
		_session.return_to_live()
	elif event.is_action_pressed("observer_follow"):
		_shortcut("follow_toggle")
		_session.toggle_follow_agent()
	elif event.is_action_pressed("observer_bookmark"):
		_shortcut("bookmark")
		_on_bookmark_add("")
	elif event.is_action_pressed("observer_focus_prev"):
		_shortcut("focus_prev")
		_session.previous_focused_event()
	elif event.is_action_pressed("observer_focus_next"):
		_shortcut("focus_next")
		_session.next_focused_event()
	elif event.is_action_pressed("observer_clear_focus"):
		_shortcut("clear_focus")
		_session.clear_focus()
		_session.set_follow("", false)
		_ui.note_selection("")


func _shortcut(action: String) -> void:
	ObserverLog.debug("main", "shortcut action=%s" % action)
	get_viewport().set_input_as_handled()


func _text_field_focused() -> bool:
	var focused := get_viewport().gui_get_focus_owner()
	return focused is LineEdit or focused is TextEdit or focused is SpinBox


func _on_run_loaded(record: Dictionary) -> void:
	_ui.note_live_tick(int(record.get("tick", 0)))
	_ui.note_civilization_timeline_tick(_session.transport.tick, int(record.get("tick", 0)))
	if not _timeline_initialized:
		_timeline_initialized = true
		_refresh_civilization_timeline_context()
		_ui.refresh_civilization_timeline()


func _on_event_seek(tick: int, sequence: int) -> void:
	_session.seek_event(tick, sequence, null)


func _on_control(action: String) -> void:
	match action:
		"play":
			_world.set_playback_paused(false)
			_session.play()
		"pause":
			_session.pause()
			_world.set_playback_paused(true)
		"previous_event":
			_session.previous_event()
		"next_event":
			_session.next_event()
		"previous_tick":
			_session.previous_tick()
		"next_tick":
			_session.next_tick()
		"jump_tick":
			_session.jump_to_tick(_ui.jump_tick_value())
		"jump_event":
			_session.jump_to_event(_ui.jump_tick_value(), _ui.jump_sequence_value())
		"return_live":
			_session.return_to_live()


func _play_fixture() -> void:
	FixturePlayer.play_into(_world, _ui.get_node("EventLog"))


func _perspective_agent_id() -> String:
	var control = _ui.get_node_or_null("PerspectiveControl")
	if control == null or not control.has_method("agent_id"):
		return ""
	return str(control.agent_id())


func _on_perspective(agent_id: String) -> void:
	ObserverLog.info("main", "perspective_entered agent_id=%s" % agent_id)
	_session.request_label_overlay(agent_id)
	if _ui.is_overlay_enabled("relationships"):
		_session.request_relationship_overlay(agent_id)
	if _ui.is_overlay_enabled("territorial_claims"):
		_session.request_claim_overlay(agent_id)
	if _ui.is_overlay_enabled("narrative_hops"):
		_session.request_narrative_hop_overlay(agent_id)


func _on_labels_cleared() -> void:
	ObserverLog.info("main", "perspective_cleared")
	_world.clear_subjective_overlays()
	_ui.clear_narrative_variants()


func _on_narrative_variant_selected(variant_id: String) -> void:
	if variant_id == "":
		_ui.focus_narrative_event_ids([])
		return
	_world.select_narrative_variant(variant_id)
	var opaque: Array = _world.narrative_opaque_event_ids()
	_ui.focus_narrative_event_ids(opaque)
	ObserverLog.debug(
		"main",
		"narrative_log_focus variant_id=%s opaque_event_count=%s" % [variant_id, opaque.size()],
	)


func _on_overlay_toggled(kind: String, evidence_class: String, enabled: bool) -> void:
	if kind == "population":
		_ui.set_generational_panel_visible(enabled)
		_session.set_demographics_enabled(enabled)
		_session.set_generation_markers_enabled(enabled)
	if kind == "generation":
		_session.set_generation_markers_enabled(enabled)
		if not enabled:
			_ui.set_generation_markers([])
	if kind in ["generation", "cohort", "age_stage"]:
		var kinds: Array = []
		for candidate in ["generation", "cohort", "age_stage"]:
			if _ui.is_generational_overlay_enabled(candidate):
				kinds.append(candidate)
		_world.apply_demographics(_session.generational.model_view, kinds)
	if kind == "kinship" or kind in ["mentorship_subjective", "mentorship_analytical"]:
		_world.set_generational_overlay_enabled(kind, enabled)
		if not enabled:
			_world.apply_generational_links([])
		else:
			_apply_lineage_links()
	if kind == "caregiving":
		_world.set_generational_overlay_enabled(kind, enabled)
		if enabled:
			_world.apply_care_events(_last_events)
		else:
			_world.apply_care_events([])
	ObserverLog.debug(
		"main",
		"overlay_toggled kind=%s evidence_class=%s enabled=%s" % [kind, evidence_class, enabled],
	)
	var agent_id := _perspective_agent_id()
	match kind:
		"communication_flows":
			_world.set_communication_flows_enabled(enabled)
		"territorial_claims":
			_world.set_claim_overlay_enabled(enabled)
			if enabled and agent_id != "":
				_session.request_claim_overlay(agent_id)
		"relationships":
			_world.set_relationship_overlay_enabled(enabled)
			if enabled and agent_id != "":
				_session.request_relationship_overlay(agent_id)
		"spatial_control":
			_world.set_analytics_overlay_enabled(enabled)
			if enabled:
				_session.request_analytics_overlay()
		"emergent_group_formation", "emergent_social_norms", "persistent_social_conventions", "distributed_reputation":
			_world.set_metric_overlay_enabled(kind, enabled)
			if enabled:
				_session.request_metric_family_overlay(kind, kind)
		"narrative_hops":
			_world.set_narrative_overlay_enabled(enabled)
			if enabled and agent_id != "":
				_session.request_narrative_hop_overlay(agent_id)
			elif not enabled:
				_ui.clear_narrative_variants()
		"communication_strategy_audit":
			_world.set_research_speech_enabled(enabled)
			if enabled:
				_session.request_strategy_audit_overlay()
		"cultural_transmission", "skill_learning":
			_world.set_metric_overlay_enabled(kind, enabled)
			if enabled:
				_session.request_metric_family_overlay(kind, kind)
		_:
			pass


func _on_overlay_payload(kind: String, payload: Variant) -> void:
	if kind == "subjective_labels":
		_world.apply_subjective_labels(payload)
	elif kind == "territorial_claims":
		_world.apply_subjective_claims(payload)
	elif kind == "relationships":
		_world.apply_relationships(payload)
	elif kind == "narrative_hops":
		_world.apply_narrative_hops(payload)
		var ids: Array = _world.narrative_variant_ids()
		_ui.set_narrative_variants(ids)
	elif kind == "spatial_control":
		_world.apply_research_analytics(payload)
	elif kind in [
		"emergent_group_formation",
		"emergent_social_norms",
		"persistent_social_conventions",
		"distributed_reputation",
		"cultural_transmission",
		"skill_learning",
	]:
		_world.apply_metric_overlay(kind, payload)
	elif kind == "communication_strategy_audit":
		_world.apply_strategy_audit(payload)
		ObserverLog.debug(
			"main",
			"strategy_audit_payload count=%s" % (
				0 if payload == null else int(payload.get("count", 0))
			),
		)
	elif kind == "causal_debugger":
		if typeof(payload) == TYPE_DICTIONARY:
			_ui.open_debugger_payload(payload)
		elif payload == null:
			pass
	elif kind == "causal_debugger_lineage":
		if typeof(payload) == TYPE_DICTIONARY:
			_ui.open_debugger_lineage(payload)
		elif payload == null:
			pass


func _on_overlay_unavailable(kind: String, reason_code: String) -> void:
	if kind == "causal_debugger":
		_ui.show_debugger_unavailable(reason_code)
	elif kind == "causal_debugger_lineage":
		_ui.show_debugger_lineage_unavailable(reason_code)


func _on_explain_requested(tick: int, sequence: int, event_id: String) -> void:
	_session.request_causal_trace(event_id, tick, sequence)


func _on_debugger_focus(tick: int, sequence: int, event_id: String) -> void:
	ObserverLog.info(
		"main",
		"debugger_seek tick=%s sequence=%s event_id=%s" % [tick, sequence, event_id],
	)
	if sequence >= 0:
		_session.seek_event(tick, sequence, null)
	if event_id != "":
		_ui.focus_narrative_event_ids([event_id])


func _on_debugger_provenance(lineage_kind: String, subject_id: String, owner_id: String) -> void:
	ObserverLog.info(
		"main",
		"debugger_provenance kind=%s subject_id=%s owner_id=%s" % [
			lineage_kind, subject_id, owner_id,
		],
	)
	_session.request_debugger_lineage(lineage_kind, subject_id, owner_id)


func _on_credentials_apply(inspection_token: String, debug_token: String) -> void:
	var ok := bool(_session.configure_credentials(inspection_token, debug_token))
	_ui.note_credentials_result(ok, "" if ok else "invalid_credential")
	ObserverLog.debug("acceptance", "credentials_applied ok=%s" % ok)
	if ok and not _session._opened:
		_session.retry_start()


func _on_credentials_forget() -> void:
	_session.forget_credentials()
	_ui.note_credentials_result(true, "")


func _on_credentials_error(reason_code: String) -> void:
	_ui.note_credentials_result(false, reason_code)


func _agent_id_for_entity(entity_id: String) -> String:
	if _session.world == null:
		return ""
	for agent in _session.world.agents:
		if str(agent.entity_id) == entity_id and agent.agent_id != null:
			return str(agent.agent_id)
	return ""


func _on_population_toggled(enabled: bool) -> void:
	ObserverLog.debug("acceptance", "main_population_toggled enabled=%s opened=%s" % [enabled, _session._opened])
	_ui.set_generational_panel_visible(enabled)
	_session.set_demographics_enabled(enabled)
	_session.set_civilization_layer_enabled("locations", enabled)
	if enabled:
		_session.set_generation_markers_enabled(_ui.is_generational_overlay_enabled("generation"))


func _on_demographic_section(section: String) -> void:
	_session.choose_demographic_section(section)


func _on_demographic_load_more() -> void:
	_session.load_more_demographics()
	_session.load_more_demographic_section()
	_session.load_more_generation_markers()


func _on_civilization_layer_toggled(layer_id: String, enabled: bool) -> void:
	_session.set_civilization_layer_enabled(layer_id, enabled)
	ObserverLog.debug("acceptance", "civilization_toggle layer=%s enabled=%s" % [layer_id, enabled])


func _on_civilization_layer_changed(layer_id: String, state: Dictionary) -> void:
	_ui.apply_civilization_layer(layer_id, state)
	_world.apply_civilization_layer(layer_id, state)


func _on_civilization_bundle(cursor: Dictionary, states: Dictionary) -> void:
	_world.apply_civilization_bundle(cursor, states)


func _on_civilization_markers(state: Dictionary) -> void:
	_ui.apply_civilization_timeline_markers(state)


func _on_civilization_catalogue(state: Dictionary) -> void:
	_ui.apply_civilization_timeline_catalogue(state)
	if _session.recorded_boundaries_only and (
		str(state.get("status", "")) != "available" or state.get("boundaries", []).is_empty()
	):
		_session.set_recorded_boundaries_only(false)


func _on_civilization_playback_bundle(frame: Variant, cursor: Dictionary, states: Dictionary) -> void:
	_world.replace_sought_frame(frame, null, true)
	_world.apply_civilization_bundle(cursor, states)
	for layer_id in states.keys():
		_ui.apply_civilization_layer(str(layer_id), states[layer_id])
	var snapshot: Dictionary = _session.playback_snapshot()
	_ui.note_civilization_timeline_tick(int(frame.world.tick), _session.transport.live_tick)
	_ui.note_civilization_playback_state(
		int(frame.world.tick),
		int(snapshot.get("desired_tick", -1)),
		int(snapshot.get("skipped", 0)),
	)
	_on_frame_for_follow(frame, null, true)
	ObserverLog.debug(
		"acceptance",
		"civilization_playback_bundle tick=%s layers=%s" % [
			str(frame.world.tick),
			states.size(),
		],
	)


func _on_civilization_frame_sought(_frame: Variant, _event: Variant, _forward: bool) -> void:
	_world.clear_civilization_layers()
	_ui.note_civilization_timeline_tick(_session.transport.tick, _session.transport.live_tick)
	_refresh_civilization_timeline_context()
	_ui.refresh_civilization_timeline()


func _on_civilization_mode(layer_id: String, mode: String, owner_id: String) -> void:
	if mode == "subjective" and owner_id.is_empty():
		_ui.show_status("restricted", "Selected owner required")
		return
	_session.set_civilization_layer_mode(layer_id, mode, owner_id)


func _on_civilization_owner(owner_id: String) -> void:
	_session.set_civilization_owner(owner_id)
	_ui.set_civilization_owner(owner_id)
	_refresh_civilization_timeline_context()
	_ui.refresh_civilization_timeline()


func _on_civilization_filters(layer_id: String, filters: Dictionary) -> void:
	_session.set_civilization_filters(layer_id, filters)


func _on_civilization_load_more(layer_id: String) -> void:
	_session.load_more_civilization(layer_id)


func _on_civilization_restart(layer_id: String) -> void:
	_session.restart_civilization_layer(layer_id)


func _on_civilization_layer_cleared(layer_id: String, reason_code: String) -> void:
	if _world.has_method("clear_civilization_layer"):
		_world.clear_civilization_layer(layer_id)
	ObserverLog.debug("acceptance", "civilization_layer_cleared layer=%s reason=%s" % [layer_id, reason_code])


func _on_civilization_credentials_help() -> void:
	_ui.focus_credentials()


func _on_civilization_timeline_seek(tick: int) -> void:
	_session.seek_tick(tick)


func _on_civilization_marker_window(
	from_tick: int,
	to_tick: int,
	evidence_class: String,
	owner_id: String,
	layer: String,
) -> void:
	_session.request_civilization_markers(from_tick, to_tick, evidence_class, owner_id, layer)


func _on_civilization_marker_load_more(
	from_tick: int,
	to_tick: int,
	evidence_class: String,
	owner_id: String,
	layer: String,
) -> void:
	_session.load_more_civilization_markers(from_tick, to_tick, evidence_class, owner_id, layer)


func _on_civilization_catalogue_requested(evidence_class: String, owner_id: String) -> void:
	_session.request_civilization_catalogue(evidence_class, owner_id)


func _on_civilization_catalogue_load_more(evidence_class: String, owner_id: String) -> void:
	_session.load_more_civilization_catalogue(evidence_class, owner_id)


func _on_civilization_recorded_mode(enabled: bool) -> void:
	var active: bool = _session.set_recorded_boundaries_only(enabled)
	if enabled and not active:
		_ui.show_status("recorded_unavailable", "Recorded boundaries unavailable")


func _refresh_civilization_timeline_context() -> void:
	_ui.set_civilization_timeline_context(
		_session.run_id,
		_ui.selected_civilization_owner(),
		_session.has_debug_credential(),
		_session.has_inspection_credential(),
	)


func _on_generational_updated() -> void:
	var source: Variant = _session.generational
	var model: Variant = source.model_view
	_ui.apply_demographics(model)
	var kinds: Array = []
	for candidate in ["generation", "cohort", "age_stage"]:
		if _ui.is_generational_overlay_enabled(candidate):
			kinds.append(candidate)
	_world.apply_demographics(model, kinds)
	_ui.set_generation_markers(source.markers, _session.run_id)
	_ui.set_civilization_population_context(model)
	if source.selected_agent_id != "":
		_ui.apply_demographic_selection(source.selected_row, source.selection_state)
		_ui.show_demographic_inspector(source.selected_row)
	ObserverLog.debug(
		"acceptance",
		"generational_rendered demographics=%s care=%s links=%s markers=%s" % [
			model != null,
			_world.generational_care_count(),
			_world.generational_link_count(),
			source.markers.size(),
		],
	)


func _on_lineage_updated() -> void:
	var data: Dictionary = (
		_session.private_lineage.genealogy
		if _active_lineage_tab == "genealogy"
		else _session.private_lineage.participants
	)
	_ui.apply_lineage_panel(_active_lineage_tab, data)
	_apply_lineage_links()


var _active_lineage_tab := "genealogy"
var _active_lineage_ui_tab := "parents"
var _selected_agent_id := ""
var _lineage_history: Array = []


func _lineage_agent_id() -> String:
	if not _selected_agent_id.is_empty():
		return _selected_agent_id
	if not _session.private_lineage.selected_agent_id.is_empty():
		return _session.private_lineage.selected_agent_id
	return _agent_id_for_entity(_session.focus_agent_id)


func _on_lineage_tab(tab: String) -> void:
	ObserverLog.debug("acceptance", "lineage_tab_clicked tab=%s" % tab)
	_active_lineage_ui_tab = tab
	var agent_id := _lineage_agent_id()
	if agent_id.is_empty():
		return
	_request_lineage_tab(tab, agent_id)


func _request_lineage_tab(tab: String, agent_id: String) -> void:
	_active_lineage_tab = "genealogy" if tab in ["parents", "children"] else "participants"
	_session.set_lineage_enabled(true)
	_session.set_generational_agent(agent_id)
	if tab == "parents":
		_session.request_genealogy(agent_id, "ancestors")
	elif tab == "children":
		_session.request_genealogy(agent_id, "descendants")
	elif tab == "teachers":
		_session.request_participants(agent_id, "teacher", "subjective", agent_id)
	elif tab == "students":
		_session.request_participants(agent_id, "learner", "subjective", agent_id)
	else:
		_session.request_participants(agent_id, "both", "subjective", agent_id)


func _select_lineage_agent(agent_id: String) -> void:
	_selected_agent_id = agent_id
	_session.select_demographic_agent(agent_id)
	_session.set_generational_agent(agent_id)
	_session.set_lineage_enabled(true)
	_session.set_generational_agent(agent_id)
	var entity_id: String = _world.agent_entity_for(agent_id)
	if entity_id != "":
		_world.focus_agent(entity_id)
		_world.highlight_selected(entity_id)


func _push_lineage_history() -> void:
	var agent_id := _lineage_agent_id()
	if agent_id.is_empty():
		return
	_lineage_history.append({
		"run_id": _session.run_id,
		"agent_id": agent_id,
		"tab": _active_lineage_ui_tab,
	})
	while _lineage_history.size() > 20:
		_lineage_history.pop_front()


func _on_lineage_entry(kind: String, native_kind: String, ref_id: String) -> void:
	ObserverLog.debug(
		"acceptance",
		"lineage_entry_selected kind=%s native_kind=%s ref=%s" % [kind, native_kind, ref_id],
	)
	if ref_id.is_empty():
		return
	if kind == "content":
		var owner_id := str(_session.private_lineage.participants.get("owner_id", ""))
		_session.set_lineage_enabled(true)
		_session.request_knowledge_root(native_kind, ref_id, "subjective", owner_id)
		return
	_push_lineage_history()
	_select_lineage_agent(ref_id)
	_request_lineage_tab(_active_lineage_ui_tab, ref_id)


func _on_generational_agent(agent_id: String) -> void:
	ObserverLog.debug("acceptance", "panel_agent_selected agent_id=%s" % agent_id)
	_select_lineage_agent(agent_id)


func _on_lineage_back() -> void:
	if not _lineage_history.is_empty():
		var previous: Dictionary = _lineage_history.pop_back()
		if str(previous.get("run_id", "")) == _session.run_id:
			_select_lineage_agent(str(previous.get("agent_id", "")))
			_request_lineage_tab(str(previous.get("tab", "parents")), str(previous.get("agent_id", "")))
			return
	_ui.set_generational_agent("")
	_session.set_lineage_enabled(false)


func _apply_lineage_links() -> void:
	var links: Array = []
	if _ui.is_generational_overlay_enabled("kinship"):
		var genealogy: Dictionary = _session.private_lineage.genealogy
		var selected_entity: String = _world.agent_entity_for(_lineage_agent_id())
		if genealogy.get("status", "") == "available" and not selected_entity.is_empty():
			for group in ["parents", "children"]:
				for node in genealogy.get(group, []):
					var entity: String = _world.agent_entity_for(str(node.ref.native_id))
					if entity.is_empty():
						continue
					links.append({"from": entity, "to": selected_entity})
	if (
		_ui.is_generational_overlay_enabled("mentorship_subjective")
		or _ui.is_generational_overlay_enabled("mentorship_analytical")
	):
		var participants: Dictionary = _session.private_lineage.participants
		if participants.get("status", "") == "available":
			for card in participants.get("items", []):
				var teacher: String = _world.agent_entity_for(str(card.teacher_id))
				var learner: String = _world.agent_entity_for(str(card.learner_id))
				if not teacher.is_empty() and not learner.is_empty():
					links.append({"from": teacher, "to": learner})
	_world.apply_generational_links(links)
