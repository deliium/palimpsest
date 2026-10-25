extends RefCounted

const SessionScript := preload("res://scripts/net/session.gd")
const TransportScript := preload("res://scripts/protocol/transport.gd")
const WorldScene := preload("res://scenes/world_view.tscn")
const Civ := preload("res://scripts/protocol/civilization.gd")
const BASE := "res://fixtures/protocol/civilization/"


class HttpStub:
	extends Node
	var calls: Array = []

	func get_json(
		url: String,
		request_id: String,
		_token: String = "",
		_expected_root: String = "object",
	) -> void:
		calls.append({"url": url, "request_id": request_id})

	func clear_queue() -> void:
		pass


class CursorStub:
	extends RefCounted
	var after_tick: Variant = null
	var after_sequence: Variant = null


class WorldStub:
	extends RefCounted
	var tick: int = 4
	var revision: int = 4


class FrameStub:
	extends RefCounted
	var cursor: CursorStub = CursorStub.new()
	var world: WorldStub = WorldStub.new()


class RenderWorldStub:
	extends RefCounted
	var locations: Array = []
	var agents: Array = []
	var structures: Array = []


class LocationStub:
	extends RefCounted
	var location_id: String = ""


class AgentStub:
	extends RefCounted
	var entity_id: String = ""
	var agent_id: Variant = null
	var location_id: String = ""


class StructureStub:
	extends RefCounted
	var structure_id: String = ""
	var location_id: String = ""


func run() -> Array:
	var failures: Array = []
	_expect(failures, _target_derivation(), "target derivation")
	_expect(failures, _staged_bundle_acceptance(), "staged bundle acceptance")
	_expect(failures, _three_intermediate_bundles(), "three intermediate bundles")
	_expect(failures, _latest_target_replaces_queued(), "latest target")
	_expect(failures, _presentation_deadline(), "presentation deadline")
	_expect(failures, _pause_invalidates_staging(), "pause invalidation")
	_expect(failures, _cursor_and_horizon(), "cursor and horizon")
	_expect(failures, _semantic_digest_ignores_lod(), "semantic digest")
	return failures


func _load(name: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(BASE + name))


func _frame(tick: int, revision: int = 4) -> FrameStub:
	var frame := FrameStub.new()
	frame.world.tick = tick
	frame.world.revision = revision
	frame.cursor.after_tick = null
	frame.cursor.after_sequence = null
	return frame


func _session() -> Array:
	var tree := Engine.get_main_loop() as SceneTree
	var session: Node = SessionScript.new()
	if tree != null:
		tree.root.add_child(session)
	var http := HttpStub.new()
	session.add_child(http)
	session._http = http
	session.run_id = "run-capture"
	session.origin = "http://127.0.0.1:8000"
	session.transport.mode = TransportScript.MODE_REPLAY
	session.transport.set_paused(false)
	session.civilization.set_context("run-capture", session._http_epoch, 0)
	session.civilization.set_layer_enabled("settlements", true)
	session._opened = true
	var signals: Array = []
	session.playback_bundle_ready.connect(
		func(frame: Variant, cursor: Dictionary, states: Dictionary) -> void:
			signals.append({"tick": int(frame.world.tick), "cursor": cursor.duplicate(true), "states": states})
	)
	return [session, http, signals]


func _release(session: Node, layer: String = "") -> void:
	for request_id in session._pending.keys():
		var meta: Dictionary = session._pending[request_id]
		if str(meta.get("source", "")) != "civilization":
			continue
		if layer != "" and str(meta.get("layer", "")) != layer:
			continue
		var name := "overlay_%s.json" % str(meta.get("layer", ""))
		session._on_http(str(request_id), 200, _load(name), "")
		return


