extends RefCounted
class_name DebuggerLabels

## Presentation-only maps for the research causal debugger inspector.
## Never invents stages, merges evidence, or scores causality.

const ObserverLog := preload("res://scripts/log.gd")

## Closed debugger artifact kinds (inspector chrome only).
const KIND_OBJECTIVE_EVENT := "objective_event"
const KIND_OBSERVATION := "observation"
const KIND_MEMORY := "memory"
const KIND_BELIEF := "belief"
const KIND_IMAGINATION := "imagination"
const KIND_COUNTERFACTUAL := "counterfactual"
const KIND_ANALYTICAL := "analytical_inference"

## Compact strip labels in locked display order.
const COMPACT_SEQUENCE: Array[String] = [
	"Observed",
	"Remembered",
	"Believed",
	"Felt",
	"Wanted",
	"Expected",
	"Decided",
	"Acted",
]

## Server RESEARCHER_CHAIN_SEQUENCE wire codes (Emotion before Goals).
const CHAIN_STAGE_CODES: Array[String] = [
	"observation",
	"relevant_memories",
	"reconstruction",
	"beliefs",
	"emotional_state",
	"goals",
	"theory_of_mind",
	"imagined_futures",
	"counterfactuals",
	"selected_intention",
	"action",
]

const EXPANDED_LABELS := {
	"observation": "Observation",
	"relevant_memories": "Memories",
	"reconstruction": "Reconstructed memory",
	"beliefs": "Beliefs",
	"emotional_state": "Emotion",
	"goals": "Goals",
	"theory_of_mind": "Theory of Mind",
	"imagined_futures": "Imagined futures",
	"counterfactuals": "Counterfactuals",
	"selected_intention": "Intention",
	"action": "Action",
}

## Each of the 11 chain codes belongs to exactly one compact group.
const COMPACT_GROUP_BY_STAGE := {
	"observation": "Observed",
	"relevant_memories": "Remembered",
	"reconstruction": "Remembered",
	"beliefs": "Believed",
	"theory_of_mind": "Believed",
	"emotional_state": "Felt",
	"goals": "Wanted",
	"imagined_futures": "Expected",
	"counterfactuals": "Expected",
	"selected_intention": "Decided",
	"action": "Acted",
}

const ARTIFACT_KIND_BY_STAGE := {
	"observation": KIND_OBSERVATION,
	"relevant_memories": KIND_MEMORY,
	"reconstruction": KIND_MEMORY,
	"beliefs": KIND_BELIEF,
	"theory_of_mind": KIND_BELIEF,
	"emotional_state": KIND_BELIEF,
	"goals": KIND_BELIEF,
	"imagined_futures": KIND_IMAGINATION,
	"counterfactuals": KIND_COUNTERFACTUAL,
	"selected_intention": KIND_BELIEF,
	"action": KIND_OBJECTIVE_EVENT,
	"situation_model": KIND_ANALYTICAL,
	"budget_summary": KIND_ANALYTICAL,
}

const ID_REF_LINEAGE := {
	"memory": "memory_derivation",
	"belief": "belief_evidence",
	"semantic_belief": "belief_evidence",
	"goal": "goal_ancestry",
}

## Status rollup priority when no child is available.
const _ROLLUP_PRIORITY: Array[String] = [
	"truncated",
	"failed",
	"skipped",
	"unavailable",
]

const LEGEND_BY_KIND := {
	KIND_OBJECTIVE_EVENT: "Objective event artifact (committed occurrence; not cognition).",
	KIND_OBSERVATION: "Observation artifact (agent-visible projection; not world truth).",
	KIND_MEMORY: "Memory artifact (subjective recall; not ground truth).",
	KIND_BELIEF: "Belief / attitude artifact (subjective; not ground truth).",
	KIND_IMAGINATION: "Imagination artifact (non-factual structured futures).",
	KIND_COUNTERFACTUAL: "Counterfactual artifact (alternate-path; distinct from imagination).",
	KIND_ANALYTICAL: "Analytical inference artifact (researcher lineage; not world fact).",
}


