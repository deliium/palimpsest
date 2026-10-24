extends RefCounted

const Lineage := preload("res://scripts/protocol/lineage.gd")
const BASE := "res://fixtures/protocol/generational/"


func run() -> Array:
	var failures: Array = []
	_expect(failures, _families(), "lineage families")
	_expect(failures, _catalogues(), "lineage catalogues")
	_expect(failures, _graph(), "lineage graph")
	_expect(failures, _participants(), "lineage participants")
	_expect(failures, _availability(), "lineage availability")
	_expect(failures, _malformed(), "malformed lineage")
	return failures


func _load(name: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(BASE + name))


func _families() -> String:
	var parsed: Dictionary = Lineage.parse_families(_load("lineage_families.json"))
	if not bool(parsed.get("ok", false)):
		return "family array failed"
	var families: Array = parsed["value"]
	if families.size() != 2 or families[1].family != "mentorship":
		return "families missing"
	if families[0].owner_required:
		return "objective family should not require owner"
	if families[1].available_classes != ["subjective", "analytical"]:
		return "class list missing"
	return ""


func _catalogues() -> String:
	var snapshots: Dictionary = Lineage.parse_snapshot_list(_load("lineage_snapshots.json"))
	if not bool(snapshots.get("ok", false)):
		return "snapshot list failed"
	if snapshots["value"].items[0].boundary_tick != 16:
		return "snapshot boundary missing"
	var nodes: Dictionary = Lineage.parse_node_list(_load("lineage_nodes.json"))
	if not bool(nodes.get("ok", false)):
		return "node list failed"
	var model = nodes["value"]
	if model.items.size() != 2 or model.matched_node_keys.size() != 1:
		return "matched/context nodes missing"
	if model.context_only_node_keys.size() != 1:
		return "context-only key missing"
	if model.items[0].ref.key == model.items[1].ref.key:
		return "opaque keys collapsed"
	return ""


func _graph() -> String:
	var payload: Dictionary = _load("lineage_graph.json")
	var parsed: Dictionary = Lineage.parse_graph(payload)
	if not bool(parsed.get("ok", false)):
		return "graph failed: %s" % parsed.get("reason_code", "")
	var model = parsed["value"]
	if model.nodes.size() != 2 or model.edges.size() != 1:
		return "graph nodes/edges missing"
	var duplicated: Dictionary = payload.duplicate(true)
	duplicated["nodes"].append(duplicated["nodes"][0])
	duplicated["edges"].append(duplicated["edges"][0])
	var deduped: Dictionary = Lineage.parse_graph(duplicated)
	if not bool(deduped.get("ok", false)):
		return "duplicate graph failed"
	if deduped["value"].nodes.size() != 2 or deduped["value"].edges.size() != 1:
		return "server keys did not deduplicate"
	var missing := payload.duplicate(true)
	missing["edges"][0]["target_key"] = "f".repeat(64)
	var broken: Dictionary = Lineage.parse_graph(missing)
	if bool(broken.get("ok", false)):
		return "missing edge endpoint accepted"
	return ""


func _participants() -> String:
	var parsed: Dictionary = Lineage.parse_participants(_load("lineage_participants.json"))
	if not bool(parsed.get("ok", false)):
		return "participants failed: %s" % parsed.get("reason_code", "")
	var model = parsed["value"]
	if model.items.size() != 1 or model.scanned_count != 3:
		return "participant card/scan count missing"
	var card = model.items[0]
	if card.owner_id != "agent-founder" or card.learning_state != "learning_evidence":
		return "participant owner/learning state missing"
	if card.content_key != "content-1" or card.ref.native_kind != "mentorship_entry":
		return "opaque content/native ref missing"
	if model.family != "mentorship" or model.role != "learner":
		return "scope fields missing"
	return ""


func _availability() -> String:
	var parsed: Dictionary = Lineage.parse_availability(_load("lineage_availability.json"))
	if not bool(parsed.get("ok", false)):
		return "availability failed"
	var model = parsed["value"]
	if model.availability != "unavailable" or model.reason_code != "snapshot_unavailable":
		return "availability reason missing"
	if model.requested_boundary_tick != 12 or model.captured_boundary_tick != null:
		return "boundary separation missing"
	return ""


func _malformed() -> String:
	var wrong: Dictionary = Lineage.parse_node_list({"schema_version": "lineage-node-list-v2"})
	if bool(wrong.get("ok", false)):
		return "foreign node-list schema accepted"
	var scalar: Dictionary = Lineage.parse_families({"family": "genealogy"})
	if bool(scalar.get("ok", false)):
		return "object families accepted"
	var bad_snapshot: Dictionary = Lineage.parse_node_list({
		"schema_version": Lineage.NODE_LIST_SCHEMA,
		"snapshot": {"publication_id": "p", "digest": "d", "boundary_tick": 1, "schema_version": "lineage-snapshot-v2"},
		"items": [],
		"matched_node_keys": [],
		"context_only_node_keys": [],
		"declared_count": 0,
		"next_cursor": null,
		"coverage": {"state": "complete", "pruned_count": 0, "unresolved_count": 0},
		"captured_boundary_tick": 1,
		"effective_page_size": 100,
	})
	if not bool(bad_snapshot.get("ok", false)):
		return "valid snapshot fields were rejected"
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