func _release_at(session: Node, layer: String, tick: int) -> void:
	for request_id in session._pending.keys():
		var meta: Dictionary = session._pending[request_id]
		if str(meta.get("source", "")) != "civilization" or str(meta.get("layer", "")) != layer:
			continue
		var payload: Dictionary = _load("overlay_%s.json" % layer)
		payload["requested_tick"] = tick
		payload["resolved_cursor"]["tick"] = tick
		payload["resolved_cursor"]["boundary_tick"] = tick
		payload["window"]["end_tick"] = tick
		for row in payload.get("rows", []):
			var history: Dictionary = row.get("history", {})
			history["boundary_tick"] = tick
			if history.get("window", null) != null:
				history["window"]["end_tick"] = tick
		session._on_http(str(request_id), 200, payload, "")
		return


func _target_derivation() -> String:
	var pair: Array = _session()
	var session: Node = pair[0]
	var http: HttpStub = pair[1]
	session._playing = true
	session._playback_last_accepted_tick = 3
	session._playback_last_step_usec = Time.get_ticks_usec() - 600000
	session.request_playback_state(4)
	if http.calls.is_empty():
		session.free()
		return "playback issued no state request"
	var url := str(http.calls[0]["url"])
	if not url.contains("/observer/state?") or not url.contains("tick=4"):
		session.free()
		return "playback did not request an exact state boundary"
	if url.contains("speed="):
		session.free()
		return "speed leaked into the state query"
	var snapshot: Dictionary = session.playback_snapshot()
	if int(snapshot.get("inflight", 0)) != 1:
		session.free()
		return "playback allowed more than one state request"
	session.request_playback_state(6)
	if http.calls.size() != 1:
		session.free()
		return "queued target started a second in-flight request"
	if int(session.playback_snapshot().get("desired_tick", -1)) != 6:
		session.free()
		return "latest desired target not retained"
	session.free()
	return ""


func _staged_bundle_acceptance() -> String:
	var pair: Array = _session()
	var session: Node = pair[0]
	var signals: Array = pair[2]
	session._playing = true
	session._playback_last_accepted_tick = 3
	var http_epoch: int = session._http_epoch
	var seek_serial: int = session._seek_serial
	session._stage_playback_frame(_frame(4))
	if session.playback_snapshot().get("pending_frame", false) != true:
		session.free()
		return "state response did not stage the frame"
	_release(session)
	if session._http_epoch != http_epoch or session._seek_serial != seek_serial:
		session.free()
		return "automatic presentation cancelled an active seek epoch"
	var snapshot: Dictionary = session.playback_snapshot()
	if int(snapshot.get("accepted", 0)) != 1:
		session.free()
		return "bundle completion did not accept the staged frame"
	if snapshot.get("pending_frame", true):
		session.free()
		return "accepted frame stayed pending"
	if session.world == null or int(session.world.tick) != 4:
		session.free()
		return "accepted world tick missing"
	if signals.size() != 1 or int(signals[0]["tick"]) != 4:
		session.free()
		return "atomic bundle signal missing"
	if str(session.civilization.states.get("settlements", {}).get("status", "")) != "available":
		session.free()
		return "matching layer state missing from acceptance"
	if int(session.civilization._cursor.get("tick", -1)) != 4:
		session.free()
		return "accepted boundary not adopted by the source"
	session.free()
	return ""


func _three_intermediate_bundles() -> String:
	var pair: Array = _session()
	var session: Node = pair[0]
	var signals: Array = pair[2]
	session._playing = true
	for tick in [1, 2, 3]:
		var before := signals.size()
		session._playback_last_accepted_tick = tick - 1
		session._stage_playback_frame(_frame(tick))
		_release_at(session, "settlements", tick)
		if signals.size() != before + 1:
			session.free()
			return "intermediate bundle %s was not displayed" % tick
		if int(signals[-1]["tick"]) != tick:
			session.free()
			return "intermediate bundle %s displayed the wrong boundary" % tick
	session.free()
	return ""


