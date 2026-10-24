class_name ObserverLineage

## Strict read-only parsers for lineage catalogue, graph and participant
## projections. Identity keys stay opaque server strings.

const FAMILIES_SCHEMA := "lineage-family-list-v1"
const SNAPSHOT_LIST_SCHEMA := "lineage-snapshot-list-v1"
const NODE_LIST_SCHEMA := "lineage-node-list-v1"
const GRAPH_SCHEMA := "lineage-graph-page-v1"
const PARTICIPANTS_SCHEMA := "lineage-participants-v1"
const AVAILABILITY_SCHEMA := "lineage-availability-v1"


class SnapshotModel:
	extends RefCounted
	var publication_id: String = ""
	var digest: String = ""
	var boundary_tick: int = 0
	var schema_version: String = ""


class CoverageModel:
	extends RefCounted
	var state: String = ""
	var reason_codes: Array = []
	var capture_start_tick: Variant = null
	var capture_end_tick: Variant = null
	var missing_prefix_tick: Variant = null
	var pruned_count: int = 0
	var unresolved_count: int = 0
	var policy_version: Variant = null


class EvidenceRefModel:
	extends RefCounted
	var evidence_class: String = ""
	var native_kind: String = ""
	var native_id: String = ""
	var owner_id: Variant = null
	var observed_tick: Variant = null


class NodeRefModel:
	extends RefCounted
	var run_id: String = ""
	var family: String = ""
	var evidence_class: String = ""
	var native_kind: String = ""
	var native_id: String = ""
	var identity_owner: Variant = null
	var key: String = ""


class NodeModel:
	extends RefCounted
	var ref: NodeRefModel = null
	var state: String = ""
	var living: Variant = null
	var observed_tick: Variant = null
	var status_code: Variant = null
	var confidence_code: Variant = null
	var confidence_value: Variant = null
	var unresolved_reason: Variant = null
	var native_revision: Variant = null
	var evidence_refs: Array = []
	var counts: Dictionary = {}
	var source_observed_boundary: Variant = null


class EdgeModel:
	extends RefCounted
	var edge_key: String = ""
	var source_key: String = ""
	var target_key: String = ""
	var relation: String = ""
	var native_kind: String = ""
	var native_id: String = ""
	var claim_owner_id: Variant = null
	var observed_tick: Variant = null
	var status_code: Variant = null


class FamilyModel:
	extends RefCounted
	var family: String = ""
	var available_classes: Array = []
	var owner_required: bool = false
	var directions: Array = []
	var max_depth: int = 0
	var max_nodes: int = 0
	var max_edges: int = 0
	var max_page_size: int = 0


class SnapshotListModel:
	extends RefCounted
	var schema_version: String = ""
	var items: Array = []
	var declared_count: int = 0
	var next_cursor: Variant = null


class NodeListModel:
	extends RefCounted
	var schema_version: String = ""
	var snapshot: SnapshotModel = null
	var items: Array = []
	var matched_node_keys: Array = []
	var context_only_node_keys: Array = []
	var declared_count: int = 0
	var next_cursor: Variant = null
	var coverage: CoverageModel = null
	var requested_boundary_tick: Variant = null
	var captured_boundary_tick: int = 0
	var effective_page_size: int = 0


class GraphModel:
	extends RefCounted
	var schema_version: String = ""
	var snapshot: SnapshotModel = null
	var nodes: Array = []
	var edges: Array = []
	var matched_node_keys: Array = []
	var context_only_node_keys: Array = []
	var next_cursor: Variant = null
	var coverage: CoverageModel = null
	var truncated: bool = false
	var stop_reason_code: Variant = null
	var requested_boundary_tick: Variant = null
	var captured_boundary_tick: int = 0
	var effective_page_size: int = 0


class ParticipantCardModel:
	extends RefCounted
	var ref: NodeRefModel = null
	var teacher_id: String = ""
	var learner_id: String = ""
	var owner_id: String = ""
	var lineage_id: String = ""
	var root_id: String = ""
	var parent_ids: Array = []
	var content_kind: String = ""
	var content_key: String = ""
	var hop: int = 0
	var acquisition_tick: int = 0
	var update_tick: int = 0
	var attempt_count: int = 0
	var learning_evidence_count: int = 0
	var confidence_band: Variant = null
	var mutated: bool = false
	var native_status: Variant = null
	var evidence_refs: Array = []
	var policy_version: String = ""
	var observed_boundary: int = 0
	var source_observed_boundary: int = 0
	var learning_state: String = ""