static func expanded_label(stage_code: String) -> String:
	if EXPANDED_LABELS.has(stage_code):
		return str(EXPANDED_LABELS[stage_code])
	ObserverLog.debug(
		"observer.debugger",
		"unmapped_debugger_stage reason_code=unmapped_debugger_stage stage_code=%s" % stage_code,
	)
	return stage_code


static func compact_label(stage_code: String) -> String:
	if COMPACT_GROUP_BY_STAGE.has(stage_code):
		return str(COMPACT_GROUP_BY_STAGE[stage_code])
	ObserverLog.debug(
		"observer.debugger",
		"unmapped_debugger_stage reason_code=unmapped_debugger_stage stage_code=%s" % stage_code,
	)
	return ""


static func artifact_kind_for_stage(stage_code: String) -> String:
	if ARTIFACT_KIND_BY_STAGE.has(stage_code):
		return str(ARTIFACT_KIND_BY_STAGE[stage_code])
	ObserverLog.debug(
		"observer.debugger",
		"unmapped_debugger_stage reason_code=unmapped_debugger_stage stage_code=%s" % stage_code,
	)
	return KIND_ANALYTICAL


static func legend_for_kind(artifact_kind: String) -> String:
	if LEGEND_BY_KIND.has(artifact_kind):
		return str(LEGEND_BY_KIND[artifact_kind])
	return "Structured artifact (not ground truth)."


static func is_chain_stage(stage_code: String) -> bool:
	return EXPANDED_LABELS.has(stage_code)


static func is_supporting_stage(stage_code: String) -> bool:
	return stage_code == "situation_model" or stage_code == "budget_summary"


static func stages_for_compact(compact: String) -> Array[String]:
	var out: Array[String] = []
	for code in CHAIN_STAGE_CODES:
		if str(COMPACT_GROUP_BY_STAGE.get(code, "")) == compact:
			out.append(code)
	return out


## Locked Expected chrome: counterfactual vs imagination over Expected children.
static func expected_artifact_kind(child_nodes: Array) -> String:
	for node in child_nodes:
		if typeof(node) != TYPE_DICTIONARY:
			continue
		var stage := str(node.get("stage_code", ""))
		if stage != "imagined_futures" and stage != "counterfactuals":
			continue
		var status := str(node.get("status", ""))
		if stage == "counterfactuals" and status != "unavailable" and status != "":
			return KIND_COUNTERFACTUAL
		if _node_has_counterfactual_markers(node):
			return KIND_COUNTERFACTUAL
	return KIND_IMAGINATION


static func lineage_kind_for_id_ref(ref_kind: String, ref_value: String = "") -> String:
	## Closed map only. Unmapped kinds WARN and return empty (no lineage GET).
	var mapped := mapped_lineage_kind(ref_kind, ref_value)
	if mapped != "":
		return mapped
	ObserverLog.warn(
		"observer.debugger",
		"unmapped_debugger_id_ref reason_code=unmapped_debugger_id_ref kind=%s" % ref_kind,
	)
	return ""


static func mapped_lineage_kind(ref_kind: String, ref_value: String = "") -> String:
	## Silent probe for UI affordances — no WARN on unmapped kinds.
	if ID_REF_LINEAGE.has(ref_kind):
		return str(ID_REF_LINEAGE[ref_kind])
	if ref_kind == "future" and _is_prediction_or_cf_subject(ref_value):
		return "prediction"
	return ""


static func can_request_lineage(ref_kind: String, ref_value: String = "") -> bool:
	return mapped_lineage_kind(ref_kind, ref_value) != ""


