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
	_session.run_id_applied.connect(_reload_bookmarks)
	_session.begin()


func _on_events_loaded(events: Array, focus_tick: int, focus_sequence: int) -> void:
	_ui.replace_events(events, focus_tick, focus_sequence, _session.world)
	_refresh_markers()


func _on_source_cleared() -> void:
	_world.clear_world()
	_ui.clear_for_source_switch()
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
	_apply_follow_camera()


func _on_frame_for_follow(_frame: Variant, _event: Variant, _forward: bool) -> void:
	_apply_follow_camera()


func _on_live_for_follow(_event: Variant) -> void:
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


func _on_event_seek(tick: int, sequence: int) -> void:
	_session.seek_event(tick, sequence, null)


func _on_control(action: String) -> void:
	match action:
		"play":
			_session.play()
		"pause":
			_session.pause()
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
