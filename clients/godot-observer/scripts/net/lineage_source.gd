class_name LineageSource

## Session-owned on-demand lineage navigation. All identity keys, edges and
## participant cards come from backend projections; nothing is inferred.

const Lineage := preload("res://scripts/protocol/lineage.gd")

const MAX_NODES := 500
const MAX_EDGES := 1000
const MAX_PARTICIPANTS := 200

var enabled := false
var selected_agent_id := ""
var partial_prefix := false
var descriptor: Dictionary = {}
var genealogy := {}
var participants := {}
var knowledge := {}
var reason_code := ""

var _sink: Callable
var _run_id := ""
var _epoch := 0
var _credential_generation := 0
var _panel_generation := 0
var _families_loaded := false
var _families: Array = []
var _pending := {}
var _cache := {}

signal changed


func set_request_sink(sink: Callable) -> void:
	_sink = sink


func set_context(run_id: String, epoch: int, credential_generation: int) -> void:
	if run_id != _run_id:
		clear()
	_run_id = run_id
	_epoch = epoch
	_credential_generation = credential_generation


func on_frame(frame: Variant) -> void:
	if frame == null or frame.cursor == null or frame.world == null:
		return
	var world_tick := int(frame.world.tick)
	var after_tick: Variant = frame.cursor.after_tick
	if after_tick == null or world_tick > int(after_tick):
		partial_prefix = false
		descriptor = {"kind": "full", "tick": world_tick, "sequence": null}
	else:
		partial_prefix = true
		descriptor = {
			"kind": "prefix",
			"tick": int(after_tick),
			"sequence": null if frame.cursor.after_sequence == null else int(frame.cursor.after_sequence),
		}
		if enabled:
			_clear_private("finalized_boundary_required")
		changed.emit()


func clear() -> void:
	enabled = false
	selected_agent_id = ""
	partial_prefix = false
	descriptor = {}
	genealogy = {}
	participants = {}
	knowledge = {}
	reason_code = ""
	_families_loaded = false
	_families = []
	_pending.clear()
	_cache.clear()
	_panel_generation += 1
	changed.emit()


func _clear_private(reason: String) -> void:
	genealogy = {}
	participants = {}
	knowledge = {}
	reason_code = reason
	_pending.clear()
	_panel_generation += 1
	changed.emit()


func invalidate_private(reason_code: String = "stale") -> void:
	if not enabled:
		return
	_clear_private(reason_code)


func request_genealogy(agent_id: String, direction: String = "both") -> void:
	selected_agent_id = agent_id
	if not enabled or agent_id.is_empty():
		return
	if partial_prefix:
		_clear_private("finalized_boundary_required")
		genealogy = {"status": "finalized_boundary_required", "reason_code": "finalized_boundary_required"}
		changed.emit()
		return
	if direction not in ["ancestors", "descendants", "both"]:
		direction = "both"
	genealogy = {"status": "loading", "direction": direction}
	_panel_generation += 1
	if not _families_loaded:
		_request_families("genealogy", {"direction": direction})
		return
	_request_genealogy_nodes({"direction": direction})


func request_participants(
	agent_id: String,
	role: String = "both",
	evidence_class: String = "subjective",
	owner_id: String = "",
) -> void:
	selected_agent_id = agent_id
	if not enabled or agent_id.is_empty():
		return
	if partial_prefix:
		_clear_private("finalized_boundary_required")
		participants = {"status": "finalized_boundary_required", "reason_code": "finalized_boundary_required"}
		changed.emit()
		return
	if role not in ["teacher", "learner", "both"]:
		role = "both"
	if evidence_class not in ["subjective", "analytical"]:
		evidence_class = "subjective"
	if evidence_class == "subjective" and owner_id.is_empty():
		owner_id = agent_id
	participants = {
		"status": "loading",
		"role": role,
		"evidence_class": evidence_class,
		"owner_id": owner_id,
		"agent_id": agent_id,
		"cache_key": _cache_key(evidence_class, owner_id),
	}
	_panel_generation += 1
	var query := _boundary_query()
	query["evidence_class"] = evidence_class
	query["agent_id"] = agent_id
	query["role"] = role
	query["limit"] = 100
	if evidence_class == "subjective":
		query["owner_id"] = owner_id
	var capability := "debug"
	_request(
		"lineage_participants",
		"/v1/simulations/%s/lineage/mentorship/participants" % _run_id,
		{
			"panel": "participants",
			"agent_id": agent_id,
			"role": role,
			"evidence_class": evidence_class,
			"owner_id": owner_id,
			"capability": capability,
		},
		query,
	)


