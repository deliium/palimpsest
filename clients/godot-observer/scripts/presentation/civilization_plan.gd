extends RefCounted
class_name CivilizationRenderPlan

const Evidence := preload("res://scripts/presentation/evidence_class.gd")
const Scale := preload("res://scripts/presentation/scale.gd")

const GLYPH_CAP := 800
const LINK_CAP := 400
const LABEL_CAP := 800
const LAYER_ORDER := [
	"regions", "routes", "locations", "settlements", "projects",
	"repositories", "records", "migration", "trade", "culture",
	"technology", "social_groups", "institutions",
]
const ACT_ORDER := ["benefit", "draw", "maintenance", "opposition"]
const ACT_LABELS := {
	"benefit": "benefit",
	"draw": "draw",
	"maintenance": "maintenance",
	"opposition": "opposition",
}
const KIND_PRIORITY := {
	"locations": 0,
	"settlements": 1,
	"projects": 2,
	"public_act": 3,
	"repositories": 4,
	"records": 5,
	"migration": 6,
	"trade": 7,
	"culture": 8,
	"technology": 9,
	"social_groups": 10,
	"institutions": 11,
}


static func build_semantic(
	world: Variant,
	layer_state: Dictionary,
	display_cursor: Dictionary,
	centers: Dictionary = {},
) -> Dictionary:
	var cursor := _normalize_cursor(display_cursor)
	if cursor.is_empty():
		return _failure("cursor_required")
	var layers := {}
	var rows: Array = []
	var unresolved: Array = []
	var warnings := {}
	var repository_locations := _repository_locations(layer_state)
	var location_counts := _location_counts(layer_state)
	for layer_id in _ordered_layers(layer_state):
		var state: Variant = layer_state.get(layer_id, null)
		if typeof(state) != TYPE_DICTIONARY:
			continue
		var status := str(state.get("status", "off"))
		var evidence := _evidence_label(layer_id, state)
		layers[layer_id] = {
			"status": status,
			"evidence_class": evidence,
			"owner_id": state.get("owner_id", null),
			"policy_version": str(state.get("policy_version", "")),
			"window": state.get("window", null),
			"coverage": state.get("coverage", null),
			"truncated": bool(state.get("truncated", false)),
		}
		if status not in ["available", "partial", "empty"]:
			continue
		var state_cursor: Variant = state.get("cursor", null)
		if typeof(state_cursor) == TYPE_DICTIONARY and not state_cursor.is_empty():
			if not _cursor_matches(state_cursor, cursor):
				return _failure("cursor_mismatch")
		for raw in _array(state.get("rows", [])):
			for built in _build_rows(
				raw,
				layer_id,
				evidence,
				world,
				centers,
				repository_locations,
				location_counts,
				state,
				layer_state,
			):
				if str(built.get("placement", "")) == "unplaced":
					var reason := str(built.get("unplaced_reason", "anchor_unavailable"))
					if reason == "anchor_unavailable":
						unresolved.append(str(built.get("row_id", "")))
					warnings[reason] = true
				rows.append(built)
	rows.sort_custom(func(left: Dictionary, right: Dictionary) -> bool:
		var left_kind := str(left.get("kind", ""))
		var right_kind := str(right.get("kind", ""))
		var left_priority := int(KIND_PRIORITY.get(left_kind, 99))
		var right_priority := int(KIND_PRIORITY.get(right_kind, 99))
		if left_priority != right_priority:
			return left_priority < right_priority
		return str(left.get("row_id", "")) < str(right.get("row_id", ""))
	)
	var warning_codes: Array = warnings.keys()
	warning_codes.sort()
	return {
		"ok": true,
		"reason_code": "",
		"cursor": cursor,
		"layers": layers,
		"rows": rows,
		"unresolved_anchor_count": unresolved.size(),
		"unresolved_row_ids": unresolved,
		"warning_codes": warning_codes,
		"counts": _row_counts(rows),
	}


static func draw_plan(semantic_plan: Dictionary, lod: String = "full") -> Dictionary:
	if not bool(semantic_plan.get("ok", false)):
		return {
			"ok": false,
			"reason_code": str(semantic_plan.get("reason_code", "invalid_plan")),
			"glyphs": [],
			"links": [],
			"labels": [],
			"suppressed": {},
			"display_truncated": false,
			"visible_counts": {},
		}
	var glyphs: Array = []
	var links: Array = []
	var labels: Array = []
	var suppressed := {"glyphs": 0, "links": 0, "labels": 0}
	var ordered: Array = _array(semantic_plan.get("rows", [])).duplicate()
	ordered.sort_custom(func(left: Dictionary, right: Dictionary) -> bool:
		var left_priority := int(KIND_PRIORITY.get(str(left.get("kind", "")), 99))
		var right_priority := int(KIND_PRIORITY.get(str(right.get("kind", "")), 99))
		if left_priority != right_priority:
			return left_priority < right_priority
		return str(left.get("row_id", "")) < str(right.get("row_id", ""))
	)
	for row in ordered:
		var kind := str(row.get("kind", ""))
		if kind == "regions":
			if links.size() < LINK_CAP:
				links.append(_link_entry(row, "region_envelope", str(row.get("label", ""))))
			else:
				suppressed["links"] += 1
			continue
		if kind == "routes":
			if links.size() < LINK_CAP:
				links.append(_link_entry(row, "configured_route", str(row.get("label", ""))))
			else:
				suppressed["links"] += 1
			continue
		if kind in ["migration", "technology"]:
			var points: Array = row.get("points", [])
			if points.size() == 2:
				if links.size() < LINK_CAP:
					links.append(_flow_link(row, kind))
				else:
					suppressed["links"] += 1
		if kind == "records" and lod != "full":
			continue
		if kind == "public_act" and lod == "aggregate":
			continue
		if glyphs.size() >= GLYPH_CAP:
			suppressed["glyphs"] += 1
			suppressed["labels"] += 1
			continue
		var glyph := _glyph_entry(row, lod)
		if glyph.is_empty():
			continue
		glyphs.append(glyph)
		var label := _label_entry(row, lod)
		if not label.is_empty():
			if labels.size() < LABEL_CAP:
				labels.append(label)
			else:
				suppressed["labels"] += 1
	var visible := {
		"glyphs": glyphs.size(),
		"links": links.size(),
		"labels": labels.size(),
	}
	return {
		"ok": true,
		"reason_code": "",
		"cursor": semantic_plan.get("cursor", {}),
		"lod": lod,
		"glyphs": glyphs,
		"links": links,
		"labels": labels,
		"suppressed": suppressed,
		"display_truncated": (
			int(suppressed["glyphs"]) > 0
			or int(suppressed["links"]) > 0
			or int(suppressed["labels"]) > 0
		),
		"visible_counts": visible,
	}


static func _ordered_layers(layer_state: Dictionary) -> Array:
	var present: Array = []
	for layer_id in layer_state.keys():
		if layer_id in LAYER_ORDER:
			present.append(str(layer_id))
	present.sort_custom(func(left: String, right: String) -> bool:
		return LAYER_ORDER.find(left) < LAYER_ORDER.find(right)
	)
	return present


