extends RefCounted
class_name ResearchFocusController

## Session-owned, bounded research focus transport. Presentation only.

signal changed

const MAX_ROWS := 500
const MAX_NODES := 200
const MAX_EDGES := 500

var _sink := Callable()
var _run_id := ""
var _epoch := 0
var _credential_generation := 0
var _focus_epoch := 0
var _state := {
	"active": false,
	"kind": "",
	"source": "",
	"evidence_class": "",
	"owner_id": "",
	"identity_owner": "",
	"family": "",
	"native_kind": "",
	"native_id": "",
	"node_key": "",
	"publication_id": "",
	"civilization_row_id": "",
	"requested_tick": null,
	"captured_tick": null,
	"coverage": {},
	"root_status": "none",
	"resolution": "none",
	"reason_code": "",
	"rows": [],
}


func set_request_sink(sink: Callable) -> void:
	_sink = sink


func set_context(run_id: String, epoch: int, credential_generation: int) -> void:
	if run_id != _run_id or epoch != _epoch or credential_generation != _credential_generation:
		_run_id = run_id
		_epoch = epoch
		_credential_generation = credential_generation
		_clear_state("context_changed")


func state() -> Dictionary:
	return _state.duplicate(true)


func clear(reason: String = "cleared") -> void:
	_clear_state(reason)


func invalidate_private(reason: String) -> void:
	if str(_state.get("evidence_class", "")) != "objective":
		_clear_state(reason)


func _clear_state(reason: String) -> void:
	_focus_epoch += 1
	_state = {
		"active": false, "kind": "", "source": "", "evidence_class": "",
		"owner_id": "", "identity_owner": "", "family": "",
		"native_kind": "", "native_id": "", "node_key": "",
		"publication_id": "", "civilization_row_id": "",
		"requested_tick": null, "captured_tick": null,
		"coverage": {}, "root_status": "none", "resolution": "none",
		"reason_code": reason, "rows": [],
	}
	changed.emit()


func resolve_selection(selection: Dictionary) -> void:
	var kind := ""
	for candidate in ["agent_id", "location_id", "institution_id", "narrative_id", "technology_id"]:
		if str(selection.get(candidate, "")) != "":
			kind = candidate.trim_suffix("_id")
			break
	if kind == "":
		_clear_state("focus_missing")
		return
	_focus_epoch += 1
	_state = {
		"active": true,
		"kind": kind,
		"source": str(selection.get("entity_source", "")),
		"evidence_class": str(selection.get("evidence_class", "objective")),
		"owner_id": str(selection.get("owner_id", "")),
		"identity_owner": str(selection.get("identity_owner", "")),
		"family": str(selection.get("lineage_family", "")),
		"native_kind": str(selection.get("native_kind", kind)),
		"native_id": str(selection.get("%s_id" % kind, "")),
		"node_key": str(selection.get("lineage_node_key", "")),
		"publication_id": str(selection.get("lineage_publication_id", selection.get("civilization_publication_id", ""))),
		"civilization_row_id": str(selection.get("civilization_row_id", "")),
		"requested_tick": selection.get("tick", null),
		"captured_tick": null,
		"coverage": {},
		"root_status": "pending",
		"resolution": "pending",
		"reason_code": "",
		"rows": [],
	}
	changed.emit()
	if kind == "agent" or kind == "location":
		_state["root_status"] = "frame_selection"
		_state["resolution"] = "resolved"
		changed.emit()
		return
	if str(_state["source"]) == "civilization":
		_request_civilization()
	else:
		_request_lineage()


func _request_lineage() -> void:
	var evidence := str(_state["evidence_class"])
	var family := str(_state["family"])
	if family == "" or evidence == "":
		_state["resolution"] = "unresolved"
		_state["reason_code"] = "lineage_focus_incomplete"
		changed.emit()
		return
	var query := {
		"evidence_class": evidence,
		"native_kind": str(_state["native_kind"]),
		"native_id": str(_state["native_id"]),
		"limit": 200,
	}
	if evidence != "analytical":
		query["owner_id"] = str(_state["owner_id"])
	if _state["requested_tick"] != null:
		query["boundary_tick"] = int(_state["requested_tick"])
	var path := "/v1/simulations/%s/lineage/%s/nodes" % [_run_id, family]
	_send("lineage_nodes", path, query, "lineage")