func request_knowledge_root(
	native_kind: String,
	native_id: String,
	evidence_class: String = "subjective",
	owner_id: String = "",
) -> void:
	if not enabled or partial_prefix:
		if partial_prefix:
			_clear_private("finalized_boundary_required")
		return
	knowledge = {"status": "loading", "native_kind": native_kind, "native_id": native_id}
	_panel_generation += 1
	var query := _boundary_query()
	query["evidence_class"] = evidence_class
	query["native_kind"] = native_kind
	query["native_id"] = native_id
	query["limit"] = 100
	if evidence_class == "subjective":
		if owner_id.is_empty():
			owner_id = selected_agent_id
		query["owner_id"] = owner_id
	_request(
		"lineage_knowledge_nodes",
		"/v1/simulations/%s/lineage/knowledge/nodes" % _run_id,
		{"panel": "knowledge", "capability": "debug", "evidence_class": evidence_class, "owner_id": owner_id},
		query,
	)


func load_more_lineage(panel: String) -> void:
	if panel == "participants":
		_load_more_participants()
	elif panel == "genealogy":
		_load_more_genealogy()
	elif panel == "knowledge":
		_load_more_knowledge()


func handle_response(meta: Dictionary, body: Variant, reason: String, _status: int) -> void:
	if int(meta.get("epoch", _epoch)) != _epoch:
		return
	if int(meta.get("credential_generation", _credential_generation)) != _credential_generation:
		return
	if int(meta.get("panel_generation", -1)) != _panel_generation:
		return
	var kind := str(meta.get("kind", ""))
	if reason != "":
		_apply_error(meta, reason)
		return
	match kind:
		"lineage_families":
			_apply_families(meta, body)
		"lineage_genealogy_nodes":
			_apply_genealogy_nodes(meta, body)
		"lineage_traverse":
			_apply_traverse(meta, body)
		"lineage_participants":
			_apply_participants(meta, body)
		"lineage_knowledge_nodes":
			_apply_knowledge_nodes(meta, body)
		"lineage_knowledge_traverse":
			_apply_knowledge_traverse(meta, body)


func _request_families(panel: String, carry: Dictionary) -> void:
	_request(
		"lineage_families",
		"/v1/simulations/%s/lineage/families" % _run_id,
		{
			"panel": panel,
			"capability": "inspection",
			"expected_root": "array",
			"carry": carry.duplicate(true),
		},
		{},
	)


func _request_genealogy_nodes(carry: Dictionary) -> void:
	var query := _boundary_query()
	query["evidence_class"] = "objective"
	query["native_kind"] = "agent"
	query["native_id"] = selected_agent_id
	query["limit"] = 100
	_request(
		"lineage_genealogy_nodes",
		"/v1/simulations/%s/lineage/genealogy/nodes" % _run_id,
		{"panel": "genealogy", "capability": "inspection", "carry": carry.duplicate(true)},
		query,
	)


func _apply_families(meta: Dictionary, body: Variant) -> void:
	var parsed: Dictionary = Lineage.parse_families(body)
	if not bool(parsed.get("ok", false)):
		_apply_error(meta, str(parsed.get("reason_code", "lineage_invalid")))
		return
	_families = parsed["value"]
	_families_loaded = true
	var panel := str(meta.get("panel", ""))
	var carry: Dictionary = meta.get("carry", {})
	if panel == "genealogy":
		_request_genealogy_nodes(carry)
	elif panel == "knowledge":
		pass


func _apply_genealogy_nodes(meta: Dictionary, body: Variant) -> void:
	var parsed: Dictionary = Lineage.parse_node_list(body)
	if not bool(parsed.get("ok", false)):
		_apply_error(meta, str(parsed.get("reason_code", "lineage_invalid")))
		return
	var model = parsed["value"]
	var root_key := ""
	for node in model.items:
		if node.ref.native_kind == "agent" and node.ref.native_id == selected_agent_id:
			root_key = node.ref.key
			break
	if root_key.is_empty():
		genealogy = {"status": "missing_root", "reason_code": "root_not_found"}
		changed.emit()
		return
	var carry: Dictionary = meta.get("carry", {})
	var direction := str(carry.get("direction", "both"))
	var query := _boundary_query()
	query["evidence_class"] = "objective"
	query["root_key"] = root_key
	query["direction"] = direction
	query["max_depth"] = 1
	query["max_nodes"] = 100
	query["max_edges"] = 200
	query["limit"] = 100
	_request(
		"lineage_traverse",
		"/v1/simulations/%s/lineage/genealogy/traverse" % _run_id,
		{"panel": "genealogy", "capability": "inspection", "carry": carry.duplicate(true)},
		query,
	)