static func _build_rows(
	raw: Variant,
	layer_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
	repository_locations: Dictionary,
	location_counts: Dictionary,
	state: Dictionary,
	all_layers: Dictionary,
) -> Array:
	if raw == null:
		return []
	var kind := str(_value(raw, "kind", layer_id))
	var raw_row_id: Variant = _value(raw, "row_id", null)
	var row_id := "" if raw_row_id == null else str(raw_row_id)
	if row_id.is_empty():
		row_id = _raw_row_id(raw, kind, layer_id)
	match kind:
		"regions":
			return [_region_row(raw, row_id, evidence, world, centers)]
		"routes":
			return [_route_row(raw, row_id, evidence, world, centers)]
		"locations":
			return [_location_row(raw, row_id, evidence, world, centers)]
		"settlements":
			return [_settlement_row(raw, row_id, evidence, world, centers, state, location_counts)]
		"projects":
			return _project_rows(raw, row_id, evidence, world, centers)
		"repositories":
			return [_repository_row(raw, row_id, evidence, world, centers)]
		"records":
			return [_record_row(raw, row_id, evidence, world, centers, repository_locations)]
		"migration":
			return [_migration_row(raw, row_id, evidence, world, centers)]
		"trade":
			return [_trade_row(raw, row_id, evidence, world, centers)]
		"culture":
			return [_culture_row(raw, row_id, evidence, world, centers)]
		"technology":
			return _technology_rows(raw, row_id, evidence, world, centers, state)
		"social_groups":
			return _group_rows(raw, row_id, evidence, world, centers, state)
		"institutions":
			return _institution_rows(raw, row_id, evidence, world, centers, state, all_layers, repository_locations)
		_:
			return []


static func _region_row(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
) -> Dictionary:
	var region_id := str(_value(raw, "region_id", ""))
	var ids: Array = _string_array(_value(raw, "location_ids", []))
	ids.sort()
	var points: Array = []
	for location_id in ids:
		var point: Variant = _location_point(str(location_id), world, centers)
		if point != null:
			points.append(point)
	var region_label := _optional_text(_value(raw, "region_label", null))
	var label := region_label if not region_label.is_empty() else region_id
	var placed := not points.is_empty()
	return {
		"row_id": row_id,
		"kind": "regions",
		"identity": region_id,
		"layer": "regions",
		"evidence_class": evidence,
		"label": label,
		"region_label": region_label,
		"location_ids": ids,
		"location_count": int(_value(raw, "location_count", ids.size())),
		"anchor_ids": ids,
		"points": points,
		"bounds": _bounds(points),
		"placement": "placed" if placed else "unplaced",
		"unplaced_reason": "anchor_unavailable" if not placed else "",
		"click": _click(row_id, "regions", evidence, raw, {"region_id": region_id, "location_count": int(_value(raw, "location_count", ids.size()))}),
	}


static func _route_row(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
) -> Dictionary:
	var endpoint_a := str(_value(raw, "endpoint_a", ""))
	var endpoint_b := str(_value(raw, "endpoint_b", ""))
	var point_a: Variant = _location_point(endpoint_a, world, centers)
	var point_b: Variant = _location_point(endpoint_b, world, centers)
	var placed := point_a != null and point_b != null and endpoint_a != "" and endpoint_b != ""
	return {
		"row_id": row_id,
		"kind": "routes",
		"identity": str(_value(raw, "route_id", row_id)),
		"layer": "routes",
		"evidence_class": evidence,
		"label": "%s %st" % [str(_value(raw, "route_id", "")), str(_value(raw, "duration_ticks", 0))],
		"anchor_ids": [endpoint_a, endpoint_b],
		"points": [point_a, point_b] if placed else [],
		"placement": "placed" if placed else "unplaced",
		"unplaced_reason": "anchor_unavailable" if not placed else "",
		"duration_ticks": int(_value(raw, "duration_ticks", 0)),
		"fatigue_cost": float(_value(raw, "fatigue_cost", 0.0)),
		"region_a": _value(raw, "region_a", null),
		"region_b": _value(raw, "region_b", null),
		"click": _click(row_id, "routes", evidence, raw, {
			"route_id": str(_value(raw, "route_id", "")),
			"endpoint_a": endpoint_a,
			"endpoint_b": endpoint_b,
			"duration_ticks": int(_value(raw, "duration_ticks", 0)),
		}),
	}


static func _location_row(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
) -> Dictionary:
	var location_id := str(_value(raw, "location_id", ""))
	var point: Variant = _location_point(location_id, world, centers)
	var living := int(_value(raw, "living_body_count", 0))
	var dead := int(_value(raw, "dead_body_count", 0))
	var registered := int(_value(raw, "registered_agent_count", 0))
	var lifecycle_living: Variant = _value(raw, "lifecycle_living_count", null)
	var lifecycle_dead: Variant = _value(raw, "lifecycle_dead_count", null)
	var present_unregistered := maxi(0, living - registered)
	var label := "%s living %s" % [location_id, living]
	if dead > 0:
		label += " dead %s" % dead
	if present_unregistered > 0:
		label += " present-unregistered %s" % present_unregistered
	if lifecycle_living == null or lifecycle_dead == null:
		label += " lifecycle unavailable"
	else:
		label += " lifecycle %s/%s" % [str(lifecycle_living), str(lifecycle_dead)]
	return {
		"row_id": row_id,
		"kind": "locations",
		"identity": location_id,
		"layer": "locations",
		"evidence_class": evidence,
		"label": label,
		"location_id": location_id,
		"point": point,
		"placement": "placed" if point != null else "unplaced",
		"unplaced_reason": "anchor_unavailable" if point == null else "",
		"living_body_count": living,
		"dead_body_count": dead,
		"registered_agent_count": registered,
		"present_unregistered_count": present_unregistered,
		"lifecycle_living_count": lifecycle_living,
		"lifecycle_dead_count": lifecycle_dead,
		"lifecycle_known": lifecycle_living != null and lifecycle_dead != null,
		"size_band": _size_band(living),
		"structure_count": int(_value(raw, "structure_count", 0)),
		"project_count": int(_value(raw, "project_count", 0)),
		"repository_count": int(_value(raw, "repository_count", 0)),
		"active_journey_count": int(_value(raw, "active_journey_count", 0)),
		"click": _click(row_id, "locations", evidence, raw, {
			"location_id": location_id,
			"living_body_count": living,
			"dead_body_count": dead,
			"registered_agent_count": registered,
			"present_unregistered_count": present_unregistered,
			"lifecycle_living_count": lifecycle_living,
			"lifecycle_dead_count": lifecycle_dead,
			"structure_count": int(_value(raw, "structure_count", 0)),
			"project_count": int(_value(raw, "project_count", 0)),
			"repository_count": int(_value(raw, "repository_count", 0)),
		}),
	}


static func _settlement_row(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
	state: Dictionary,
	location_counts: Dictionary,
) -> Dictionary:
	var location_id := str(_value(raw, "location_id", ""))
	var point: Variant = _location_point(location_id, world, centers)
	var status := str(_value(raw, "status", ""))
	var counts: Dictionary = location_counts.get(location_id, {})
	var living: Variant = counts.get("living_body_count", null)
	var dead: Variant = counts.get("dead_body_count", null)
	var population_text := "pop unknown" if living == null else "pop %s" % str(living)
	var dead_text := "" if dead == null or int(dead) == 0 else " dead %s" % str(dead)
	var coverage: Variant = state.get("coverage", null)
	var coverage_state := "" if coverage == null else str(_value(coverage, "state", ""))
	var style := "solid"
	if status in ["censored", "insufficient_history"]:
		style = "uncertain"
	elif status == "inactive":
		style = "hollow"
	if coverage_state != "" and coverage_state != "complete":
		style = "uncertain"
	return {
		"row_id": row_id,
		"kind": "settlements",
		"identity": str(_value(raw, "candidate_id", row_id)),
		"layer": "settlements",
		"evidence_class": evidence,
		"label": "%s %s %s%s infra %s" % [
			location_id,
			status,
			population_text,
			dead_text,
			str(_value(raw, "infrastructure_count", 0)),
		],
		"candidate_id": str(_value(raw, "candidate_id", "")),
		"location_id": location_id,
		"point": point,
		"placement": "placed" if point != null else "unplaced",
		"unplaced_reason": "anchor_unavailable" if point == null else "",
		"status": status,
		"style": style,
		"eligible_occupancy": int(_value(raw, "eligible_occupancy", 0)),
		"infrastructure_count": int(_value(raw, "infrastructure_count", 0)),
		"observed_streak": int(_value(raw, "observed_streak", 0)),
		"living_body_count": living,
		"dead_body_count": dead,
		"first_supported_boundary": _value(raw, "first_supported_boundary", null),
		"last_supported_boundary": _value(raw, "last_supported_boundary", null),
		"episode_start_boundary": _value(raw, "episode_start_boundary", null),
		"click": _click(row_id, "settlements", evidence, raw, {
			"candidate_id": str(_value(raw, "candidate_id", "")),
			"location_id": location_id,
			"status": status,
			"eligible_occupancy": int(_value(raw, "eligible_occupancy", 0)),
			"infrastructure_count": int(_value(raw, "infrastructure_count", 0)),
			"observed_streak": int(_value(raw, "observed_streak", 0)),
			"living_body_count": living,
			"dead_body_count": dead,
			"history_window": _window_text(_history_window(row_id, state, raw)),
			"first_supported_boundary": _value(raw, "first_supported_boundary", null),
			"last_supported_boundary": _value(raw, "last_supported_boundary", null),
			"coverage_state": coverage_state,
		}),
	}


