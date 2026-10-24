extends RefCounted

const Demographics := preload("res://scripts/protocol/demographics.gd")
const BASE := "res://fixtures/protocol/generational/"


func run() -> Array:
	var failures: Array = []
	_expect(failures, _agents_page(), "demographic agent page")
	_expect(failures, _unavailable(), "demographic unavailable")
	_expect(failures, _cohorts_page(), "demographic cohorts page")
	_expect(failures, _markers(), "generation markers")
	_expect(failures, _markers_unavailable(), "marker unavailable")
	_expect(failures, _malformed(), "malformed sidecars")
	return failures


func _load(name: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(BASE + name))


func _agents_page() -> String:
	var parsed: Dictionary = Demographics.parse_demographics(_load("demographics_agents.json"))
	if not bool(parsed.get("ok", false)):
		return "agent page failed: %s" % parsed.get("reason_code", "")
	var model = parsed["value"]
	if model.schema_version != Demographics.DEMOGRAPHICS_SCHEMA:
		return "schema missing"
	if model.resolved_tick != 16 or model.requested_tick != 16:
		return "cursor mismatch"
	if model.population.living != 2 or model.population.admitted != 3:
		return "population totals wrong"
	if model.population.dead != 1 or model.population.max_generation_index != 1:
		return "population turnover wrong"
	if model.agents.size() != 2:
		return "agent rows missing"
	if model.agents[1].generation_index != 1 or model.agents[1].entry_tick != 5:
		return "generation/entry labels missing"
	if model.agents[1].age_ticks != 11:
		return "living age missing"
	if model.stage_rows.size() != 2 or model.stage_rows[0].count != 2:
		return "stage rows missing"
	if model.stage_counts_truncated:
		return "stage truncation should be explicit false"
	return ""


func _unavailable() -> String:
	var parsed: Dictionary = Demographics.parse_demographics(_load("demographics_unavailable.json"))
	if not bool(parsed.get("ok", false)):
		return "unavailable page failed"
	var model = parsed["value"]
	if model.availability != "unavailable" or model.reason_code != "lifecycle_disabled":
		return "unavailable reason missing"
	if model.population != null or not model.agents.is_empty():
		return "unavailable must not fabricate zero population"
	return ""


func _cohorts_page() -> String:
	var parsed: Dictionary = Demographics.parse_demographics(_load("demographics_cohorts.json"))
	if not bool(parsed.get("ok", false)):
		return "cohort page failed"
	var model = parsed["value"]
	if model.section != "cohorts" or model.cohorts.size() != 2:
		return "cohort section missing"
	if not model.agents.is_empty() or not model.generations.is_empty():
		return "only the selected section may carry rows"
	if model.cohorts[1].cohort_id != "cohort-5":
		return "cohort identity missing"
	return ""


func _markers() -> String:
	var parsed: Dictionary = Demographics.parse_markers(_load("markers.json"))
	if not bool(parsed.get("ok", false)):
		return "markers failed"
	var model = parsed["value"]
	if model.markers.size() != 2:
		return "marker rows missing"
	if model.markers[0].label_code != "founders" or model.markers[0].seek_tick != 0:
		return "founder marker wrong"
	if model.markers[1].seek_tick != 6:
		return "post-admission seek boundary wrong"
	if model.markers[1].admitted_count != 1:
		return "marker admitted count wrong"
	return ""


func _markers_unavailable() -> String:
	var parsed: Dictionary = Demographics.parse_markers(_load("markers_unavailable.json"))
	if not bool(parsed.get("ok", false)):
		return "unavailable markers failed"
	var model = parsed["value"]
	if model.availability != "unavailable" or not model.markers.is_empty():
		return "unavailable markers fabricated data"
	return ""


func _malformed() -> String:
	var wrong_schema: Dictionary = Demographics.parse_demographics({
		"schema_version": "observer-demographics-v2",
	})
	if bool(wrong_schema.get("ok", false)):
		return "foreign schema accepted"
	var boolean_count: Dictionary = Demographics.parse_demographics({
		"schema_version": Demographics.DEMOGRAPHICS_SCHEMA,
		"run_id": "run-1",
		"requested_tick": 1,
		"requested_through_sequence": null,
		"resolved_tick": 1,
		"revision": 0,
		"evidence_class": "objective",
		"availability": "available",
		"reason_code": null,
		"section": "agents",
		"selection_state": "all",
		"population": {"living": true, "admitted": 0, "dead": 0, "max_generation_index": 0},
		"stage_rows": [],
		"stage_counts_truncated": false,
		"agents": [],
		"cohorts": [],
		"generations": [],
		"next_after_agent_id": null,
		"next_after_group_key": null,
		"limit": 100,
	})
	if bool(boolean_count.get("ok", false)):
		return "boolean count accepted"
	var negative: Dictionary = Demographics.parse_demographics({
		"schema_version": Demographics.DEMOGRAPHICS_SCHEMA,
		"run_id": "run-1",
		"requested_tick": -1,
	})
	if bool(negative.get("ok", false)):
		return "negative tick accepted"
	var markers: Dictionary = Demographics.parse_markers({"schema_version": Demographics.MARKERS_SCHEMA, "markers": "nope"})
	if bool(markers.get("ok", false)):
		return "scalar marker list accepted"
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
