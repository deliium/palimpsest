extends RefCounted

const DebuggerLabels := preload("res://scripts/presentation/debugger_labels.gd")
const Log := preload("res://scripts/log.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _chain_coverage(), "chain coverage")
	_expect(failures, _compact_partition(), "compact partition")
	_expect(failures, _id_ref_map(), "id_ref map")
	_expect(failures, _expected_chrome(), "expected chrome")
	_expect(failures, _rollup_priority(), "rollup priority")
	_expect(failures, _parse_id_refs(), "parse id_refs")
	_expect(failures, _legends_non_objective(), "legends")
	return failures


func _chain_coverage() -> String:
	if DebuggerLabels.CHAIN_STAGE_CODES.size() != 11:
		return "expected 11 chain codes"
	for code in DebuggerLabels.CHAIN_STAGE_CODES:
		var expanded := DebuggerLabels.expanded_label(code)
		if expanded == "" or expanded == code and not DebuggerLabels.EXPANDED_LABELS.has(code):
			return "missing expanded label for %s" % code
		if DebuggerLabels.compact_label(code) == "":
			return "missing compact label for %s" % code
		if DebuggerLabels.artifact_kind_for_stage(code) == "":
			return "missing artifact kind for %s" % code
	# Emotion before Goals in expanded order.
	var emotion_idx := DebuggerLabels.CHAIN_STAGE_CODES.find("emotional_state")
	var goals_idx := DebuggerLabels.CHAIN_STAGE_CODES.find("goals")
	if emotion_idx < 0 or goals_idx < 0 or emotion_idx >= goals_idx:
		return "Emotion must precede Goals in chain order"
	if DebuggerLabels.expanded_label("emotional_state") != "Emotion":
		return "emotional_state label"
	if DebuggerLabels.expanded_label("goals") != "Goals":
		return "goals label"
	return ""


func _compact_partition() -> String:
	if DebuggerLabels.COMPACT_SEQUENCE.size() != 8:
		return "expected 8 compact labels"
	var seen := {}
	for code in DebuggerLabels.CHAIN_STAGE_CODES:
		var compact := DebuggerLabels.compact_label(code)
		if compact not in DebuggerLabels.COMPACT_SEQUENCE:
			return "stage %s maps outside compact strip" % code
		if seen.has(code):
			return "duplicate stage %s" % code
		seen[code] = compact
	if seen.size() != 11:
		return "partition must cover all 11 codes"
	# Supporting stages must not enter compact strip.
	if DebuggerLabels.compact_label("situation_model") != "":
		return "situation_model must not join compact strip"
	if DebuggerLabels.is_supporting_stage("budget_summary") != true:
		return "budget_summary should be supporting"
	return ""


func _id_ref_map() -> String:
	if DebuggerLabels.lineage_kind_for_id_ref("memory") != "memory_derivation":
		return "memory map"
	if DebuggerLabels.lineage_kind_for_id_ref("belief") != "belief_evidence":
		return "belief map"
	if DebuggerLabels.lineage_kind_for_id_ref("semantic_belief") != "belief_evidence":
		return "semantic_belief map"
	if DebuggerLabels.lineage_kind_for_id_ref("goal") != "goal_ancestry":
		return "goal map"
	if DebuggerLabels.lineage_kind_for_id_ref("future", "cf_alt_1") != "prediction":
		return "cf future should map to prediction"
	if DebuggerLabels.lineage_kind_for_id_ref("future", "pred_42") != "prediction":
		return "prediction future should map"
	var unmapped := DebuggerLabels.lineage_kind_for_id_ref("drive", "hunger")
	if unmapped != "":
		return "drive must be rejected"
	var logged := "\n".join(Log.recent)
	if "unmapped_debugger_id_ref" not in logged:
		return "unmapped id_ref must WARN"
	if DebuggerLabels.lineage_kind_for_id_ref("future", "future-plain") != "":
		return "plain future must be rejected"
	if DebuggerLabels.lineage_kind_for_id_ref("emotion", "fear") != "":
		return "emotion must be rejected"
	return ""


func _expected_chrome() -> String:
	var imagination_only: Array = [
		{"stage_code": "imagined_futures", "status": "available", "id_refs": [], "selection_codes": []},
		{"stage_code": "counterfactuals", "status": "unavailable", "reason_code": "counterfactual_unavailable"},
	]
	if DebuggerLabels.expected_artifact_kind(imagination_only) != DebuggerLabels.KIND_IMAGINATION:
		return "default Expected chrome should be imagination"
	var cf_status: Array = [
		{"stage_code": "imagined_futures", "status": "available"},
		{"stage_code": "counterfactuals", "status": "available"},
	]
	if DebuggerLabels.expected_artifact_kind(cf_status) != DebuggerLabels.KIND_COUNTERFACTUAL:
		return "non-unavailable counterfactuals stage should force counterfactual chrome"
	var cf_codes: Array = [
		{
			"stage_code": "imagined_futures",
			"status": "available",
			"selection_codes": ["cf_branch_a"],
			"id_refs": [],
		},
		{"stage_code": "counterfactuals", "status": "unavailable"},
	]
	if DebuggerLabels.expected_artifact_kind(cf_codes) != DebuggerLabels.KIND_COUNTERFACTUAL:
		return "cf_* selection_codes should force counterfactual chrome"
	var cf_refs: Array = [
		{
			"stage_code": "imagined_futures",
			"status": "available",
			"id_refs": [["future", "cf_scenario_1"]],
			"selection_codes": [],
		},
	]
	if DebuggerLabels.expected_artifact_kind(cf_refs) != DebuggerLabels.KIND_COUNTERFACTUAL:
		return "cf id_refs should force counterfactual chrome"
	return ""


func _rollup_priority() -> String:
	var available := DebuggerLabels.rollup_status([
		{"status": "unavailable", "reason_code": "stage_missing"},
		{"status": "available", "reason_code": ""},
		{"status": "failed", "reason_code": "boom"},
	])
	if str(available.get("status", "")) != "available":
		return "any available wins"
	var truncated := DebuggerLabels.rollup_status([
		{"status": "unavailable", "reason_code": "gone"},
		{"status": "truncated", "reason_code": "too_long"},
		{"status": "failed", "reason_code": "boom"},
	])
	if str(truncated.get("status", "")) != "truncated":
		return "truncated before failed"
	if str(truncated.get("reason_code", "")) != "too_long":
		return "reason from contributing status child"
	var failed := DebuggerLabels.rollup_status([
		{"status": "skipped", "reason_code": "skip"},
		{"status": "failed", "reason_code": "err"},
		{"status": "unavailable", "reason_code": "gone"},
	])
	if str(failed.get("status", "")) != "failed":
		return "failed before skipped"
	return ""


func _parse_id_refs() -> String:
	var parsed := DebuggerLabels.parse_id_refs([["memory", "mem-1"], ["belief", "b-2"], "bad"])
	if parsed.size() != 2:
		return "should keep [kind,value] pairs only"
	if str(parsed[0].get("kind", "")) != "memory" or str(parsed[0].get("value", "")) != "mem-1":
		return "first pair"
	if typeof(DebuggerLabels.parse_id_refs({"memory": "x"})) != TYPE_ARRAY:
		return "non-array should yield empty"
	if not DebuggerLabels.parse_id_refs({"memory": "x"}).is_empty():
		return "non-array must be empty"
	return ""


func _legends_non_objective() -> String:
	for kind in [
		DebuggerLabels.KIND_OBSERVATION,
		DebuggerLabels.KIND_MEMORY,
		DebuggerLabels.KIND_BELIEF,
		DebuggerLabels.KIND_IMAGINATION,
		DebuggerLabels.KIND_COUNTERFACTUAL,
		DebuggerLabels.KIND_ANALYTICAL,
	]:
		var text := DebuggerLabels.legend_for_kind(kind)
		if "ground truth" not in text.to_lower() and "not world" not in text.to_lower() and "non-factual" not in text.to_lower() and "not cognition" not in text.to_lower() and "not world fact" not in text.to_lower() and "researcher" not in text.to_lower() and "agent-visible" not in text.to_lower():
			# Softer check: legends must mark non-objective kinds explicitly.
			if "not" not in text.to_lower() and "non-" not in text.to_lower() and "researcher" not in text.to_lower() and "subjective" not in text.to_lower() and "alternate" not in text.to_lower() and "projection" not in text.to_lower():
				return "legend missing non-objective marker for %s" % kind
	var objective := DebuggerLabels.legend_for_kind(DebuggerLabels.KIND_OBJECTIVE_EVENT)
	if objective == "":
		return "objective legend missing"
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