static func _project_rows(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
) -> Array:
	var rows: Array = []
	var location_id := str(_value(raw, "location_id", ""))
	var point: Variant = _location_point(location_id, world, centers)
	var linked_id := _optional_text(_value(raw, "linked_structure_id", null))
	var linked_point: Variant = _structure_point(linked_id, world, centers)
	var labor_required := int(_value(raw, "labor_required", 0))
	var material_required := int(_value(raw, "material_required", 0))
	var labor_progress := int(_value(raw, "labor_progress", 0))
	var material_progress := int(_value(raw, "material_progress", 0))
	rows.append({
		"row_id": row_id,
		"kind": "projects",
		"identity": str(_value(raw, "project_id", row_id)),
		"layer": "projects",
		"evidence_class": evidence,
		"label": "%s %s %s" % [
			str(_value(raw, "kind", "project")),
			str(_value(raw, "status", "")),
			_progress_label(labor_progress, labor_required),
		],
		"project_id": str(_value(raw, "project_id", "")),
		"location_id": location_id,
		"point": point,
		"placement": "placed" if point != null else "unplaced",
		"unplaced_reason": "anchor_unavailable" if point == null else "",
		"status": str(_value(raw, "status", "")),
		"project_kind": str(_value(raw, "kind", "")),
		"labor_progress": labor_progress,
		"labor_required": labor_required,
		"labor_ratio": _ratio(labor_progress, labor_required),
		"material_progress": material_progress,
		"material_required": material_required,
		"material_ratio": _ratio(material_progress, material_required),
		"material_kind": _value(raw, "material_kind", null),
		"accepted_contribution_count": int(_value(raw, "accepted_contribution_count", 0)),
		"shortage_count": int(_value(raw, "shortage_count", 0)),
		"linked_structure_id": linked_id,
		"linked_structure_kind": _value(raw, "linked_structure_kind", null),
		"linked_structure_point": linked_point,
		"style": str(_value(raw, "status", "open")),
		"click": _click(row_id, "projects", evidence, raw, {
			"project_id": str(_value(raw, "project_id", "")),
			"location_id": location_id,
			"project_kind": str(_value(raw, "kind", "")),
			"status": str(_value(raw, "status", "")),
			"labor_progress": labor_progress,
			"labor_required": labor_required,
			"material_progress": material_progress,
			"material_required": material_required,
			"material_kind": _value(raw, "material_kind", null),
			"accepted_contribution_count": int(_value(raw, "accepted_contribution_count", 0)),
			"shortage_count": int(_value(raw, "shortage_count", 0)),
			"linked_structure_id": linked_id,
		}),
	})
	var acts: Variant = _value(raw, "public_acts", null)
	if acts != null:
		for index in ACT_ORDER.size():
			var act := str(ACT_ORDER[index])
			var count := int(_value(acts, act + "_count", 0))
			if count <= 0:
				continue
			rows.append({
				"row_id": "%s:%s" % [row_id, act],
				"kind": "public_act",
				"identity": "%s:%s" % [str(_value(raw, "project_id", row_id)), act],
				"layer": "projects",
				"evidence_class": evidence,
				"label": "%s %s" % [ACT_LABELS.get(act, act), count],
				"act": act,
				"act_index": index,
				"count": count,
				"project_id": str(_value(raw, "project_id", "")),
				"location_id": location_id,
				"point": point,
				"placement": "placed" if point != null else "unplaced",
				"unplaced_reason": "anchor_unavailable" if point == null else "",
				"click": _click("%s:%s" % [row_id, act], "projects", evidence, raw, {
					"project_id": str(_value(raw, "project_id", "")),
					"location_id": location_id,
					"act": act,
					"count": count,
				}),
			})
	return rows


static func _repository_row(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
) -> Dictionary:
	var location_id := str(_value(raw, "location_id", ""))
	var point: Variant = _location_point(location_id, world, centers)
	var status := str(_value(raw, "status", ""))
	return {
		"row_id": row_id,
		"kind": "repositories",
		"identity": str(_value(raw, "repository_id", row_id)),
		"layer": "repositories",
		"evidence_class": evidence,
		"label": "%s %s" % [str(_value(raw, "repository_id", "")), status],
		"repository_id": str(_value(raw, "repository_id", "")),
		"location_id": location_id,
		"point": point,
		"placement": "placed" if point != null else "unplaced",
		"unplaced_reason": "anchor_unavailable" if point == null else "",
		"status": status,
		"access_mode": _value(raw, "access_mode", null),
		"member_count": int(_value(raw, "member_count", 0)),
		"linked_structure_id": _optional_text(_value(raw, "linked_structure_id", null)),
		"linked_structure_point": _structure_point(_optional_text(_value(raw, "linked_structure_id", null)), world, centers),
		"neglect_streak": int(_value(raw, "neglect_streak", 0)),
		"established_tick": int(_value(raw, "established_tick", 0)),
		"last_maintained_tick": int(_value(raw, "last_maintained_tick", 0)),
		"style": status,
		"click": _click(row_id, "repositories", evidence, raw, {
			"repository_id": str(_value(raw, "repository_id", "")),
			"location_id": location_id,
			"status": status,
			"access_mode": _value(raw, "access_mode", null),
			"member_count": int(_value(raw, "member_count", 0)),
			"neglect_streak": int(_value(raw, "neglect_streak", 0)),
		}),
	}


static func _record_row(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
	repository_locations: Dictionary,
) -> Dictionary:
	var location_id := _optional_text(_value(raw, "location_id", null))
	var placement_basis := "location"
	var point: Variant = _location_point(location_id, world, centers)
	if point == null:
		var custodian := _optional_text(_value(raw, "custodian_repository_id", null))
		if not custodian.is_empty() and repository_locations.has(custodian):
			location_id = str(repository_locations[custodian])
			point = _location_point(location_id, world, centers)
			placement_basis = "custodian"
	if point == null:
		var holder := _optional_text(_value(raw, "holder_id", null))
		if not holder.is_empty():
			var holder_location := _agent_location(holder, world)
			if not holder_location.is_empty():
				location_id = holder_location
				point = _location_point(location_id, world, centers)
				placement_basis = "holder"
	var kind := str(_value(raw, "representation_id", "record"))
	var integrity := str(_value(raw, "integrity", ""))
	var label := kind if integrity.is_empty() else "%s %s" % [kind, integrity]
	return {
		"row_id": row_id,
		"kind": "records",
		"identity": str(_value(raw, "record_id", row_id)),
		"layer": "records",
		"evidence_class": evidence,
		"label": label,
		"record_id": str(_value(raw, "record_id", "")),
		"record_kind": kind,
		"genre": _value(raw, "genre", null),
		"integrity": _value(raw, "integrity", null),
		"location_id": location_id,
		"placement_basis": placement_basis,
		"point": point,
		"placement": "placed" if point != null else "unplaced",
		"unplaced_reason": "anchor_unavailable" if point == null else "",
		"custodian_repository_id": _value(raw, "custodian_repository_id", null),
		"holder_id": _value(raw, "holder_id", null),
		"copy_generation": int(_value(raw, "copy_generation", 0)),
		"annotation_revisions": int(_value(raw, "annotation_revisions", 0)),
		"lost_mark_count": int(_value(raw, "lost_mark_count", 0)),
		"style": integrity if not integrity.is_empty() else "intact",
		"click": _click(row_id, "records", evidence, raw, {
			"record_id": str(_value(raw, "record_id", "")),
			"record_kind": kind,
			"genre": _value(raw, "genre", null),
			"integrity": _value(raw, "integrity", null),
			"location_id": location_id,
			"placement_basis": placement_basis,
			"copy_generation": int(_value(raw, "copy_generation", 0)),
			"lost_mark_count": int(_value(raw, "lost_mark_count", 0)),
		}),
	}