class ParticipantsModel:
	extends RefCounted
	var schema_version: String = ""
	var snapshot: SnapshotModel = null
	var requested_boundary_tick: Variant = null
	var captured_boundary_tick: int = 0
	var family: String = ""
	var evidence_class: String = ""
	var owner_id: Variant = null
	var agent_id: String = ""
	var role: String = ""
	var items: Array = []
	var scanned_count: int = 0
	var unprojectable_count: int = 0
	var scan_limited: bool = false
	var coverage: CoverageModel = null
	var next_cursor: Variant = null
	var effective_page_size: int = 0


class AvailabilityModel:
	extends RefCounted
	var schema_version: String = ""
	var availability: String = ""
	var reason_code: String = ""
	var family: String = ""
	var evidence_class: String = ""
	var requested_boundary_tick: Variant = null
	var captured_boundary_tick: Variant = null


static func parse_families(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_ARRAY:
		return _failure("lineage_invalid")
	var families: Array = []
	for item in payload:
		if typeof(item) != TYPE_DICTIONARY:
			return _failure("lineage_invalid")
		if not _is_string(item.get("family")):
			return _failure("lineage_invalid")
		var classes: Variant = item.get("available_classes")
		if typeof(classes) != TYPE_ARRAY or classes.is_empty():
			return _failure("lineage_invalid")
		for value in classes:
			if not _is_string(value):
				return _failure("lineage_invalid")
		var model := FamilyModel.new()
		model.family = item["family"]
		model.available_classes = classes.duplicate()
		model.owner_required = bool(item.get("owner_required", false))
		if typeof(item.get("owner_required", false)) != TYPE_BOOL:
			return _failure("lineage_invalid")
		model.directions = _string_array(item.get("directions"))
		if model.directions.is_empty():
			return _failure("lineage_invalid")
		for key in ["max_depth", "max_nodes", "max_edges", "max_page_size"]:
			if not _is_nonneg_int(item.get(key)):
				return _failure("lineage_invalid")
		model.max_depth = item["max_depth"]
		model.max_nodes = item["max_nodes"]
		model.max_edges = item["max_edges"]
		model.max_page_size = item["max_page_size"]
		families.append(model)
	return {"ok": true, "value": families}


static func parse_snapshot_list(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY:
		return _failure("lineage_invalid")
	if payload.get("schema_version") != SNAPSHOT_LIST_SCHEMA:
		return _failure("lineage_invalid")
	if not _is_nonneg_int(payload.get("declared_count")):
		return _failure("lineage_invalid")
	if not _is_optional_string(payload.get("next_cursor")):
		return _failure("lineage_invalid")
	var snapshots: Array = []
	for item in _array(payload.get("items")):
		var snapshot: Variant = _snapshot(item)
		if snapshot == null:
			return _failure("lineage_invalid")
		snapshots.append(snapshot)
	var model := SnapshotListModel.new()
	model.schema_version = SNAPSHOT_LIST_SCHEMA
	model.items = snapshots
	model.declared_count = payload["declared_count"]
	model.next_cursor = payload.get("next_cursor")
	return {"ok": true, "value": model}


static func parse_node_list(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY:
		return _failure("lineage_invalid")
	if payload.get("schema_version") != NODE_LIST_SCHEMA:
		return _failure("lineage_invalid")
	var snapshot: Variant = _snapshot(payload.get("snapshot"))
	if snapshot == null:
		return _failure("lineage_invalid")
	var parsed := _nodes_and_edges(payload.get("items"))
	if not bool(parsed.get("ok", false)):
		return parsed
	var coverage: Variant = _coverage(payload.get("coverage"))
	if coverage == null:
		return _failure("lineage_invalid")
	if not _is_nonneg_int(payload.get("declared_count")):
		return _failure("lineage_invalid")
	if not _is_bounded_page(payload.get("effective_page_size")):
		return _failure("lineage_invalid")
	if not _is_optional_nonneg_int(payload.get("requested_boundary_tick")):
		return _failure("lineage_invalid")
	if not _is_nonneg_int(payload.get("captured_boundary_tick")):
		return _failure("lineage_invalid")
	var model := NodeListModel.new()
	model.schema_version = NODE_LIST_SCHEMA
	model.snapshot = snapshot
	model.items = parsed["nodes"]
	model.matched_node_keys = _key_array(payload.get("matched_node_keys"))
	model.context_only_node_keys = _key_array(payload.get("context_only_node_keys"))
	model.declared_count = payload["declared_count"]
	model.next_cursor = payload.get("next_cursor")
	if not _is_optional_string(model.next_cursor):
		return _failure("lineage_invalid")
	model.coverage = coverage
	model.requested_boundary_tick = payload.get("requested_boundary_tick")
	model.captured_boundary_tick = payload["captured_boundary_tick"]
	model.effective_page_size = payload["effective_page_size"]
	return {"ok": true, "value": model}


static func parse_graph(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY:
		return _failure("lineage_invalid")
	if payload.get("schema_version") != GRAPH_SCHEMA:
		return _failure("lineage_invalid")
	var snapshot: Variant = _snapshot(payload.get("snapshot"))
	if snapshot == null:
		return _failure("lineage_invalid")
	var parsed := _nodes_and_edges(payload.get("nodes"))
	if not bool(parsed.get("ok", false)):
		return parsed
	var nodes_by_key: Dictionary = {}
	for node in parsed["nodes"]:
		nodes_by_key[node.ref.key] = node
	var edges: Array = []
	var seen_edges: Dictionary = {}
	for raw in _array(payload.get("edges")):
		if typeof(raw) != TYPE_DICTIONARY:
			return _failure("lineage_invalid")
		var edge: Variant = _edge(raw)
		if edge == null:
			return _failure("lineage_invalid")
		if not nodes_by_key.has(edge.source_key) or not nodes_by_key.has(edge.target_key):
			return _failure("lineage_invalid")
		if seen_edges.has(edge.edge_key):
			continue
		seen_edges[edge.edge_key] = true
		edges.append(edge)
	var coverage: Variant = _coverage(payload.get("coverage"))
	if coverage == null:
		return _failure("lineage_invalid")
	if typeof(payload.get("truncated", false)) != TYPE_BOOL:
		return _failure("lineage_invalid")
	if not _is_bounded_page(payload.get("effective_page_size")):
		return _failure("lineage_invalid")
	if not _is_optional_nonneg_int(payload.get("requested_boundary_tick")):
		return _failure("lineage_invalid")
	if not _is_nonneg_int(payload.get("captured_boundary_tick")):
		return _failure("lineage_invalid")
	if not _is_optional_string(payload.get("next_cursor")):
		return _failure("lineage_invalid")
	var model := GraphModel.new()
	model.schema_version = GRAPH_SCHEMA
	model.snapshot = snapshot
	model.nodes = parsed["nodes"]
	model.edges = edges
	model.matched_node_keys = _key_array(payload.get("matched_node_keys"))
	model.context_only_node_keys = _key_array(payload.get("context_only_node_keys"))
	model.next_cursor = payload.get("next_cursor")
	model.coverage = coverage
	model.truncated = bool(payload.get("truncated", false))
	model.stop_reason_code = payload.get("stop_reason_code")
	if not _is_optional_string(model.stop_reason_code):
		return _failure("lineage_invalid")
	model.requested_boundary_tick = payload.get("requested_boundary_tick")
	model.captured_boundary_tick = payload["captured_boundary_tick"]
	model.effective_page_size = payload["effective_page_size"]
	return {"ok": true, "value": model}


static func parse_participants(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY:
		return _failure("lineage_invalid")
	if payload.get("schema_version") != PARTICIPANTS_SCHEMA:
		return _failure("lineage_invalid")
	var snapshot: Variant = _snapshot(payload.get("snapshot"))
	if snapshot == null:
		return _failure("lineage_invalid")
	if payload.get("family") != "mentorship":
		return _failure("lineage_invalid")
	if payload.get("evidence_class") not in ["subjective", "analytical"]:
		return _failure("lineage_invalid")
	if payload.get("role") not in ["teacher", "learner", "both"]:
		return _failure("lineage_invalid")
	if not _is_string(payload.get("agent_id")):
		return _failure("lineage_invalid")
	if not _is_optional_string(payload.get("owner_id")):
		return _failure("lineage_invalid")
	if not _is_nonneg_int(payload.get("captured_boundary_tick")):
		return _failure("lineage_invalid")
	if not _is_optional_nonneg_int(payload.get("requested_boundary_tick")):
		return _failure("lineage_invalid")
	if not _is_nonneg_int(payload.get("scanned_count")):
		return _failure("lineage_invalid")
	if not _is_nonneg_int(payload.get("unprojectable_count")):
		return _failure("lineage_invalid")
	if typeof(payload.get("scan_limited")) != TYPE_BOOL:
		return _failure("lineage_invalid")
	if not _is_bounded_page(payload.get("effective_page_size")):
		return _failure("lineage_invalid")
	if not _is_optional_string(payload.get("next_cursor")):
		return _failure("lineage_invalid")
	var coverage: Variant = _coverage(payload.get("coverage"))
	if coverage == null:
		return _failure("lineage_invalid")
	var items: Array = []
	var seen_keys: Dictionary = {}
	for raw in _array(payload.get("items")):
		var card: Variant = _participant_card(raw)
		if card == null:
			return _failure("lineage_invalid")
		if seen_keys.has(card.ref.key):
			continue
		seen_keys[card.ref.key] = true
		items.append(card)
	var model := ParticipantsModel.new()
	model.schema_version = PARTICIPANTS_SCHEMA
	model.snapshot = snapshot
	model.requested_boundary_tick = payload.get("requested_boundary_tick")
	model.captured_boundary_tick = payload["captured_boundary_tick"]
	model.family = "mentorship"
	model.evidence_class = payload["evidence_class"]
	model.owner_id = payload.get("owner_id")
	model.agent_id = payload["agent_id"]
	model.role = payload["role"]
	model.items = items
	model.scanned_count = payload["scanned_count"]
	model.unprojectable_count = payload["unprojectable_count"]
	model.scan_limited = bool(payload["scan_limited"])
	model.coverage = coverage
	model.next_cursor = payload.get("next_cursor")
	model.effective_page_size = payload["effective_page_size"]
	return {"ok": true, "value": model}


static func parse_availability(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY:
		return _failure("lineage_invalid")
	if payload.get("schema_version") != AVAILABILITY_SCHEMA:
		return _failure("lineage_invalid")
	if payload.get("availability") != "unavailable":
		return _failure("lineage_invalid")
	if not _is_string(payload.get("reason_code")):
		return _failure("lineage_invalid")
	if not _is_string(payload.get("family")):
		return _failure("lineage_invalid")
	if not _is_string(payload.get("evidence_class")):
		return _failure("lineage_invalid")
	if not _is_optional_nonneg_int(payload.get("requested_boundary_tick")):
		return _failure("lineage_invalid")
	if not _is_optional_nonneg_int(payload.get("captured_boundary_tick")):
		return _failure("lineage_invalid")
	var model := AvailabilityModel.new()
	model.schema_version = AVAILABILITY_SCHEMA
	model.availability = "unavailable"
	model.reason_code = payload["reason_code"]
	model.family = payload["family"]
	model.evidence_class = payload["evidence_class"]
	model.requested_boundary_tick = payload.get("requested_boundary_tick")
	model.captured_boundary_tick = payload.get("captured_boundary_tick")
	return {"ok": true, "value": model}


static func _nodes_and_edges(value: Variant) -> Dictionary:
	if typeof(value) != TYPE_ARRAY:
		return _failure("lineage_invalid")
	var nodes: Array = []
	var seen: Dictionary = {}
	for raw in value:
		var node: Variant = _node(raw)
		if node == null:
			return _failure("lineage_invalid")
		if seen.has(node.ref.key):
			continue
		seen[node.ref.key] = true
		nodes.append(node)
	return {"ok": true, "nodes": nodes}


static func _snapshot(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if not _is_string(value.get("publication_id")):
		return null
	if not _is_string(value.get("digest")):
		return null
	if not _is_string(value.get("schema_version")):
		return null
	if not _is_nonneg_int(value.get("boundary_tick")):
		return null
	var model := SnapshotModel.new()
	model.publication_id = value["publication_id"]
	model.digest = value["digest"]
	model.boundary_tick = value["boundary_tick"]
	model.schema_version = value["schema_version"]
	return model


static func _coverage(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if value.get("state") not in ["complete", "partial", "unavailable", "disabled"]:
		return null
	for key in ["pruned_count", "unresolved_count"]:
		if not _is_nonneg_int(value.get(key, 0)):
			return null
	if not _is_optional_nonneg_int(value.get("capture_start_tick")):
		return null
	if not _is_optional_nonneg_int(value.get("capture_end_tick")):
		return null
	if not _is_optional_nonneg_int(value.get("missing_prefix_tick")):
		return null
	if not _is_optional_string(value.get("policy_version")):
		return null
	var model := CoverageModel.new()
	model.state = value["state"]
	model.reason_codes = _string_array(value.get("reason_codes", []))
	model.capture_start_tick = value.get("capture_start_tick")
	model.capture_end_tick = value.get("capture_end_tick")
	model.missing_prefix_tick = value.get("missing_prefix_tick")
	model.pruned_count = int(value.get("pruned_count", 0))
	model.unresolved_count = int(value.get("unresolved_count", 0))
	model.policy_version = value.get("policy_version")
	return model


static func _node(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	var ref: Variant = _node_ref(value.get("ref"))
	if ref == null:
		return null
	if value.get("state") not in ["observed", "archived", "unresolved"]:
		return null
	if not _is_optional_string(value.get("status_code")):
		return null
	if not _is_optional_string(value.get("confidence_code")):
		return null
	if not _is_optional_nonneg_int(value.get("observed_tick")):
		return null
	if not _is_optional_nonneg_int(value.get("source_observed_boundary")):
		return null
	var evidence: Array = []
	for raw in _array(value.get("evidence_refs", [])):
		var item: Variant = _evidence_ref(raw)
		if item == null:
			return null
		evidence.append(item)
	var counts: Dictionary = {}
	var raw_counts: Variant = value.get("counts", {})
	if typeof(raw_counts) != TYPE_DICTIONARY:
		return null
	for key in raw_counts.keys():
		if not _is_string(str(key)) or not _is_nonneg_int(raw_counts[key]):
			return null
		counts[str(key)] = int(raw_counts[key])
	var model := NodeModel.new()
	model.ref = ref
	model.state = value["state"]
	model.living = value.get("living")
	if model.living != null and typeof(model.living) != TYPE_BOOL:
		return null
	model.observed_tick = value.get("observed_tick")
	model.status_code = value.get("status_code")
	model.confidence_code = value.get("confidence_code")
	model.confidence_value = value.get("confidence_value")
	model.unresolved_reason = value.get("unresolved_reason")
	model.native_revision = value.get("native_revision")
	model.evidence_refs = evidence
	model.counts = counts
	model.source_observed_boundary = value.get("source_observed_boundary")
	return model


static func _edge(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	for key in ["edge_key", "source_key", "target_key", "relation", "native_kind", "native_id"]:
		if not _is_string(value.get(key)):
			return null
	if not _is_optional_nonneg_int(value.get("observed_tick")):
		return null
	if not _is_optional_string(value.get("status_code")):
		return null
	var model := EdgeModel.new()
	model.edge_key = value["edge_key"]
	model.source_key = value["source_key"]
	model.target_key = value["target_key"]
	model.relation = value["relation"]
	model.native_kind = value["native_kind"]
	model.native_id = value["native_id"]
	model.claim_owner_id = value.get("claim_owner_id")
	model.observed_tick = value.get("observed_tick")
	model.status_code = value.get("status_code")
	return model


static func _participant_card(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	var ref: Variant = _node_ref(value.get("ref"))
	if ref == null:
		return null
	for key in [
		"teacher_id",
		"learner_id",
		"owner_id",
		"lineage_id",
		"root_id",
		"content_kind",
		"content_key",
		"policy_version",
	]:
		if not _is_string(value.get(key)):
			return null
	for key in ["hop", "acquisition_tick", "update_tick", "attempt_count", "learning_evidence_count", "observed_boundary", "source_observed_boundary"]:
		if not _is_nonneg_int(value.get(key)):
			return null
	if typeof(value.get("mutated")) != TYPE_BOOL:
		return null
	if not _is_optional_string(value.get("confidence_band")):
		return null
	if not _is_optional_string(value.get("native_status")):
		return null
	if value.get("learning_state") not in ["attempt_only", "learning_evidence"]:
		return null
	var evidence: Array = []
	for raw in _array(value.get("evidence_refs")):
		var item: Variant = _evidence_ref(raw)
		if item == null:
			return null
		evidence.append(item)
	var parents := _string_array(value.get("parent_ids", []))
	var model := ParticipantCardModel.new()
	model.ref = ref
	model.teacher_id = value["teacher_id"]
	model.learner_id = value["learner_id"]
	model.owner_id = value["owner_id"]
	model.lineage_id = value["lineage_id"]
	model.root_id = value["root_id"]
	model.parent_ids = parents
	model.content_kind = value["content_kind"]
	model.content_key = value["content_key"]
	model.hop = value["hop"]
	model.acquisition_tick = value["acquisition_tick"]
	model.update_tick = value["update_tick"]
	model.attempt_count = value["attempt_count"]
	model.learning_evidence_count = value["learning_evidence_count"]
	model.confidence_band = value.get("confidence_band")
	model.mutated = value["mutated"]
	model.native_status = value.get("native_status")
	model.evidence_refs = evidence
	model.policy_version = value["policy_version"]
	model.observed_boundary = value["observed_boundary"]
	model.source_observed_boundary = value["source_observed_boundary"]
	model.learning_state = value["learning_state"]
	return model


static func _node_ref(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	for key in ["run_id", "family", "evidence_class", "native_kind", "native_id", "key"]:
		if not _is_string(value.get(key)):
			return null
	if not _is_optional_string(value.get("identity_owner")):
		return null
	var model := NodeRefModel.new()
	model.run_id = value["run_id"]
	model.family = value["family"]
	model.evidence_class = value["evidence_class"]
	model.native_kind = value["native_kind"]
	model.native_id = value["native_id"]
	model.identity_owner = value.get("identity_owner")
	model.key = value["key"]
	return model


static func _evidence_ref(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	for key in ["evidence_class", "native_kind", "native_id"]:
		if not _is_string(value.get(key)):
			return null
	if not _is_optional_string(value.get("owner_id")):
		return null
	if not _is_optional_nonneg_int(value.get("observed_tick")):
		return null
	var model := EvidenceRefModel.new()
	model.evidence_class = value["evidence_class"]
	model.native_kind = value["native_kind"]
	model.native_id = value["native_id"]
	model.owner_id = value.get("owner_id")
	model.observed_tick = value.get("observed_tick")
	return model


static func _failure(reason_code: String) -> Dictionary:
	return {"ok": false, "reason_code": reason_code}


static func _array(value: Variant) -> Array:
	return value if typeof(value) == TYPE_ARRAY else []


static func _string_array(value: Variant) -> Array:
	if typeof(value) != TYPE_ARRAY:
		return []
	var result: Array = []
	for item in value:
		if not _is_string(item):
			return []
		result.append(item)
	return result


static func _key_array(value: Variant) -> Array:
	return _string_array(value)


static func _is_string(value: Variant) -> bool:
	return typeof(value) == TYPE_STRING and not str(value).is_empty()


static func _is_optional_string(value: Variant) -> bool:
	return value == null or _is_string(value)


static func _is_nonneg_int(value: Variant) -> bool:
	if typeof(value) == TYPE_INT:
		return int(value) >= 0
	if typeof(value) == TYPE_FLOAT:
		return is_finite(value) and float(value) == floor(float(value)) and float(value) >= 0.0
	return false


static func _is_optional_nonneg_int(value: Variant) -> bool:
	return value == null or _is_nonneg_int(value)


static func _is_bounded_page(value: Variant) -> bool:
	return _is_nonneg_int(value) and int(value) >= 1 and int(value) <= 200