static func parse_id_refs(raw: Variant) -> Array:
	## Wire shape: JSON arrays of [kind, value] pairs only.
	var out: Array = []
	if typeof(raw) != TYPE_ARRAY:
		return out
	for item in raw:
		if typeof(item) != TYPE_ARRAY:
			continue
		var pair: Array = item
		if pair.size() < 2:
			continue
		out.append({"kind": str(pair[0]), "value": str(pair[1])})
	return out


## Compact status rollup over child wire nodes (locked priority).
static func rollup_status(child_nodes: Array) -> Dictionary:
	## Returns {status, reason_code}. reason_code empty when available.
	var by_status := {}
	for node in child_nodes:
		if typeof(node) != TYPE_DICTIONARY:
			continue
		var status := str(node.get("status", ""))
		if status == "":
			continue
		if not by_status.has(status):
			by_status[status] = []
		(by_status[status] as Array).append(node)
	if by_status.has("available"):
		return {"status": "available", "reason_code": ""}
	for candidate in _ROLLUP_PRIORITY:
		if not by_status.has(candidate):
			continue
		var contributors: Array = by_status[candidate]
		var reason := ""
		for node in contributors:
			reason = str(node.get("reason_code", ""))
			if reason != "":
				break
		ObserverLog.debug(
			"observer.debugger",
			"compact_rollup status=%s reason_code=%s child_count=%s" % [
				candidate, reason, contributors.size(),
			],
		)
		return {"status": candidate, "reason_code": reason}
	return {"status": "unavailable", "reason_code": "no_child_status"}


static func group_nodes_by_compact(nodes: Array) -> Dictionary:
	## Maps compact label → Array of chain nodes (supporting excluded).
	var groups := {}
	for label in COMPACT_SEQUENCE:
		groups[label] = []
	for node in nodes:
		if typeof(node) != TYPE_DICTIONARY:
			continue
		var stage := str(node.get("stage_code", ""))
		if is_supporting_stage(stage):
			continue
		var compact := compact_label(stage)
		if compact == "" or not groups.has(compact):
			continue
		(groups[compact] as Array).append(node)
	return groups


static func chain_nodes_ordered(nodes: Array) -> Array:
	## Full expanded rows in server RESEARCHER_CHAIN_SEQUENCE order.
	var by_stage := {}
	for node in nodes:
		if typeof(node) != TYPE_DICTIONARY:
			continue
		var stage := str(node.get("stage_code", ""))
		if not is_chain_stage(stage):
			continue
		by_stage[stage] = node
	var ordered: Array = []
	for code in CHAIN_STAGE_CODES:
		if by_stage.has(code):
			ordered.append(by_stage[code])
	return ordered


static func supporting_nodes(nodes: Array) -> Array:
	var out: Array = []
	for node in nodes:
		if typeof(node) != TYPE_DICTIONARY:
			continue
		var stage := str(node.get("stage_code", ""))
		if is_supporting_stage(stage) or bool(node.get("secondary", false)):
			out.append(node)
	return out


static func _node_has_counterfactual_markers(node: Dictionary) -> bool:
	var refs := parse_id_refs(node.get("id_refs", []))
	for ref in refs:
		var kind := str(ref.get("kind", ""))
		var value := str(ref.get("value", ""))
		if kind == "future" and _is_prediction_or_cf_subject(value):
			return true
		if _is_prediction_or_cf_subject(value) or value.to_lower().begins_with("counterfactual"):
			return true
	var codes: Variant = node.get("selection_codes", [])
	if typeof(codes) == TYPE_ARRAY:
		for code in codes:
			var token := str(code).to_lower()
			if token == "counterfactual" or token.begins_with("cf_"):
				return true
	return false


static func _is_prediction_or_cf_subject(value: String) -> bool:
	var token := value.strip_edges().to_lower()
	if token.is_empty():
		return false
	if token.begins_with("cf_") or token.begins_with("pred_"):
		return true
	if token.begins_with("prediction") or token.begins_with("counterfactual"):
		return true
	return false