static func _link_entry(row: Dictionary, kind: String, label: String) -> Dictionary:
	var entry := {
		"kind": kind,
		"row_id": str(row.get("row_id", "")),
		"label": label,
		"evidence_class": str(row.get("evidence_class", "")),
		"click": row.get("click", {}).duplicate(true),
	}
	if kind == "region_envelope":
		entry["bounds"] = row.get("bounds", Rect2())
		entry["region_label"] = str(row.get("region_label", ""))
	else:
		entry["points"] = row.get("points", [])
		entry["style"] = str(row.get("link_style", "dashed"))
	return entry


static func _flow_link(row: Dictionary, kind: String) -> Dictionary:
	var link_kind := "knowledge_diffusion"
	if kind == "migration":
		var style := str(row.get("link_style", "intention_dashed"))
		if style == "outcome":
			link_kind = "journey_outcome"
		elif style == "ended":
			link_kind = "journey_ended"
		else:
			link_kind = "journey_intention"
	return _link_entry(row, link_kind, str(row.get("label", "")))


static func _glyph_entry(row: Dictionary, lod: String) -> Dictionary:
	var kind := str(row.get("kind", ""))
	var point: Variant = row.get("point", null)
	if point == null:
		return {}
	var glyph := {
		"kind": kind,
		"row_id": str(row.get("row_id", "")),
		"point": point,
		"evidence_class": str(row.get("evidence_class", "")),
		"style": str(row.get("style", "")),
		"click": row.get("click", {}).duplicate(true),
	}
	match kind:
		"locations":
			glyph["size_band"] = str(row.get("size_band", "small"))
			glyph["count"] = int(row.get("living_body_count", 0))
		"settlements":
			glyph["status"] = str(row.get("status", ""))
		"projects":
			glyph["labor_ratio"] = _clamp_ratio(row.get("labor_ratio", null))
			glyph["material_ratio"] = _clamp_ratio(row.get("material_ratio", null))
			glyph["progress_known"] = row.get("labor_ratio", null) != null
			glyph["linked_structure_point"] = row.get("linked_structure_point", null)
		"public_act":
			glyph["act"] = str(row.get("act", ""))
			glyph["act_index"] = int(row.get("act_index", 0))
			glyph["count"] = int(row.get("count", 0))
		"repositories":
			glyph["status"] = str(row.get("status", ""))
		"records":
			glyph["integrity"] = row.get("integrity", null)
		"migration":
			glyph["phase"] = str(row.get("phase", ""))
			glyph["link_style"] = str(row.get("link_style", ""))
		"trade":
			glyph["completed_exchange_count"] = int(row.get("completed_exchange_count", 0))
			glyph["forward_items"] = row.get("forward_items", [])
			glyph["reverse_items"] = row.get("reverse_items", [])
		"culture":
			glyph["proportion_text"] = str(row.get("proportion_text", "unknown"))
			glyph["carrier_count"] = int(row.get("carrier_count", 0))
			glyph["eligible_owner_count"] = row.get("eligible_owner_count", null)
			glyph["unavailable_owner_count"] = int(row.get("unavailable_owner_count", 0))
		"technology":
			glyph["knowledge_id"] = str(row.get("knowledge_id", ""))
			glyph["status"] = str(row.get("status", ""))
			glyph["attribution"] = str(row.get("attribution", ""))
			glyph["modality"] = str(row.get("modality", ""))
			glyph["has_diffusion_edge"] = bool(row.get("has_diffusion_edge", false))
		"social_groups":
			glyph["member_points"] = row.get("member_points", {})
			glyph["style"] = str(row.get("style", ""))
			glyph["color_key"] = str(row.get("color_key", ""))
			glyph["missing_lanes"] = row.get("missing_lanes", [])
			glyph["unresolved_member_count"] = row.get("unresolved_member_ids", []).size()
		"institutions":
			glyph["site_points"] = row.get("site_points", [])
			glyph["sites"] = row.get("sites", [])
			glyph["status"] = str(row.get("status", ""))
			glyph["institution_kind"] = str(row.get("institution_kind", ""))
			glyph["historical_evidence"] = bool(row.get("historical_evidence", false))
	if lod == "aggregate" and kind in ["public_act", "projects"]:
		glyph["label_hidden"] = true
	return glyph


static func _label_entry(row: Dictionary, lod: String) -> Dictionary:
	var kind := str(row.get("kind", ""))
	if lod == "aggregate" and kind not in ["locations", "settlements"]:
		return {}
	var point: Variant = row.get("point", null)
	if point == null:
		return {}
	var text := str(row.get("label", ""))
	if lod != "full" and kind in ["records", "projects", "public_act"]:
		text = _compact_label(kind, row)
	return {
		"row_id": str(row.get("row_id", "")),
		"kind": kind,
		"point": point + Vector2(10.0, -10.0),
		"text": text,
		"evidence_class": str(row.get("evidence_class", "")),
		"click": row.get("click", {}).duplicate(true),
	}


static func _compact_label(kind: String, row: Dictionary) -> String:
	match kind:
		"records":
			return str(row.get("record_kind", "record"))
		"projects":
			return str(row.get("project_kind", "project"))
		"public_act":
			return "%s %s" % [str(row.get("act", "")), str(row.get("count", 0))]
		_:
			return str(row.get("label", ""))


static func _click(
	row_id: String,
	layer_id: String,
	evidence: String,
	raw: Variant,
	summary: Dictionary,
) -> Dictionary:
	var source_refs: Array = []
	var context: Variant = _value(raw, "context", null)
	var raw_refs: Variant = _value(raw, "source_refs", null)
	var raw_anchors: Variant = _value(raw, "anchors", null)
	if context != null:
		raw_refs = _value(context, "source_refs", null)
		raw_anchors = _value(context, "anchors", null)
	for ref in _array(raw_refs):
		source_refs.append({
			"source_kind": str(_value(ref, "source_kind", "")),
			"source_id": str(_value(ref, "source_id", "")),
			"tick": int(_value(ref, "tick", 0)),
			"owner_id": _value(ref, "owner_id", null),
		})
	var anchors: Array = []
	for anchor in _array(raw_anchors):
		anchors.append({
			"kind": str(_value(anchor, "kind", "")),
			"location_id": _value(anchor, "location_id", null),
			"entity_id": _value(anchor, "entity_id", null),
			"evidence_tick": _value(anchor, "evidence_tick", null),
		})
	var lineage_refs: Array = []
	for ref in source_refs:
		if str(ref.get("source_kind", "")) != "lineage":
			continue
		lineage_refs.append({
			"source_id": str(ref.get("source_id", "")),
			"tick": int(ref.get("tick", 0)),
			"owner_id": ref.get("owner_id", null),
		})
	return {
		"row_id": row_id,
		"layer": layer_id,
		"evidence_class": evidence,
		"source_refs": source_refs,
		"anchors": anchors,
		"lineage_refs": lineage_refs,
		"summary": summary.duplicate(true),
	}