func _apply_traverse(meta: Dictionary, body: Variant) -> void:
	var parsed: Dictionary = Lineage.parse_graph(body)
	if not bool(parsed.get("ok", false)):
		_apply_error(meta, str(parsed.get("reason_code", "lineage_invalid")))
		return
	var model = parsed["value"]
	var parents: Array = []
	var children: Array = []
	var nodes_by_key: Dictionary = {}
	for node in model.nodes:
		nodes_by_key[node.ref.key] = node
	for edge in model.edges:
		if edge.relation != "parent_of":
			continue
		var source = nodes_by_key.get(edge.source_key)
		var target = nodes_by_key.get(edge.target_key)
		if source == null or target == null:
			continue
		if target.ref.native_id == selected_agent_id:
			parents.append(source)
		if source.ref.native_id == selected_agent_id:
			children.append(target)
	genealogy = {
		"status": "available",
		"parents": _cap_nodes(parents),
		"children": _cap_nodes(children),
		"nodes": _cap_nodes(model.nodes),
		"edges": model.edges.slice(0, MAX_EDGES),
		"next_cursor": model.next_cursor,
		"coverage": model.coverage,
		"publication": model.snapshot,
		"truncated": model.truncated or model.nodes.size() > MAX_NODES or model.edges.size() > MAX_EDGES,
		"requested_boundary_tick": model.requested_boundary_tick,
		"captured_boundary_tick": model.captured_boundary_tick,
	}
	remember_publication(model.snapshot)
	changed.emit()


func _apply_participants(meta: Dictionary, body: Variant) -> void:
	var parsed: Dictionary = Lineage.parse_participants(body)
	if not bool(parsed.get("ok", false)):
		_apply_error(meta, str(parsed.get("reason_code", "lineage_invalid")))
		return
	var model = parsed["value"]
	if model.agent_id != str(meta.get("agent_id", "")) or model.role != str(meta.get("role", "")):
		return
	if model.evidence_class != str(meta.get("evidence_class", "")):
		return
	if model.owner_id != meta.get("owner_id", null) and str(meta.get("owner_id", "")) != "":
		return
	var items: Array = model.items.duplicate()
	if bool(meta.get("append", false)) and not participants.is_empty():
		items = participants.get("items", []).duplicate()
		for item in model.items:
			if items.size() >= MAX_PARTICIPANTS:
				break
			items.append(item)
	participants = {
		"status": "available",
		"items": items.slice(0, MAX_PARTICIPANTS),
		"scanned_count": model.scanned_count,
		"unprojectable_count": model.unprojectable_count,
		"scan_limited": model.scan_limited,
		"next_cursor": model.next_cursor,
		"coverage": model.coverage,
		"publication": model.snapshot,
		"agent_id": model.agent_id,
		"role": model.role,
		"evidence_class": model.evidence_class,
		"owner_id": model.owner_id,
		"requested_boundary_tick": model.requested_boundary_tick,
		"captured_boundary_tick": model.captured_boundary_tick,
	}
	if (
		meta.get("after", null) != null
		and model.next_cursor != null
		and str(model.next_cursor) == str(meta.get("after", ""))
	):
		participants["status"] = "non_progressing_cursor"
	remember_publication(model.snapshot)
	changed.emit()


func _apply_knowledge_nodes(meta: Dictionary, body: Variant) -> void:
	var parsed: Dictionary = Lineage.parse_node_list(body)
	if not bool(parsed.get("ok", false)):
		_apply_error(meta, str(parsed.get("reason_code", "lineage_invalid")))
		return
	var model = parsed["value"]
	var matches: Array = []
	for node in model.items:
		if node.ref.native_kind == str(meta.get("native_kind", "")) and node.ref.native_id == str(meta.get("native_id", "")):
			matches.append(node)
	if matches.is_empty():
		knowledge = {
			"status": "missing_root",
			"items": [],
			"publication": model.snapshot,
			"next_cursor": model.next_cursor,
			"coverage": model.coverage,
		}
		changed.emit()
		return
	var root = matches[0]
	var query := _boundary_query()
	query["evidence_class"] = str(meta.get("evidence_class", "subjective"))
	query["root_key"] = root.ref.key
	query["direction"] = "both"
	query["max_depth"] = 1
	query["max_nodes"] = 100
	query["max_edges"] = 200
	query["limit"] = 100
	if str(meta.get("evidence_class", "")) == "subjective":
		query["owner_id"] = str(meta.get("owner_id", ""))
	_request(
		"lineage_knowledge_traverse",
		"/v1/simulations/%s/lineage/knowledge/traverse" % _run_id,
		{
			"panel": "knowledge",
			"capability": "debug",
			"evidence_class": query["evidence_class"],
			"owner_id": query.get("owner_id", ""),
		},
		query,
	)


