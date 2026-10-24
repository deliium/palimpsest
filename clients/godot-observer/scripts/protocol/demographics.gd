class_name ObserverDemographics

## Independent parsers for demographic sidecars. These are backend facts only;
## the objective frame reducer never derives generation, cohort, or age.

const DEMOGRAPHICS_SCHEMA := "observer-demographics-v1"
const MARKERS_SCHEMA := "observer-generation-markers-v1"

const _SECTIONS: Array[String] = ["agents", "cohorts", "generations"]
const _SELECTION_STATES: Array[String] = [
	"all",
	"selected",
	"not_present_at_cursor",
	"unavailable",
]


class PopulationModel:
	extends RefCounted
	var living: int = 0
	var admitted: int = 0
	var dead: int = 0
	var max_generation_index: int = 0


class StageRowModel:
	extends RefCounted
	var stage: String = ""
	var life_status: String = ""
	var count: int = 0


class AgentRowModel:
	extends RefCounted
	var agent_id: String = ""
	var entity_id: String = ""
	var entry_tick: int = 0
	var generation_index: int = 0
	var cohort_id: String = ""
	var stage: String = ""
	var dependency_status: String = ""
	var life_status: String = ""
	var age_ticks: Variant = null
	var age_reason_code: Variant = null


class CohortRowModel:
	extends RefCounted
	var generation_index: int = 0
	var entry_tick: int = 0
	var cohort_id: String = ""
	var admitted: int = 0
	var living: int = 0
	var dead: int = 0


class GenerationRowModel:
	extends RefCounted
	var generation_index: int = 0
	var admitted: int = 0
	var living: int = 0
	var dead: int = 0


class DemographicsModel:
	extends RefCounted
	var schema_version: String = ""
	var run_id: String = ""
	var requested_tick: int = 0
	var requested_through_sequence: Variant = null
	var resolved_tick: int = 0
	var revision: int = 0
	var evidence_class: String = ""
	var availability: String = ""
	var reason_code: Variant = null
	var section: String = ""
	var selection_state: String = ""
	var population: Variant = null
	var stage_rows: Array = []
	var stage_counts_truncated: bool = false
	var agents: Array = []
	var cohorts: Array = []
	var generations: Array = []
	var next_after_agent_id: Variant = null
	var next_after_group_key: Variant = null
	var limit: int = 0


class MarkerRowModel:
	extends RefCounted
	var generation_index: int = 0
	var first_entry_tick: int = 0
	var seek_tick: int = 0
	var admitted_count: int = 0
	var label_code: String = ""


class MarkersModel:
	extends RefCounted
	var schema_version: String = ""
	var run_id: String = ""
	var requested_tick: int = 0
	var resolved_tick: int = 0
	var revision: int = 0
	var evidence_class: String = ""
	var availability: String = ""
	var reason_code: Variant = null
	var markers: Array = []
	var next_after_generation_index: Variant = null
	var limit: int = 0