static func _location_counts(layer_state: Dictionary) -> Dictionary:
	var result := {}
	var state: Variant = layer_state.get("locations", null)
	if typeof(state) != TYPE_DICTIONARY:
		return result
	if str(state.get("status", "")) not in ["available", "partial", "empty"]:
		return result
	for row in _array(state.get("rows", [])):
		var location_id := str(_value(row, "location_id", ""))
		if location_id.is_empty():
			continue
		result[location_id] = {
			"living_body_count": int(_value(row, "living_body_count", 0)),
			"dead_body_count": int(_value(row, "dead_body_count", 0)),
			"registered_agent_count": int(_value(row, "registered_agent_count", 0)),
		}
	return result


static func _window_text(window: Variant) -> String:
	if window == null:
		return ""
	return "%s..%s" % [
		str(_value(window, "start_tick", "?")),
		str(_value(window, "end_tick", "?")),
	]


static func _history_window(row_id: String, state: Dictionary, raw: Variant) -> Variant:
	var window: Variant = state.get("window", null)
	if window != null:
		return window
	var history: Variant = _value(raw, "history", null)
	if history != null:
		return _value(history, "window", null)
	return null


static func _group_rows(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
	state: Dictionary,
) -> Array:
	var basis := str(_value(raw, "basis", ""))
	var scope_owner := _normalize_owner(state.get("owner_id", null))
	var row_owner := _row_owner(raw)
	if evidence == "SUBJECTIVE":
		if basis != "owner_belief":
			return []
		if scope_owner.is_empty() or row_owner != scope_owner:
			return []
	elif basis != "interaction_residence":
		return []
	var member_ids := _string_array(_value(raw, "member_ids", []))
	member_ids.sort()
	var member_points := {}
	var unresolved: Array = []
	for member_id in member_ids:
		var member_point: Variant = _agent_point(str(member_id), world, centers)
		if member_point == null:
			unresolved.append(str(member_id))
		else:
			member_points[str(member_id)] = member_point
	var points: Array = member_points.values()
	points.sort_custom(func(left: Vector2, right: Vector2) -> bool:
		if left.x != right.x:
			return left.x < right.x
		return left.y < right.y
	)
	var missing_lanes := _string_array(_value(raw, "missing_lanes", []))
	missing_lanes.sort()
	var label := "%s %s members %s" % [
		str(_value(raw, "group_id", "?")),
		basis,
		str(_value(raw, "member_count", member_ids.size())),
	]
	if not missing_lanes.is_empty():
		label += " missing %s" % ",".join(missing_lanes)
	if not unresolved.is_empty():
		label += " unbound %s" % unresolved.size()
	var style := "owner_membership" if evidence == "SUBJECTIVE" else "inferred_community"
	var history: Variant = _value(raw, "history", null)
	var coverage: Variant = state.get("coverage", null)
	var coverage_state := "complete" if coverage == null else str(_value(coverage, "state", ""))
	return [{
		"row_id": row_id,
		"kind": "social_groups",
		"identity": row_id,
		"layer": "social_groups",
		"evidence_class": evidence,
		"owner_id": scope_owner if evidence == "SUBJECTIVE" else null,
		"label": label,
		"group_id": str(_value(raw, "group_id", "")),
		"basis": basis,
		"member_ids": member_ids,
		"member_count": int(_value(raw, "member_count", member_ids.size())),
		"member_points": member_points,
		"unresolved_member_ids": unresolved,
		"missing_lanes": missing_lanes,
		"missing_lanes_text": ",".join(missing_lanes),
		"points": points,
		"point": points[0] if not points.is_empty() else null,
		"style": style,
		"color_key": "%s|%s|%s" % [str(_value(raw, "group_id", "")), basis, scope_owner],
		"placement": "placed" if not points.is_empty() else "unplaced",
		"unplaced_reason": "unresolved_member" if points.is_empty() else "",
		"click": _click(row_id, "social_groups", evidence, raw, {
			"group_id": str(_value(raw, "group_id", "")),
			"basis": basis,
			"owner_id": scope_owner if evidence == "SUBJECTIVE" else null,
			"member_count": int(_value(raw, "member_count", member_ids.size())),
			"missing_lanes_text": ",".join(missing_lanes),
			"unresolved_member_count": unresolved.size(),
			"binding": "owner_belief" if evidence == "SUBJECTIVE" else "inferred_membership",
			"coverage_state": coverage_state,
			"boundary_tick": _value(history, "boundary_tick", null),
			"policy_version": str(_value(history, "policy_version", "")),
		}),
	}]


static func _institution_rows(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
	state: Dictionary,
	all_layers: Dictionary,
	repository_locations: Dictionary,
) -> Array:
	var kind := str(_value(raw, "basis", ""))
	var native_owner := _normalize_owner(_value(raw, "native_owner_id", null))
	var scope_owner := _normalize_owner(state.get("owner_id", null))
	if evidence == "SUBJECTIVE":
		if kind not in ["concept", "office"]:
			return []
		if scope_owner.is_empty() or native_owner != scope_owner:
			return []
	else:
		if kind != "episode":
			return []
	var sites: Array = _institution_sites(raw, world, centers, all_layers, repository_locations)
	var site_points: Array = []
	var historical := false
	for site in sites:
		site_points.append(site["point"])
		if bool(site.get("historical_evidence", false)):
			historical = true
	var coverage: Variant = state.get("coverage", null)
	var coverage_state := "complete" if coverage == null else str(_value(coverage, "state", ""))
	var status := str(_value(raw, "status", ""))
	var style := "solid"
	if coverage_state != "complete":
		style = "gap"
	elif status in ["collapsed", "lost"]:
		style = "collapsed"
	elif status in ["censored", "uncertain", "contested", "vacant"]:
		style = status
	var label := "%s %s %s" % [str(_value(raw, "institution_id", "?")), kind, status]
	if native_owner.is_empty():
		label += " owner unknown"
	else:
		label += " owner %s" % native_owner
	if sites.is_empty():
		label += " unplaced"
	elif historical:
		label += " institution evidence at this site (historical t=%s)" % _site_evidence_ticks(sites)
	else:
		label += " institution evidence at this site"
	var history: Variant = _value(raw, "history", null)
	var boundary_tick: Variant = _value(history, "boundary_tick", null)
	var policy_version := str(_value(history, "policy_version", ""))
	return [{
		"row_id": row_id,
		"kind": "institutions",
		"identity": row_id,
		"layer": "institutions",
		"evidence_class": evidence,
		"owner_id": native_owner if evidence == "SUBJECTIVE" else null,
		"label": label,
		"institution_id": str(_value(raw, "institution_id", "")),
		"native_owner_id": _value(raw, "native_owner_id", null),
		"native_id": str(_value(raw, "native_id", "")),
		"institution_kind": kind,
		"status": status,
		"first_supported_boundary": _value(raw, "first_supported_boundary", null),
		"last_supported_boundary": _value(raw, "last_supported_boundary", null),
		"evidence_start_tick": _value(raw, "evidence_start_tick", null),
		"evidence_end_tick": _value(raw, "evidence_end_tick", null),
		"sites": sites,
		"site_points": site_points,
		"point": site_points[0] if not site_points.is_empty() else null,
		"style": style,
		"coverage_state": coverage_state,
		"historical_evidence": historical,
		"placement": "placed" if not site_points.is_empty() else "unplaced",
		"unplaced_reason": "nonspatial" if site_points.is_empty() else "",
		"click": _click(row_id, "institutions", evidence, raw, {
			"institution_id": str(_value(raw, "institution_id", "")),
			"institution_kind": kind,
			"native_owner_id": _value(raw, "native_owner_id", null),
			"status": status,
			"coverage_state": coverage_state,
			"boundary_tick": boundary_tick,
			"policy_version": policy_version,
			"site_count": sites.size(),
			"historical_evidence": historical,
			"association_basis": "typed_grounding_witness" if not sites.is_empty() else "none",
		}),
	}]