func _latest_target_replaces_queued() -> String:
	var pair: Array = _session()
	var session: Node = pair[0]
	var http: HttpStub = pair[1]
	var signals: Array = pair[2]
	session._playing = true
	session._playback_last_accepted_tick = 3
	session._stage_playback_frame(_frame(4))
	session.request_playback_state(7)
	_release(session)
	if signals.size() != 1 or int(signals[0]["tick"]) != 4:
		session.free()
		return "intermediate matching bundle was not displayed"
	var last_kind := str(session.last_request.get("kind", ""))
	if last_kind != "state_playback":
		session.free()
		return "accepted bundle did not advance to the newest target"
	var requested := -1
	for call in http.calls:
		if str(call["url"]).contains("tick=7"):
			requested = 7
	if requested != 7:
		session.free()
		return "newest queued target was not requested"
	if int(session.playback_snapshot().get("inflight", 0)) != 1:
		session.free()
		return "target replacement left more than one in-flight request"
	session.free()
	return ""


func _presentation_deadline() -> String:
	var pair: Array = _session()
	var session: Node = pair[0]
	var signals: Array = pair[2]
	session.civilization.set_layer_enabled("culture", true)
	session._playing = true
	session._playback_last_accepted_tick = 5
	session._stage_playback_frame(_frame(6))
	_release_at(session, "settlements", 6)
	session._on_playback_deadline()
	if session.playback_snapshot().get("pending_frame", true):
		session.free()
		return "deadline did not settle the staged frame"
	var ready: Dictionary = session.civilization.states.get("settlements", {})
	if str(ready.get("status", "")) != "available":
		session.free()
		return "deadline discarded a ready matching layer"
	if session.world == null or int(session.world.tick) != 6:
		session.free()
		return "timed-out boundary was not displayed"
	var state: Dictionary = session.civilization.states.get("culture", {})
	if str(state.get("status", "")) != "unavailable" or str(state.get("reason_code", "")) != "presentation_timeout":
		session.free()
		return "timed-out layer was not explicitly unavailable"
	if signals.is_empty():
		session.free()
		return "timed-out bundle did not accept atomically"
	session.free()
	return ""


func _pause_invalidates_staging() -> String:
	var pair: Array = _session()
	var session: Node = pair[0]
	session._playing = true
	session._playback_last_accepted_tick = 5
	var epoch := int(session.playback_snapshot().get("epoch", 0))
	session._stage_playback_frame(_frame(6))
	session.pause()
	var snapshot: Dictionary = session.playback_snapshot()
	if snapshot.get("pending_frame", true):
		session.free()
		return "pause retained staged presentation work"
	if int(snapshot.get("epoch", -1)) <= epoch:
		session.free()
		return "pause did not advance the playback epoch"
	if not session.civilization._active_bundle.is_empty():
		session.free()
		return "pause did not cancel the staged bundle"
	session.request_playback_state(5)
	if str(session.last_request.get("kind", "")) != "state_playback":
		session.free()
		return "same-boundary retry while paused was suppressed"
	if int(session.last_request.get("query", {}).get("tick", -1)) != 5:
		session.free()
		return "same-boundary retry requested a different boundary"
	session.free()
	return ""


func _cursor_and_horizon() -> String:
	var pair: Array = _session()
	var session: Node = pair[0]
	session._playback_last_accepted_tick = 3
	var helper: Dictionary = session._playback_cursor_for(_frame(4))
	if int(helper.get("tick", -1)) != 4 or int(helper.get("boundary_tick", -1)) != 4:
		session.free()
		return "resume pair replaced the actual frame tick"
	var prefix_frame := _frame(4)
	prefix_frame.cursor.after_tick = 4
	prefix_frame.cursor.after_sequence = 2
	var prefix: Dictionary = session._playback_cursor_for(prefix_frame)
	if prefix.get("boundary_tick", null) != null or int(prefix.get("through_sequence", -1)) != 2:
		session.free()
		return "prior-event prefix lost its exact sequence"
	session.transport.mode = TransportScript.MODE_REPLAY
	session.transport.live_tick = 4
	session._playback_last_accepted_tick = 4
	session._playing = true
	session.request_playback_state(8)
	if session.playback_snapshot().get("playing", true):
		session.free()
		return "playback did not stop at the run high water"
	if int(session._playback_desired_tick) != -1:
		session.free()
		return "horizon stop retained a forward target"
	session.free()
	var limit_pair: Array = _session()
	var limited: Node = limit_pair[0]
	limited.civilization.set_layer_enabled("culture", true)
	limited.civilization.set_layer_enabled("technology", true)
	limited._playing = true
	limited._stage_playback_frame(_frame(4))
	var inflight := 0
	for meta in limited._pending.values():
		if str(meta.get("source", "")) == "civilization":
			inflight += 1
	if inflight > 2:
		limited.free()
		return "more than two civilization requests in flight"
	limited.free()
	return ""