func _apply_knowledge_traverse(meta: Dictionary, body: Variant) -> void:
	var parsed: Dictionary = Lineage.parse_graph(body)
	if not bool(parsed.get("ok", false)):
		_apply_error(meta, str(parsed.get("reason_code", "lineage_invalid")))
		return
	var model = parsed["value"]
	knowledge = {
		"status": "available",
		"items": _cap_nodes(model.nodes),
		"edges": model.edges.slice(0, MAX_EDGES),
		"next_cursor": model.next_cursor,
		"coverage": model.coverage,
		"publication": model.snapshot,
		"truncated": model.truncated,
	}
	changed.emit()


func _load_more_participants() -> void:
	if participants.is_empty() or participants.get("next_cursor", null) == null:
		return
	var query := _boundary_query()
	query["evidence_class"] = str(participants.get("evidence_class", "subjective"))
	query["agent_id"] = str(participants.get("agent_id", ""))
	query["role"] = str(participants.get("role", "both"))
	query["limit"] = 100
	query["after"] = participants["next_cursor"]
	if str(participants.get("evidence_class", "")) == "subjective":
		query["owner_id"] = str(participants.get("owner_id", ""))
	_request(
		"lineage_participants",
		"/v1/simulations/%s/lineage/mentorship/participants" % _run_id,
		{
			"panel": "participants",
			"agent_id": query["agent_id"],
			"role": query["role"],
			"evidence_class": query["evidence_class"],
			"owner_id": query.get("owner_id", ""),
			"capability": "debug",
			"append": true,
			"panel_generation": _panel_generation,
			"after": participants["next_cursor"],
		},
		query,
	)


func _load_more_genealogy() -> void:
	# Direct parents/children stay complete; deeper exploration is explicit.
	if genealogy.get("next_cursor", null) == null:
		return


func _load_more_knowledge() -> void:
	if knowledge.get("next_cursor", null) == null:
		return


func _boundary_query() -> Dictionary:
	var query := {"boundary_tick": int(descriptor.get("tick", 0))}
	return query


func _cache_key(evidence_class: String, owner_id: String) -> String:
	return "%s|%s|%s" % [evidence_class, owner_id, str(descriptor.get("tick", 0))]


func remember_publication(snapshot: Variant) -> void:
	if snapshot == null:
		return
	var key := "%s|%s" % [snapshot.publication_id, snapshot.digest]
	if not _cache.has(key):
		_cache[key] = true


func publication_matches(snapshot: Variant) -> bool:
	if snapshot == null:
		return false
	return _cache.has("%s|%s" % [snapshot.publication_id, snapshot.digest])


func _cap_nodes(nodes: Array) -> Array:
	return nodes.slice(0, MAX_NODES)


func _apply_error(meta: Dictionary, reason: String) -> void:
	var panel := str(meta.get("panel", ""))
	var code := reason
	if reason == "forbidden":
		code = "restricted"
	elif reason == "gone":
		code = "cursor_gone"
	elif reason == "not_found":
		code = "unsupported"
	elif reason == "lineage_cursor_expired":
		code = "cursor_gone"
	if panel == "participants":
		participants = {"status": "unavailable", "reason_code": code}
	elif panel == "knowledge":
		knowledge = {"status": "unavailable", "reason_code": code}
	else:
		genealogy = {"status": "unavailable", "reason_code": code}
	reason_code = code
	changed.emit()


func _request(kind: String, path: String, meta: Dictionary, query: Dictionary) -> void:
	if _sink.is_null() or _run_id.is_empty():
		return
	_pending[kind] = int(_pending.get(kind, 0)) + 1
	var payload := {
		"source": "lineage",
		"kind": kind,
		"epoch": _epoch,
		"credential_generation": _credential_generation,
		"panel_generation": _panel_generation,
		"serial": _pending[kind],
	}
	for key in meta.keys():
		payload[key] = meta[key]
	_sink.call(kind, path, payload, query)