static func _site_evidence_ticks(sites: Array) -> String:
	var ticks: Array = []
	for site in sites:
		var tick: Variant = site.get("evidence_tick", null)
		if tick != null:
			ticks.append(str(tick))
	return ",".join(ticks)


static func _institution_sites(
	raw: Variant,
	world: Variant,
	centers: Dictionary,
	all_layers: Dictionary,
	repository_locations: Dictionary,
) -> Array:
	var sites: Array = []
	var context: Variant = _value(raw, "context", null)
	if context == null:
		return sites
	for anchor in _array(_value(context, "anchors", [])):
		var kind := str(_value(anchor, "kind", ""))
		if kind == "none":
			continue
		var entity_id := _optional_text(_value(anchor, "entity_id", null))
		var location_id := _optional_text(_value(anchor, "location_id", null))
		if kind in ["project", "repository"] and location_id.is_empty() and repository_locations.has(entity_id):
			location_id = str(repository_locations[entity_id])
		var point: Variant = _location_point(location_id, world, centers)
		if point == null and kind == "structure":
			point = _structure_point(entity_id, world, centers)
		if point == null:
			continue
		var source_status: Variant = null
		var source_present: Variant = null
		var source_layer := "repositories" if kind == "repository" else "projects"
		if kind in ["project", "repository"]:
			source_status = _layer_row_status(all_layers, source_layer, "repository_id" if kind == "repository" else "project_id", entity_id)
			if _layer_loaded(all_layers, source_layer):
				source_present = _layer_has_row(all_layers, source_layer, entity_id)
				if source_present and source_status != null and str(source_status) in ["destroyed", "abandoned"]:
					source_present = false
		sites.append({
			"kind": kind,
			"entity_id": entity_id,
			"location_id": location_id,
			"point": point,
			"evidence_tick": _value(anchor, "evidence_tick", null),
			"source_status": source_status,
			"source_present": source_present,
			"historical_evidence": source_present == false,
		})
	return sites


static func _layer_row_status(state: Dictionary, layer_id: String, id_key: String, entity_id: String) -> Variant:
	var layer: Variant = state.get(layer_id, null)
	if typeof(layer) != TYPE_DICTIONARY:
		return null
	for row in _array(layer.get("rows", [])):
		if str(_value(row, id_key, "")) == entity_id:
			return _value(row, "status", null)
	return null


static func _layer_loaded(state: Dictionary, layer_id: String) -> bool:
	var layer: Variant = state.get(layer_id, null)
	if typeof(layer) != TYPE_DICTIONARY:
		return false
	return str(layer.get("status", "")) in ["available", "partial", "empty"]


static func _layer_has_row(state: Dictionary, layer_id: String, entity_id: String) -> bool:
	var layer: Variant = state.get(layer_id, null)
	if typeof(layer) != TYPE_DICTIONARY:
		return false
	var id_key := "repository_id" if layer_id == "repositories" else "project_id"
	for row in _array(layer.get("rows", [])):
		if str(_value(row, id_key, "")) == entity_id:
			return true
	return false


static func _row_owner(raw: Variant) -> String:
	var history: Variant = _value(raw, "history", null)
	if history != null:
		var scope: Variant = _value(history, "scope", null)
		if scope != null:
			var owner := _normalize_owner(_value(scope, "owner_id", null))
			if not owner.is_empty():
				return owner
	var context: Variant = _value(raw, "context", null)
	if context != null:
		for ref in _array(_value(context, "source_refs", [])):
			var owner := _normalize_owner(_value(ref, "owner_id", null))
			if not owner.is_empty():
				return owner
	return ""


static func _normalize_owner(value: Variant) -> String:
	if value == null:
		return ""
	return str(value)


static func _migration_row(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
) -> Dictionary:
	var origin := str(_value(raw, "origin_location_id", ""))
	var destination := str(_value(raw, "destination_location_id", ""))
	var origin_point: Variant = _location_point(origin, world, centers)
	var destination_point: Variant = _location_point(destination, world, centers)
	var phase := str(_value(raw, "phase", ""))
	var has_route := origin_point != null and destination_point != null
	var placed := origin_point != null
	var counts := "%s/%s" % [
		str(_value(raw, "participant_count", 0)),
		str(_value(raw, "arrival_count", 0)),
	]
	var label := "%s %s %s" % [phase, origin, destination]
	if phase == "capacity_wait":
		label = "capacity wait %s %s->%s" % [str(_value(raw, "participant_count", 0)), origin, destination]
	elif phase == "preparing":
		label = "preparing %s at %s -> %s" % [str(_value(raw, "participant_count", 0)), origin, destination]
	elif phase == "arrived":
		label = "arrived %s %s->%s" % [str(_value(raw, "arrival_count", 0)), origin, destination]
	elif phase == "ended":
		label = "ended %s %s->%s" % [str(_value(raw, "ended_count", 0)), origin, destination]
	return {
		"row_id": row_id,
		"kind": "migration",
		"identity": str(_value(raw, "journey_id", row_id)),
		"layer": "migration",
		"evidence_class": evidence,
		"label": label,
		"journey_id": str(_value(raw, "journey_id", "")),
		"route_id": str(_value(raw, "route_id", "")),
		"origin_location_id": origin,
		"destination_location_id": destination,
		"participant_count": int(_value(raw, "participant_count", 0)),
		"participant_ids": _string_array(_value(raw, "participant_ids", [])),
		"phase": phase,
		"started_tick": _value(raw, "started_tick", null),
		"arrived_tick": _value(raw, "arrived_tick", null),
		"ended_tick": _value(raw, "ended_tick", null),
		"start_count": int(_value(raw, "start_count", 0)),
		"arrival_count": int(_value(raw, "arrival_count", 0)),
		"capacity_wait_count": int(_value(raw, "capacity_wait_count", 0)),
		"ended_count": int(_value(raw, "ended_count", 0)),
		"point": origin_point,
		"points": [origin_point, destination_point] if has_route else [],
		"link_style": _migration_link_style(phase),
		"placement": "placed" if placed else "unplaced",
		"unplaced_reason": "anchor_unavailable" if not placed else "",
		"click": _click(row_id, "migration", evidence, raw, {
			"journey_id": str(_value(raw, "journey_id", "")),
			"route_id": str(_value(raw, "route_id", "")),
			"origin_location_id": origin,
			"destination_location_id": destination,
			"phase": phase,
			"participant_count": int(_value(raw, "participant_count", 0)),
			"start_count": int(_value(raw, "start_count", 0)),
			"arrival_count": int(_value(raw, "arrival_count", 0)),
			"capacity_wait_count": int(_value(raw, "capacity_wait_count", 0)),
			"ended_count": int(_value(raw, "ended_count", 0)),
			"started_tick": _value(raw, "started_tick", null),
			"arrived_tick": _value(raw, "arrived_tick", null),
			"ended_tick": _value(raw, "ended_tick", null),
		}),
	}


static func _migration_link_style(phase: String) -> String:
	if phase in ["preparing", "capacity_wait", "travelling"]:
		return "intention_dashed"
	if phase == "arrived":
		return "outcome"
	return "ended"