func _render_world() -> RenderWorldStub:
	var world := RenderWorldStub.new()
	for location_id in ["loc-1", "loc-2", "loc-3"]:
		var location := LocationStub.new()
		location.location_id = location_id
		world.locations.append(location)
	var agent_a := AgentStub.new()
	agent_a.entity_id = "body-a"
	agent_a.agent_id = "agent-a"
	agent_a.location_id = "loc-1"
	world.agents.append(agent_a)
	var agent_b := AgentStub.new()
	agent_b.entity_id = "body-b"
	agent_b.agent_id = "agent-b"
	agent_b.location_id = "loc-2"
	world.agents.append(agent_b)
	var structure := StructureStub.new()
	structure.structure_id = "structure-1"
	structure.location_id = "loc-1"
	world.structures.append(structure)
	return world


func _cursor() -> Dictionary:
	return {
		"run_id": "run-physical",
		"world_id": "world-physical",
		"tick": 4,
		"through_sequence": null,
		"boundary_tick": 4,
		"revision": 4,
	}


func _map_state() -> Dictionary:
	var parsed: Dictionary = Civ.parse_map(_load("map_locations.json"))
	var model = parsed["value"]
	return {
		"status": "available",
		"layer": "locations",
		"evidence_class": model.scope.evidence_class,
		"owner_id": model.scope.owner_id,
		"cursor": _cursor(),
		"rows": model.rows,
		"coverage": model.coverage,
		"truncated": model.truncated,
	}


func _overlay_state() -> Dictionary:
	var parsed: Dictionary = Civ.parse_overlay(_load("overlay_settlements.json"))
	var model = parsed["value"]
	return {
		"status": "available",
		"layer": "settlements",
		"evidence_class": model.scope.evidence_class,
		"owner_id": model.scope.owner_id,
		"cursor": _cursor(),
		"rows": model.rows,
		"coverage": model.coverage,
		"truncated": model.truncated,
		"publication": null,
	}


func _semantic_digest_ignores_lod() -> String:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	var view: Node2D = WorldScene.instantiate()
	tree.root.add_child(view)
	view._world_state = _render_world()
	view._centers = {"loc-1": Vector2(100, 100), "loc-2": Vector2(300, 100), "loc-3": Vector2(200, 240)}
	view.apply_civilization_bundle(_cursor(), {"locations": _map_state(), "settlements": _overlay_state()})
	var digest: String = view.semantic_digest()
	var snapshot: Dictionary = view.semantic_snapshot()
	if int(snapshot.get("counts", {}).get("layers", 0)) != 2:
		view.free()
		return "semantic counts missing"
	if int(snapshot.get("counts", {}).get("rows", 0)) <= 0:
		view.free()
		return "semantic row identity counts missing"
	view.set_presentation_detail("aggregate")
	if view.semantic_digest() != digest:
		view.free()
		return "LOD changed the scientific semantic digest"
	var facilities = view.get_node_or_null("CivilizationFacilities")
	if facilities == null or str(facilities.lod()) != "aggregate":
		view.free()
		return "aggregate LOD not applied to the render plan"
	var effects = view.get_node_or_null("EffectsLayer")
	if effects == null or str(effects.lod()) != "aggregate":
		view.free()
		return "aggregate LOD not applied to effects"
	effects._lod = "aggregate"
	effects._marks.clear()
	for index in range(40):
		effects._marks.append({"action": "activity", "point": Vector2.ZERO, "age": 0.0, "life": 1.0})
	effects.set_lod("reduced")
	if effects._marks.size() > 32:
		view.free()
		return "reduced LOD did not bound transient effects"
	view.set_presentation_detail("full")
	if view.semantic_digest() != digest:
		view.free()
		return "return to full detail changed semantic state"
	view.free()
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