static func parse_demographics(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY:
		return _failure("demographics_invalid")
	if payload.get("schema_version") != DEMOGRAPHICS_SCHEMA:
		return _failure("demographics_invalid")
	if not _is_nonneg_int(payload.get("requested_tick")):
		return _failure("demographics_invalid")
	if not _is_nonneg_int(payload.get("resolved_tick")):
		return _failure("demographics_invalid")
	if not _is_nonneg_int(payload.get("revision")):
		return _failure("demographics_invalid")
	if not _is_string(payload.get("run_id")):
		return _failure("demographics_invalid")
	if payload.get("evidence_class") != "objective":
		return _failure("demographics_invalid")
	var availability: Variant = payload.get("availability")
	if availability not in ["available", "unavailable"]:
		return _failure("demographics_invalid")
	var section: Variant = payload.get("section")
	if section not in _SECTIONS:
		return _failure("demographics_invalid")
	var selection: Variant = payload.get("selection_state")
	if selection not in _SELECTION_STATES:
		return _failure("demographics_invalid")
	if not _is_optional_nonneg_int(payload.get("requested_through_sequence")):
		return _failure("demographics_invalid")
	if not _is_bounded_limit(payload.get("limit")):
		return _failure("demographics_invalid")
	if not _is_optional_string(payload.get("next_after_agent_id")):
		return _failure("demographics_invalid")
	if not _is_optional_string(payload.get("next_after_group_key")):
		return _failure("demographics_invalid")
	var truncated: Variant = payload.get("stage_counts_truncated")
	if typeof(truncated) != TYPE_BOOL:
		return _failure("demographics_invalid")

	var population: Variant = payload.get("population")
	var parsed_population: Variant = null
	if population != null:
		var parsed: Variant = _parse_population(population)
		if parsed == null:
			return _failure("demographics_invalid")
		parsed_population = parsed

	var stage_rows: Array = []
	for row in _array(payload.get("stage_rows")):
		var parsed_row: Variant = _parse_stage_row(row)
		if parsed_row == null:
			return _failure("demographics_invalid")
		stage_rows.append(parsed_row)
	var agents: Array = []
	for row in _array(payload.get("agents")):
		var parsed_agent: Variant = _parse_agent_row(row)
		if parsed_agent == null:
			return _failure("demographics_invalid")
		agents.append(parsed_agent)
	var cohorts: Array = []
	for row in _array(payload.get("cohorts")):
		var parsed_cohort: Variant = _parse_cohort_row(row)
		if parsed_cohort == null:
			return _failure("demographics_invalid")
		cohorts.append(parsed_cohort)
	var generations: Array = []
	for row in _array(payload.get("generations")):
		var parsed_generation: Variant = _parse_generation_row(row)
		if parsed_generation == null:
			return _failure("demographics_invalid")
		generations.append(parsed_generation)

	var model := DemographicsModel.new()
	model.schema_version = DEMOGRAPHICS_SCHEMA
	model.run_id = payload["run_id"]
	model.requested_tick = payload["requested_tick"]
	model.requested_through_sequence = payload.get("requested_through_sequence")
	model.resolved_tick = payload["resolved_tick"]
	model.revision = payload["revision"]
	model.evidence_class = "objective"
	model.availability = availability
	model.reason_code = payload.get("reason_code")
	if not _is_optional_string(model.reason_code):
		return _failure("demographics_invalid")
	model.section = section
	model.selection_state = selection
	model.population = parsed_population
	model.stage_rows = stage_rows
	model.stage_counts_truncated = truncated
	model.agents = agents
	model.cohorts = cohorts
	model.generations = generations
	model.next_after_agent_id = payload.get("next_after_agent_id")
	model.next_after_group_key = payload.get("next_after_group_key")
	model.limit = payload["limit"]
	return {"ok": true, "value": model}


static func parse_markers(payload: Variant) -> Dictionary:
	if typeof(payload) != TYPE_DICTIONARY:
		return _failure("markers_invalid")
	if payload.get("schema_version") != MARKERS_SCHEMA:
		return _failure("markers_invalid")
	if not _is_nonneg_int(payload.get("requested_tick")):
		return _failure("markers_invalid")
	if not _is_nonneg_int(payload.get("resolved_tick")):
		return _failure("markers_invalid")
	if not _is_nonneg_int(payload.get("revision")):
		return _failure("markers_invalid")
	if not _is_string(payload.get("run_id")):
		return _failure("markers_invalid")
	if payload.get("evidence_class") != "objective":
		return _failure("markers_invalid")
	var availability: Variant = payload.get("availability")
	if availability not in ["available", "unavailable"]:
		return _failure("markers_invalid")
	if not _is_optional_nonneg_int(payload.get("next_after_generation_index")):
		return _failure("markers_invalid")
	if not _is_bounded_limit(payload.get("limit")):
		return _failure("markers_invalid")
	var markers: Array = []
	for row in _array(payload.get("markers")):
		if typeof(row) != TYPE_DICTIONARY:
			return _failure("markers_invalid")
		var marker := MarkerRowModel.new()
		if not _is_nonneg_int(row.get("generation_index")):
			return _failure("markers_invalid")
		if not _is_nonneg_int(row.get("first_entry_tick")):
			return _failure("markers_invalid")
		if not _is_nonneg_int(row.get("seek_tick")):
			return _failure("markers_invalid")
		if not _is_nonneg_int(row.get("admitted_count")):
			return _failure("markers_invalid")
		if not _is_string(row.get("label_code")):
			return _failure("markers_invalid")
		if row.get("label_code") not in ["founders", "generation_first_admission"]:
			return _failure("markers_invalid")
		marker.generation_index = row["generation_index"]
		marker.first_entry_tick = row["first_entry_tick"]
		marker.seek_tick = row["seek_tick"]
		marker.admitted_count = row["admitted_count"]
		marker.label_code = row["label_code"]
		markers.append(marker)
	var model := MarkersModel.new()
	model.schema_version = MARKERS_SCHEMA
	model.run_id = payload["run_id"]
	model.requested_tick = payload["requested_tick"]
	model.resolved_tick = payload["resolved_tick"]
	model.revision = payload["revision"]
	model.evidence_class = "objective"
	model.availability = availability
	model.reason_code = payload.get("reason_code")
	if not _is_optional_string(model.reason_code):
		return _failure("markers_invalid")
	model.markers = markers
	model.next_after_generation_index = payload.get("next_after_generation_index")
	model.limit = payload["limit"]
	return {"ok": true, "value": model}


static func _parse_population(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	for key in ["living", "admitted", "dead", "max_generation_index"]:
		if not _is_nonneg_int(value.get(key)):
			return null
	var model := PopulationModel.new()
	model.living = value["living"]
	model.admitted = value["admitted"]
	model.dead = value["dead"]
	model.max_generation_index = value["max_generation_index"]
	return model


static func _parse_stage_row(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if not _is_string(value.get("stage")):
		return null
	if value.get("life_status") not in ["alive", "dead"]:
		return null
	if not _is_nonneg_int(value.get("count")):
		return null
	var model := StageRowModel.new()
	model.stage = value["stage"]
	model.life_status = value["life_status"]
	model.count = value["count"]
	return model


static func _parse_agent_row(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	for key in ["agent_id", "entity_id", "cohort_id", "stage"]:
		if not _is_string(value.get(key)):
			return null
	if value.get("dependency_status") not in ["dependent", "independent"]:
		return null
	if value.get("life_status") not in ["alive", "dead"]:
		return null
	for key in ["entry_tick", "generation_index"]:
		if not _is_nonneg_int(value.get(key)):
			return null
	if not _is_optional_nonneg_int(value.get("age_ticks")):
		return null
	if not _is_optional_string(value.get("age_reason_code")):
		return null
	if value.get("age_reason_code") not in [null, "dead_age_not_projected"]:
		return null
	var model := AgentRowModel.new()
	model.agent_id = value["agent_id"]
	model.entity_id = value["entity_id"]
	model.entry_tick = value["entry_tick"]
	model.generation_index = value["generation_index"]
	model.cohort_id = value["cohort_id"]
	model.stage = value["stage"]
	model.dependency_status = value["dependency_status"]
	model.life_status = value["life_status"]
	model.age_ticks = value.get("age_ticks")
	model.age_reason_code = value.get("age_reason_code")
	return model


static func _parse_cohort_row(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	if not _is_string(value.get("cohort_id")):
		return null
	for key in ["generation_index", "entry_tick", "admitted", "living", "dead"]:
		if not _is_nonneg_int(value.get(key)):
			return null
	var model := CohortRowModel.new()
	model.generation_index = value["generation_index"]
	model.entry_tick = value["entry_tick"]
	model.cohort_id = value["cohort_id"]
	model.admitted = value["admitted"]
	model.living = value["living"]
	model.dead = value["dead"]
	return model


static func _parse_generation_row(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	for key in ["generation_index", "admitted", "living", "dead"]:
		if not _is_nonneg_int(value.get(key)):
			return null
	var model := GenerationRowModel.new()
	model.generation_index = value["generation_index"]
	model.admitted = value["admitted"]
	model.living = value["living"]
	model.dead = value["dead"]
	return model


static func _failure(reason_code: String) -> Dictionary:
	return {"ok": false, "reason_code": reason_code}


static func _array(value: Variant) -> Array:
	return value if typeof(value) == TYPE_ARRAY else []


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


static func _is_bounded_limit(value: Variant) -> bool:
	return _is_nonneg_int(value) and int(value) >= 1 and int(value) <= 200