static func _trade_row(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
) -> Dictionary:
	var occurrence := _optional_text(_value(raw, "occurrence_location_id", null))
	var point: Variant = _location_point(occurrence, world, centers)
	var forward: Array = _item_count_rows(_value(raw, "forward_items", []))
	var reverse: Array = _item_count_rows(_value(raw, "reverse_items", []))
	return {
		"row_id": row_id,
		"kind": "trade",
		"identity": row_id,
		"layer": "trade",
		"evidence_class": evidence,
		"label": "%s completed exchange(s) at %s" % [
			str(_value(raw, "completed_exchange_count", 0)),
			occurrence if not occurrence.is_empty() else "unknown",
		],
		"occurrence_location_id": occurrence if not occurrence.is_empty() else null,
		"participant_ids": _string_array(_value(raw, "participant_ids", [])),
		"completed_exchange_count": int(_value(raw, "completed_exchange_count", 0)),
		"forward_items": forward,
		"reverse_items": reverse,
		"forward_items_text": _item_count_text(forward),
		"reverse_items_text": _item_count_text(reverse),
		"point": point,
		"points": [],
		"style": "local_loop",
		"placement": "placed" if point != null else "unplaced",
		"unplaced_reason": "anchor_unavailable" if point == null else "",
		"click": _click(row_id, "trade", evidence, raw, {
			"occurrence_location_id": occurrence if not occurrence.is_empty() else null,
			"participant_count": int(_value(raw, "participant_count", 0)),
			"completed_exchange_count": int(_value(raw, "completed_exchange_count", 0)),
			"forward_items_text": _item_count_text(forward),
			"reverse_items_text": _item_count_text(reverse),
			"event_ref_count": _array(_value(raw, "source_refs", [])).size()
				if _value(raw, "context", null) == null
				else _array(_value(_value(raw, "context", null), "source_refs", [])).size(),
		}),
	}


static func _culture_row(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
) -> Dictionary:
	var point: Variant = _anchor_point(raw, world, centers)
	var basis := str(_value(raw, "basis", ""))
	var denominator: Variant = _value(raw, "eligible_owner_count", null)
	var unavailable := int(_value(raw, "unavailable_owner_count", 0))
	var proportion: Variant = _value(raw, "proportion", null)
	var denominator_text := "unknown" if denominator == null else str(denominator)
	var proportion_text := "unknown" if proportion == null else "%s%%" % str(
		round(float(proportion) * 1000.0) / 10.0
	)
	var label := "%s carriers %s/%s (%s) basis %s" % [
		str(_value(raw, "representation_id", "?")),
		str(_value(raw, "carrier_count", 0)),
		denominator_text,
		proportion_text,
		basis,
	]
	if unavailable > 0:
		label += " unknown owners %s" % unavailable
	return {
		"row_id": row_id,
		"kind": "culture",
		"identity": row_id,
		"layer": "culture",
		"evidence_class": evidence,
		"label": label,
		"trait_id": str(_value(raw, "trait_id", "")),
		"representation_id": str(_value(raw, "representation_id", "")),
		"basis": basis,
		"carrier_count": int(_value(raw, "carrier_count", 0)),
		"carrier_ids": _string_array(_value(raw, "carrier_ids", [])),
		"eligible_owner_count": denominator,
		"unavailable_owner_count": unavailable,
		"proportion": proportion,
		"proportion_text": proportion_text,
		"point": point,
		"points": [],
		"style": "hatch",
		"nonspatial": point == null,
		"placement": "placed" if point != null else "unplaced",
		"unplaced_reason": "nonspatial" if point == null else "",
		"click": _click(row_id, "culture", evidence, raw, {
			"trait_id": str(_value(raw, "trait_id", "")),
			"representation_id": str(_value(raw, "representation_id", "")),
			"basis": basis,
			"carrier_count": int(_value(raw, "carrier_count", 0)),
			"eligible_owner_count": denominator,
			"unavailable_owner_count": unavailable,
			"proportion_text": proportion_text,
			"boundary_tick": _value(_value(raw, "history", null), "boundary_tick", null),
			"policy_version": str(_value(_value(raw, "history", null), "policy_version", "")),
		}),
	}


static func _technology_rows(
	raw: Variant,
	row_id: String,
	evidence: String,
	world: Variant,
	centers: Dictionary,
	state: Dictionary,
) -> Array:
	var acquisition: Variant = _value(raw, "acquisition_boundary", null)
	var boundary: Variant = _state_boundary(state)
	if acquisition != null and boundary != null and int(acquisition) > int(boundary):
		return []
	var holder := str(_value(raw, "holder_id", ""))
	var holder_point: Variant = _agent_point(holder, world, centers)
	var attribution := str(_value(raw, "attribution", ""))
	var modality := str(_value(raw, "modality", ""))
	var source_owner := _optional_text(_value(raw, "source_owner_id", null))
	var source_knowledge := _optional_text(_value(raw, "source_knowledge_id", null))
	var source_point: Variant = _agent_point(source_owner, world, centers)
	var has_edge := attribution == "attributable" and holder_point != null and source_point != null
	var source_text := ""
	if attribution == "attributable":
		source_text = "source %s" % source_owner
	elif attribution in ["unknown", "ambiguous", "rediscovery"]:
		source_text = "source %s" % attribution
	var label := "%s %s %s %s" % [
		str(_value(raw, "knowledge_id", "?")),
		str(_value(raw, "status", "")),
		modality,
		source_text,
	]
	label = label.strip_edges()
	return [{
		"row_id": row_id,
		"kind": "technology",
		"identity": row_id,
		"layer": "technology",
		"evidence_class": evidence,
		"label": label,
		"knowledge_id": str(_value(raw, "knowledge_id", "")),
		"holder_id": holder,
		"status": str(_value(raw, "status", "")),
		"acquisition_boundary": acquisition,
		"attribution": attribution,
		"modality": modality,
		"source_owner_id": _value(raw, "source_owner_id", null),
		"source_knowledge_id": _value(raw, "source_knowledge_id", null),
		"living_holder_count": _value(raw, "living_holder_count", null),
		"eligible_owner_count": _value(raw, "eligible_owner_count", null),
		"point": holder_point,
		"points": [source_point, holder_point] if has_edge else [],
		"link_style": _technology_link_style(modality),
		"has_diffusion_edge": has_edge,
		"style": "lost" if str(_value(raw, "status", "")) == "lost" else "held",
		"placement": "placed" if holder_point != null else "unplaced",
		"unplaced_reason": "anchor_unavailable" if holder_point == null else "",
		"click": _click(row_id, "technology", evidence, raw, {
			"knowledge_id": str(_value(raw, "knowledge_id", "")),
			"holder_id": holder,
			"status": str(_value(raw, "status", "")),
			"attribution": attribution,
			"modality": modality,
			"source_owner_id": _value(raw, "source_owner_id", null),
			"source_knowledge_id": _value(raw, "source_knowledge_id", null),
			"acquisition_boundary": acquisition,
			"living_holder_count": _value(raw, "living_holder_count", null),
			"eligible_owner_count": _value(raw, "eligible_owner_count", null),
		}),
	}]


static func _technology_link_style(modality: String) -> String:
	match modality:
		"teaching":
			return "teaching_dashed"
		"record":
			return "record_dotted"
		"observation":
			return "observation_dashdot"
		"practice":
			return "practice_solid"
		_:
			return "unknown_dotted"


static func _state_boundary(state: Dictionary) -> Variant:
	var cursor: Variant = state.get("cursor", null)
	if typeof(cursor) == TYPE_DICTIONARY:
		return cursor.get("boundary_tick", null)
	return null


static func _item_count_rows(source: Variant) -> Array:
	var rows: Array = []
	for item in _array(source):
		rows.append({
			"kind": str(_value(item, "kind", "")),
			"count": int(_value(item, "count", 0)),
		})
	return rows


static func _item_count_text(items: Array) -> String:
	var parts: Array = []
	for item in items:
		parts.append("%s %s" % [str(item.get("kind", "")), str(item.get("count", 0))])
	return ", ".join(parts)


static func _anchor_point(raw: Variant, world: Variant, centers: Dictionary) -> Variant:
	var context: Variant = _value(raw, "context", null)
	if context == null:
		return null
	for anchor in _array(_value(context, "anchors", [])):
		var kind := str(_value(anchor, "kind", ""))
		if kind == "location":
			var point: Variant = _location_point(str(_value(anchor, "location_id", "")), world, centers)
			if point != null:
				return point
	return null