func _request_civilization() -> void:
	var layer := "institutions" if str(_state["kind"]) == "institution" else "technology"
	var query := {
		"layer": layer,
		"evidence_class": str(_state["evidence_class"]),
		"limit": 200,
		"tick": int(_state["requested_tick"]),
	}
	if str(_state["evidence_class"]) != "objective":
		query["owner_id"] = str(_state["owner_id"])
	if str(_state["publication_id"]) != "":
		query["publication_id"] = str(_state["publication_id"])
	_send("civilization_overlay", "/v1/simulations/%s/observer/civilization/overlays" % _run_id, query, "civilization")


func _send(kind: String, path: String, query: Dictionary, source: String) -> void:
	if not _sink.is_valid():
		_state["resolution"] = "unresolved"
		_state["reason_code"] = "focus_transport_unavailable"
		changed.emit()
		return
	_sink.call(
		kind,
		path,
		{
			"source": "research_focus",
			"expected_root": "object",
			"focus_epoch": _focus_epoch,
			"run_id": _run_id,
			"credential_generation": _credential_generation,
			"focus_source": source,
		},
		query,
	)


func handle_response(meta: Dictionary, body: Variant, reason_code: String, status: int) -> void:
	if int(meta.get("focus_epoch", -1)) != _focus_epoch:
		return
	if int(meta.get("credential_generation", -1)) != _credential_generation:
		clear("credential_changed")
		return
	if reason_code != "" or status >= 400:
		_state["resolution"] = "unresolved"
		_state["reason_code"] = reason_code if reason_code != "" else "http_%s" % status
		changed.emit()
		return
	if typeof(body) != TYPE_DICTIONARY:
		_state["resolution"] = "unresolved"
		_state["reason_code"] = "invalid_research_response"
		changed.emit()
		return
	if str(meta.get("kind", "")) == "lineage_nodes":
		_handle_lineage_nodes(body)
	elif str(meta.get("kind", "")) == "civilization_overlay":
		_handle_civilization(body)


func _handle_lineage_nodes(body: Dictionary) -> void:
	var snapshot: Dictionary = body.get("snapshot", {}) if typeof(body.get("snapshot", {})) == TYPE_DICTIONARY else {}
	_state["captured_tick"] = snapshot.get("boundary_tick", null)
	_state["coverage"] = body.get("coverage", {})
	var matches: Array = []
	for item in body.get("items", []):
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var ref: Dictionary = item.get("ref", {})
		if typeof(ref) != TYPE_DICTIONARY:
			continue
		if str(ref.get("native_kind", "")) != str(_state["native_kind"]):
			continue
		if str(ref.get("native_id", "")) != str(_state["native_id"]):
			continue
		if str(_state["identity_owner"]) != "" and str(ref.get("identity_owner", "")) != str(_state["identity_owner"]):
			continue
		if str(_state["node_key"]) != "" and str(ref.get("key", "")) != str(_state["node_key"]):
			continue
		matches.append(ref)
	if matches.size() != 1:
		_state["resolution"] = "unresolved"
		_state["root_status"] = "ambiguous" if matches.size() > 1 else "missing"
		_state["reason_code"] = "ambiguous_lineage_node" if matches.size() > 1 else "lineage_node_not_found"
		changed.emit()
		return
	_state["node_key"] = str(matches[0].get("key", ""))
	_state["root_status"] = "matched"
	_state["resolution"] = "resolved"
	_state["rows"] = body.get("items", []).slice(0, MAX_ROWS)
	changed.emit()


func _handle_civilization(body: Dictionary) -> void:
	_state["coverage"] = body.get("coverage", {})
	var publication: Dictionary = body.get("publication", {}) if typeof(body.get("publication", {})) == TYPE_DICTIONARY else {}
	_state["captured_tick"] = (body.get("resolved_cursor", {}) as Dictionary).get("boundary_tick", null)
	var rows: Array = []
	for row in body.get("rows", []):
		if typeof(row) != TYPE_DICTIONARY:
			continue
		rows.append(row)
		if rows.size() >= MAX_ROWS:
			break
	_state["rows"] = rows
	for row in rows:
		var context: Dictionary = row.get("context", {}) if typeof(row.get("context", {})) == TYPE_DICTIONARY else {}
		if str(_state["civilization_row_id"]) != "" and str(context.get("row_id", "")) == str(_state["civilization_row_id"]):
			_state["resolution"] = "resolved"
			_state["root_status"] = "matched_row"
			changed.emit()
			return
	_state["resolution"] = "unresolved"
	_state["root_status"] = "missing"
	_state["reason_code"] = "civilization_row_not_found"
	changed.emit()