static func _agent_point(agent_id: String, world: Variant, centers: Dictionary) -> Variant:
	if agent_id.is_empty():
		return null
	var location_id := _agent_location(agent_id, world)
	if location_id.is_empty():
		return null
	return _location_point(location_id, world, centers)


static func _repository_locations(layer_state: Dictionary) -> Dictionary:
	var result := {}
	var state: Variant = layer_state.get("repositories", null)
	if typeof(state) != TYPE_DICTIONARY:
		return result
	if str(state.get("status", "")) not in ["available", "partial", "empty"]:
		return result
	for row in _array(state.get("rows", [])):
		var repository_id := str(_value(row, "repository_id", ""))
		var location_id := _optional_text(_value(row, "location_id", null))
		if repository_id.is_empty() or location_id.is_empty():
			continue
		result[repository_id] = location_id
	return result


static func _location_point(location_id: String, world: Variant, centers: Dictionary) -> Variant:
	if location_id.is_empty():
		return null
	if centers.has(location_id):
		var center: Variant = centers[location_id]
		if typeof(center) == TYPE_VECTOR2:
			return center
	for location in _array(_value(world, "locations", [])):
		if str(_value(location, "location_id", "")) != location_id:
			continue
		return _presentation_point(location)
	return null


static func _presentation_point(location: Variant) -> Variant:
	var presentation: Variant = _value(location, "presentation", null)
	if presentation == null:
		return null
	var bounds: Variant = _value(presentation, "visual_bounds", null)
	if bounds != null:
		var x := float(_value(bounds, "x", 0.0))
		var y := float(_value(bounds, "y", 0.0))
		var width := float(_value(bounds, "width", 0.0))
		var height := float(_value(bounds, "height", 0.0))
		return Scale.to_pixels(x + width * 0.5, y + height * 0.5)
	var screen: Variant = _value(presentation, "screen_position", null)
	if screen != null:
		return Scale.to_pixels(float(_value(screen, "x", 0.0)), float(_value(screen, "y", 0.0)))
	return null


static func _structure_point(structure_id: String, world: Variant, centers: Dictionary) -> Variant:
	if structure_id.is_empty():
		return null
	for structure in _array(_value(world, "structures", [])):
		if str(_value(structure, "structure_id", "")) != structure_id:
			continue
		return _location_point(str(_value(structure, "location_id", "")), world, centers)
	return null


static func _agent_location(entity_id: String, world: Variant) -> String:
	var found := ""
	for agent in _array(_value(world, "agents", [])):
		var body_id := str(_value(agent, "entity_id", ""))
		var logical_id: Variant = _value(agent, "agent_id", null)
		var matches := body_id == entity_id
		if not matches and logical_id != null:
			matches = str(logical_id) == entity_id
		if not matches:
			continue
		if not found.is_empty() and found != body_id:
			return ""
		found = body_id
	if found.is_empty():
		return ""
	for agent in _array(_value(world, "agents", [])):
		if str(_value(agent, "entity_id", "")) == found:
			return str(_value(agent, "location_id", ""))
	return ""


static func _normalize_cursor(cursor: Dictionary) -> Dictionary:
	if cursor.is_empty() or cursor.get("tick", null) == null:
		return {}
	return {
		"run_id": str(cursor.get("run_id", "")),
		"tick": int(cursor.get("tick", 0)),
		"revision": cursor.get("revision", null),
		"boundary_tick": cursor.get("boundary_tick", null),
		"through_sequence": cursor.get("through_sequence", null),
	}


static func _cursor_matches(state_cursor: Dictionary, display: Dictionary) -> bool:
	if int(state_cursor.get("tick", -1)) != int(display.get("tick", -2)):
		return false
	if state_cursor.get("revision", null) != null and display.get("revision", null) != null:
		if int(state_cursor["revision"]) != int(display["revision"]):
			return false
	if state_cursor.get("boundary_tick", null) != display.get("boundary_tick", null):
		return false
	if state_cursor.get("through_sequence", null) != display.get("through_sequence", null):
		return false
	var state_run := str(state_cursor.get("run_id", ""))
	var display_run := str(display.get("run_id", ""))
	if not state_run.is_empty() and not display_run.is_empty() and state_run != display_run:
		return false
	return true


static func _evidence_label(layer_id: String, state: Dictionary) -> String:
	var raw := str(state.get("evidence_class", "")).to_upper()
	if raw.begins_with("OBJECTIVE"):
		return Evidence.LABEL_OBJECTIVE
	if raw.begins_with("SUBJECTIVE"):
		return Evidence.LABEL_SUBJECTIVE
	if raw.begins_with("ANALYTICAL"):
		return Evidence.LABEL_ANALYTICAL
	if layer_id in ["regions", "routes", "locations", "migration", "projects", "repositories", "records"]:
		return Evidence.LABEL_OBJECTIVE
	if layer_id in ["settlements", "trade", "culture"]:
		return Evidence.LABEL_ANALYTICAL
	return Evidence.LABEL_ANALYTICAL


static func _size_band(count: int) -> String:
	if count <= 0:
		return "none"
	if count < 3:
		return "small"
	if count < 7:
		return "medium"
	return "large"


static func _ratio(progress: int, required: int) -> Variant:
	if required <= 0:
		return null
	return float(progress) / float(required)


static func _clamp_ratio(value: Variant) -> float:
	if value == null:
		return 0.0
	return clampf(float(value), 0.0, 1.0)


static func _progress_label(progress: int, required: int) -> String:
	if required <= 0:
		return "N/A"
	return "%s/%s" % [progress, required]


static func _row_counts(rows: Array) -> Dictionary:
	var counts := {}
	for row in rows:
		var kind := str(_value(row, "kind", ""))
		counts[kind] = int(counts.get(kind, 0)) + 1
	return counts


static func _bounds(points: Array) -> Rect2:
	if points.is_empty():
		return Rect2()
	var minimum := points[0] as Vector2
	var maximum := points[0] as Vector2
	for point in points:
		var value := point as Vector2
		minimum.x = minf(minimum.x, value.x)
		minimum.y = minf(minimum.y, value.y)
		maximum.x = maxf(maximum.x, value.x)
		maximum.y = maxf(maximum.y, value.y)
	return Rect2(minimum, maximum - minimum)


static func _raw_row_id(raw: Variant, kind: String, layer_id: String) -> String:
	var context: Variant = _value(raw, "context", null)
	if context != null:
		var row_id := str(_value(context, "row_id", ""))
		if not row_id.is_empty():
			return row_id
	for key in [
		"region_id", "route_id", "location_id", "candidate_id", "project_id",
		"repository_id", "record_id", "journey_id", "group_id", "institution_id",
	]:
		var value := _optional_text(_value(raw, key, null))
		if not value.is_empty():
			return "%s:%s" % [layer_id, value]
	return "%s:%s" % [layer_id, kind]


static func _failure(reason: String) -> Dictionary:
	return {
		"ok": false,
		"reason_code": reason,
		"cursor": {},
		"layers": {},
		"rows": [],
		"unresolved_anchor_count": 0,
		"unresolved_row_ids": [],
		"warning_codes": [reason],
		"counts": {},
	}


static func _value(source: Variant, key: String, fallback: Variant = null) -> Variant:
	if source == null:
		return fallback
	if typeof(source) == TYPE_DICTIONARY:
		return source.get(key, fallback)
	return source.get(key)


static func _array(source: Variant) -> Array:
	if typeof(source) == TYPE_ARRAY:
		return source
	return []


static func _string_array(source: Variant) -> Array:
	var result: Array = []
	if typeof(source) != TYPE_ARRAY:
		return result
	for value in source:
		result.append(str(value))
	return result


static func _optional_text(value: Variant) -> String:
	if value == null:
		return ""
	return str(value)
