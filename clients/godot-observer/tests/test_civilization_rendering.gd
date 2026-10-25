extends RefCounted

const Civ := preload("res://scripts/protocol/civilization.gd")
const Plan := preload("res://scripts/presentation/civilization_plan.gd")
const WorldScene := preload("res://scenes/world_view.tscn")
const BASE := "res://fixtures/protocol/civilization/"


class WorldStub:
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
	_expect(failures, _wire_fixtures(), "wire fixtures")
	_expect(failures, _facility_rows(), "facility rows")
	_expect(failures, _settlements(), "settlements")
	_expect(failures, _projects_and_public_acts(), "projects/public acts")
	_expect(failures, _repositories_and_records(), "repositories/records")
	_expect(failures, _flows(), "flows")
	_expect(failures, _flow_caps(), "flow caps")
	_expect(failures, _beliefs(), "beliefs")
	_expect(failures, _cursors_and_anchors(), "cursors/anchors")
	_expect(failures, _scene_and_clearing(), "scene/clearing")
	return failures


func _expect(failures: Array, error: String, label: String) -> void:
	if not error.is_empty():
		failures.append("%s: %s" % [label, error])


func _load(name: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(BASE + name))


func _world() -> WorldStub:
	var world := WorldStub.new()
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


func _centers() -> Dictionary:
	return {
		"loc-1": Vector2(100, 100),
		"loc-2": Vector2(300, 100),
		"loc-3": Vector2(200, 240),
	}


func _cursor(tick: int = 4, revision: int = 4) -> Dictionary:
	return {
		"run_id": "run-physical",
		"world_id": "world-physical",
		"tick": tick,
		"through_sequence": null,
		"boundary_tick": tick,
		"revision": revision,
	}


func _map_state(section: String) -> Dictionary:
	var parsed: Dictionary = Civ.parse_map(_load("map_%s.json" % section))
	var model = parsed["value"]
	return {
		"status": "available",
		"layer": section,
		"evidence_class": model.scope.evidence_class,
		"owner_id": model.scope.owner_id,
		"cursor": _cursor(),
		"rows": model.rows,
		"coverage": model.coverage,
		"truncated": model.truncated,
		"policy_version": "objective-map-v1",
	}


func _overlay_state(payload: Dictionary, layer_id: String, tick: int = 4, revision: int = 4) -> Dictionary:
	var modified := payload.duplicate(true)
	modified["run_id"] = "run-physical"
	modified["world_id"] = "world-physical"
	modified["requested_tick"] = tick
	modified["resolved_cursor"]["run_id"] = "run-physical"
	modified["resolved_cursor"]["world_id"] = "world-physical"
	modified["resolved_cursor"]["tick"] = tick
	modified["resolved_cursor"]["boundary_tick"] = tick
	modified["resolved_cursor"]["revision"] = revision
	modified["source_revision"] = revision
	modified["window"]["end_tick"] = tick
	for row in modified.get("rows", []):
		row["history"]["boundary_tick"] = tick
		row["history"]["window"]["end_tick"] = tick
	var parsed: Dictionary = Civ.parse_overlay(modified)
	if not bool(parsed.get("ok", false)):
		return {"status": "error", "reason_code": str(parsed.get("reason_code", ""))}
	var model = parsed["value"]
	return {
		"status": "available",
		"layer": layer_id,
		"evidence_class": model.scope.evidence_class,
		"owner_id": model.scope.owner_id,
		"cursor": _cursor(tick, revision),
		"window": {"start_tick": 0, "end_tick": tick},
		"coverage": model.coverage,
		"rows": model.rows,
		"truncated": model.truncated,
		"policy_version": "civilization-overlays.v1",
	}


func _wire_fixtures() -> String:
	for section in Civ.SECTIONS:
		var state := _map_state(section)
		var plan: Dictionary = Plan.build_semantic(
			_world(),
			{section: state},
			_cursor(),
			_centers(),
		)
		if not bool(plan.get("ok", false)):
			return "%s rejected: %s" % [section, str(plan.get("reason_code", ""))]
		if plan.get("rows", []).size() != state["rows"].size():
			return "%s row count mismatch" % section
		for row in plan.get("rows", []):
			if str(row.get("evidence_class", "")) != "OBJECTIVE":
				return "%s row is not objective" % section
	return ""


func _facility_rows() -> String:
	var states := {
		"regions": _map_state("regions"),
		"routes": _map_state("routes"),
		"locations": _map_state("locations"),
		"projects": _map_state("projects"),
		"repositories": _map_state("repositories"),
		"records": _map_state("records"),
	}
	var plan: Dictionary = Plan.build_semantic(_world(), states, _cursor(), _centers())
	if not bool(plan.get("ok", false)):
		return "plan rejected: %s" % str(plan.get("reason_code", ""))
	var counts: Dictionary = plan.get("counts", {})
	if int(counts.get("locations", 0)) != 2:
		return "location rows missing"
	if int(counts.get("regions", 0)) != 1:
		return "region rows missing"
	if int(counts.get("routes", 0)) != 1:
		return "route rows missing"
	if int(counts.get("projects", 0)) != 1:
		return "project rows missing"
	if int(counts.get("repositories", 0)) != 2:
		return "repository rows missing"
	if int(counts.get("records", 0)) != 1:
		return "record rows missing"
	var location_points := {}
	for row in plan.get("rows", []):
		if str(row.get("kind", "")) == "locations":
			location_points[str(row["location_id"])] = row.get("point", null)
	if location_points.get("loc-1", null) != Vector2(100, 100):
		return "loc-1 center moved"
	if location_points.get("loc-2", null) != Vector2(300, 100):
		return "loc-2 center moved"
	var draw: Dictionary = Plan.draw_plan(plan, "full")
	var link_kinds := {}
	for link in draw.get("links", []):
		link_kinds[str(link.get("kind", ""))] = int(link_kinds.get(str(link.get("kind", "")), 0)) + 1
	if int(link_kinds.get("region_envelope", 0)) != 1:
		return "region envelope missing"
	if int(link_kinds.get("configured_route", 0)) != 1:
		return "configured route missing"
	for kind in link_kinds.keys():
		if kind not in ["region_envelope", "configured_route"]:
			return "invented link: %s" % kind
	for link in draw.get("links", []):
		if str(link.get("kind", "")) == "configured_route":
			var points: Array = link.get("points", [])
			if points.size() != 2 or points[0] != Vector2(100, 100) or points[1] != Vector2(300, 100):
				return "route endpoints moved"
		if str(link.get("kind", "")) == "region_envelope":
			var bounds: Rect2 = link.get("bounds", Rect2())
			if bounds.size == Vector2.ZERO:
				return "region bounds missing"
	var project := _row(plan, "projects", "project-1")
	if project.is_empty():
		return "project identity missing"
	if project.get("linked_structure_point", null) != Vector2(100, 100):
		return "linked structure anchor missing"
	if abs(float(project.get("labor_ratio", 0.0)) - 1.0 / 3.0) > 0.0001:
		return "labor ratio mismatch"
	if project.get("material_required", -1) != 2:
		return "raw material denominator lost"
	var record := _row(plan, "records", "record-1")
	if record.is_empty() or record.get("point", null) != Vector2(300, 100):
		return "record placement missing"
	if str(record.get("placement_basis", "")) != "location":
		return "record placement basis changed"
	var serialized := JSON.stringify(plan)
	for leaked in ["mark_text", "marks", "interpretation", "content"]:
		if serialized.contains(leaked):
			return "record payload leaked: %s" % leaked
	return ""


func _settlements() -> String:
	var payload: Dictionary = _load("overlay_settlements.json")
	var state := _overlay_state(payload, "settlements")
	var plan: Dictionary = Plan.build_semantic(_world(), {"settlements": state}, _cursor(), _centers())
	if not bool(plan.get("ok", false)):
		return "settlement plan rejected"
	var settlements: Array = _rows(plan, "settlements")
	if settlements.size() != 2:
		return "two settlements did not remain separate"
	if settlements[0].get("point", null) != Vector2(100, 100):
		return "settlement anchor missing"
	if settlements[1].get("point", null) != Vector2(300, 100):
		return "second settlement anchor missing"
	for row in settlements:
		if str(row.get("evidence_class", "")) != "ANALYTICAL":
			return "settlement promoted to objective"
		if bool(row.get("objective", false)):
			return "objective settlement class invented"
		if str(row.get("candidate_id", "")).is_empty():
			return "settlement identity missing"
	if str(settlements[0].get("style", "")) != "solid":
		return "active settlement style"
	var later_payload := payload.duplicate(true)
	later_payload["rows"][0]["status"] = "inactive"
	later_payload["rows"][0]["eligible_occupancy"] = 0
	var later := _overlay_state(later_payload, "settlements", 5, 5)
	var later_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"settlements": later},
		_cursor(5, 5),
		_centers(),
	)
	if not bool(later_plan.get("ok", false)):
		return "later settlement plan rejected"
	var later_rows: Array = _rows(later_plan, "settlements")
	if later_rows.size() != 2:
		return "settlement identity lost across boundary"
	if str(later_rows[0].get("candidate_id", "")) != str(settlements[0].get("candidate_id", "")):
		return "settlement identity changed across boundary"
	if str(later_rows[0].get("style", "")) != "hollow":
		return "historical status change not styled"
	var backward := state.duplicate(true)
	backward["rows"] = []
	var backward_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"settlements": backward},
		_cursor(),
		_centers(),
	)
	if not bool(backward_plan.get("ok", false)):
		return "empty settlement plan rejected"
	if not _rows(backward_plan, "settlements").is_empty():
		return "backward seek retained settlement rows"
	var uncertain_payload := payload.duplicate(true)
	uncertain_payload["rows"][0]["status"] = "censored"
	uncertain_payload["coverage"]["state"] = "partial"
	uncertain_payload["coverage"]["reason"] = "capture_gap"
	uncertain_payload["coverage"]["missing_intervals"] = [{"start_tick": 2, "end_tick": 3}]
	var uncertain := _overlay_state(uncertain_payload, "settlements")
	var uncertain_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"settlements": uncertain},
		_cursor(),
		_centers(),
	)
	var uncertain_row := _row(uncertain_plan, "settlements", "settlement:loc-1")
	if str(uncertain_row.get("style", "")) != "uncertain":
		return "censored settlement rendered as confirmed"
	return ""


func _projects_and_public_acts() -> String:
	var payload: Dictionary = _load("map_projects.json")
	payload["rows"][0]["public_acts"] = {
		"benefit_count": 2,
		"draw_count": 1,
		"maintenance_count": 0,
		"opposition_count": 3,
	}
	var project_state := _map_state_from_payload(payload, "projects")
	var plan: Dictionary = Plan.build_semantic(
		_world(),
		{"projects": project_state},
		_cursor(),
		_centers(),
	)
	if not bool(plan.get("ok", false)):
		return "project plan rejected"
	if int(plan.get("counts", {}).get("projects", 0)) != 1:
		return "project row missing"
	if int(plan.get("counts", {}).get("public_act", 0)) != 3:
		return "public acts not separated"
	var acts := {}
	for row in _rows(plan, "public_act"):
		acts[str(row.get("act", ""))] = int(row.get("count", 0))
	if int(acts.get("benefit", 0)) != 2 or int(acts.get("draw", 0)) != 1 or int(acts.get("opposition", 0)) != 3:
		return "public act counts changed"
	if acts.has("maintenance"):
		return "zero public act emitted"
	var zero_payload: Dictionary = _load("map_projects.json")
	zero_payload["rows"][0]["labor_required"] = 0
	zero_payload["rows"][0]["labor_progress"] = 0
	zero_payload["rows"][0]["material_required"] = 0
	zero_payload["rows"][0]["material_progress"] = 0
	var zero_state := _map_state_from_payload(zero_payload, "projects")
	var zero_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"projects": zero_state},
		_cursor(),
		_centers(),
	)
	var zero_row := _row(zero_plan, "projects", "project-1")
	if zero_row.get("labor_ratio", null) != null:
		return "zero denominator became a ratio"
	if zero_row.get("material_ratio", null) != null:
		return "zero denominator became a material ratio"
	if not str(zero_row.get("label", "")).contains("N/A"):
		return "zero denominator not labeled N/A"
	var zero_draw: Dictionary = Plan.draw_plan(zero_plan, "full")
	for glyph in zero_draw.get("glyphs", []):
		if str(glyph.get("kind", "")) == "projects" and float(glyph.get("labor_ratio", -1.0)) != 0.0:
			return "visual progress not clamped"
	return ""


func _repositories_and_records() -> String:
	var repos: Dictionary = _load("map_repositories.json")
	repos["rows"][0]["status"] = "neglected"
	repos["rows"][1]["status"] = "destroyed"
	var repo_state := _map_state_from_payload(repos, "repositories")
	var repo_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"repositories": repo_state},
		_cursor(),
		_centers(),
	)
	if not bool(repo_plan.get("ok", false)):
		return "repository plan rejected"
	var styles := {}
	for row in _rows(repo_plan, "repositories"):
		styles[str(row.get("repository_id", ""))] = str(row.get("style", ""))
	if str(styles.get("repo-0000", "")) != "neglected":
		return "neglected repository style missing"
	if str(styles.get("repo-0001", "")) != "destroyed":
		return "destroyed repository style missing"
	var records: Dictionary = _load("map_records.json")
	records["rows"][0]["integrity"] = "damaged"
	var record_state := _map_state_from_payload(records, "records")
	var record_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"records": record_state},
		_cursor(),
		_centers(),
	)
	var record := _row(record_plan, "records", "record-1")
	if str(record.get("style", "")) != "damaged":
		return "damaged record style missing"
	var click: Dictionary = record.get("click", {})
	if click.get("summary", {}).has("marks") or click.get("summary", {}).has("content"):
		return "record click exposes payload"
	if click.get("source_refs", []).is_empty():
		return "record click lost source refs"
	if click.has("command") or click.has("command_kind"):
		return "record click invented a command surface"
	return ""


func _cursors_and_anchors() -> String:
	var payload: Dictionary = _load("overlay_settlements.json")
	var state := _overlay_state(payload, "settlements")
	var mismatched: Dictionary = Plan.build_semantic(
		_world(),
		{"settlements": state},
		_cursor(5, 5),
		_centers(),
	)
	if bool(mismatched.get("ok", false)) or str(mismatched.get("reason_code", "")) != "cursor_mismatch":
		return "mismatched cursor accepted"
	var centers := _centers()
	centers.erase("loc-2")
	var unplaced: Dictionary = Plan.build_semantic(
		_world(),
		{"settlements": state},
		_cursor(),
		centers,
	)
	if not bool(unplaced.get("ok", false)):
		return "unplaced plan rejected"
	if int(unplaced.get("unresolved_anchor_count", 0)) != 1:
		return "unresolved anchor not counted"
	if not unplaced.get("warning_codes", []).has("anchor_unavailable"):
		return "unresolved warning missing"
	for row in _rows(unplaced, "settlements"):
		if str(row.get("location_id", "")) == "loc-2":
			if row.get("point", null) != null:
				return "unresolved anchor gained an origin point"
			if str(row.get("placement", "")) != "unplaced":
				return "unresolved anchor rendered as placed"
	return ""


func _scene_and_clearing() -> String:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return "scene tree missing"
	var view: Node2D = WorldScene.instantiate()
	tree.root.add_child(view)
	var facilities = view.get_node_or_null("CivilizationFacilities")
	if facilities == null or not facilities.has_method("apply_plan"):
		view.free()
		return "civilization facilities layer missing"
	var flows = view.get_node_or_null("CivilizationFlows")
	if flows == null or not flows.has_method("apply_plan"):
		view.free()
		return "civilization flows layer missing"
	var beliefs = view.get_node_or_null("CivilizationBeliefs")
	if beliefs == null or not beliefs.has_method("apply_plan"):
		view.free()
		return "civilization beliefs layer missing"
	var states := {
		"locations": _map_state("locations"),
		"settlements": _overlay_state(_load("overlay_settlements.json"), "settlements"),
	}
	var plan: Dictionary = Plan.build_semantic(_world(), states, _cursor(), _centers())
	facilities.apply_plan(plan)
	if int(facilities.glyph_count()) == 0:
		view.free()
		return "facilities rendered no glyphs"
	facilities.apply_plan(Plan.build_semantic({}, {}, _cursor(), {}))
	if facilities.glyph_count() != 0:
		view.free()
		return "overlay off retained glyphs"
	facilities.clear_plan()
	if facilities.has_plan():
		view.free()
		return "clear retained prior plan"
	var flow_plan: Dictionary = Plan.build_semantic(
		_world(),
		{
			"migration": _overlay_state(_load("overlay_migration.json"), "migration"),
			"technology": _overlay_state(
				_technology_payload("attributable", "teaching", "agent-b", "knowledge-0"),
				"technology",
			),
		},
		_cursor(),
		_centers(),
	)
	flows.apply_plan(flow_plan)
	if int(flows.link_count()) < 2:
		view.free()
		return "flow layer rendered no segments"
	if int(flows.glyph_count()) < 1:
		view.free()
		return "flow layer rendered no glyphs"
	flows.clear_plan()
	if flows.has_plan():
		view.free()
		return "flow clear retained prior plan"
	var owner_a := _overlay_state(
		_subjective_group_payload("agent-a", "local-1", ["agent-a"]),
		"social_groups",
		4,
		4,
	)
	var belief_plan: Dictionary = Plan.build_semantic(
		_world(),
		{
			"social_groups": owner_a,
			"institutions": _overlay_state(
				_institution_payload("concept", "recognized", [{
					"kind": "project",
					"location_id": "loc-1",
					"entity_id": "project-1",
					"evidence_ref": {"source_kind": "project", "source_id": "project-1", "tick": 3, "owner_id": "agent-a"},
					"evidence_tick": 3,
				}]),
				"institutions",
			),
			"projects": _map_state("projects"),
		},
		_cursor(),
		_centers(),
	)
	beliefs.apply_plan(belief_plan)
	if int(beliefs.node_count()) < 2:
		view.free()
		return "belief layer rendered no member/site nodes"
	var owner_b := _overlay_state(
		_subjective_group_payload("agent-b", "local-1", ["agent-b"]),
		"social_groups",
		4,
		4,
	)
	var switched: Dictionary = Plan.build_semantic(
		_world(),
		{"social_groups": owner_b},
		_cursor(),
		_centers(),
	)
	beliefs.apply_plan(switched)
	if int(beliefs.node_count()) != 1:
		view.free()
		return "owner switch retained the prior membership halo"
	beliefs.clear_plan()
	if beliefs.has_plan():
		view.free()
		return "belief clear retained prior plan"
	view.free()
	return ""


func _flows() -> String:
	var migration := _overlay_state(_load("overlay_migration.json"), "migration")
	var migration_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"migration": migration},
		_cursor(),
		_centers(),
	)
	if not bool(migration_plan.get("ok", false)):
		return "migration plan rejected"
	var migration_row := _one(_rows(migration_plan, "migration"))
	if migration_row.is_empty():
		return "migration row missing"
	if migration_row.get("point", null) != Vector2(100, 100):
		return "migration origin anchor missing"
	if migration_row.get("points", []).size() != 2:
		return "migration endpoints missing"
	if str(migration_row.get("link_style", "")) != "outcome":
		return "arrival style missing"
	if str(migration_row.get("evidence_class", "")) != "OBJECTIVE":
		return "migration is not objective"
	var migration_draw: Dictionary = Plan.draw_plan(migration_plan, "full")
	if _link_count(migration_draw, "journey_outcome") != 1:
		return "arrival outcome link missing"
	var preparing_payload: Dictionary = _load("overlay_migration.json")
	preparing_payload["rows"][0]["phase"] = "preparing"
	preparing_payload["rows"][0]["arrived_tick"] = null
	preparing_payload["rows"][0]["arrival_count"] = 0
	var preparing := _overlay_state(preparing_payload, "migration")
	var preparing_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"migration": preparing},
		_cursor(),
		_centers(),
	)
	var preparing_row: Dictionary = _rows(preparing_plan, "migration")[0]
	if str(preparing_row.get("link_style", "")) != "intention_dashed":
		return "preparing intention style missing"
	if not str(preparing_row.get("label", "")).contains("preparing"):
		return "preparing label missing"
	var ended_payload: Dictionary = _load("overlay_migration.json")
	ended_payload["rows"][0]["phase"] = "ended"
	ended_payload["rows"][0]["ended_tick"] = 4
	ended_payload["rows"][0]["ended_count"] = 1
	var ended := _overlay_state(ended_payload, "migration")
	var ended_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"migration": ended},
		_cursor(),
		_centers(),
	)
	var ended_draw: Dictionary = Plan.draw_plan(ended_plan, "full")
	if _link_count(ended_draw, "journey_ended") != 1:
		return "ended journey style missing"
	var trade := _overlay_state(_load("overlay_trade.json"), "trade")
	var trade_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"trade": trade},
		_cursor(),
		_centers(),
	)
	if not bool(trade_plan.get("ok", false)):
		return "trade plan rejected"
	var trade_row := _one(_rows(trade_plan, "trade"))
	if trade_row.get("point", null) != Vector2(100, 100):
		return "trade occurrence anchor missing"
	if not trade_row.get("points", []).is_empty():
		return "trade invented endpoints"
	if str(trade_row.get("forward_items_text", "")) != "tool 1":
		return "forward item kinds changed"
	if str(trade_row.get("reverse_items_text", "")) != "food 1":
		return "reverse item kinds changed"
	if str(trade_row.get("evidence_class", "")) != "ANALYTICAL":
		return "trade summary is not analytical"
	if trade_row.get("click", {}).get("source_refs", []).is_empty():
		return "trade objective event drill-down missing"
	var trade_draw: Dictionary = Plan.draw_plan(trade_plan, "full")
	if _link_count(trade_draw, "knowledge_diffusion") != 0:
		return "trade became a transport link"
	var global_culture := _overlay_state(_load("overlay_culture.json"), "culture")
	var global_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"culture": global_culture},
		_cursor(),
		_centers(),
	)
	var global_row := _one(_rows(global_plan, "culture"))
	if global_row.get("point", null) != null:
		return "global culture row gained a map origin"
	if str(global_row.get("unplaced_reason", "")) != "nonspatial":
		return "global culture row is not nonspatial"
	if int(global_plan.get("unresolved_anchor_count", 0)) != 0:
		return "nonspatial row counted as unresolved anchor"
	var global_draw: Dictionary = Plan.draw_plan(global_plan, "full")
	for glyph in global_draw.get("glyphs", []):
		if str(glyph.get("kind", "")) == "culture":
			return "nonspatial culture glyph painted"
	var local_payload: Dictionary = _load("overlay_culture.json")
	local_payload["rows"][0]["basis"] = "location_presence"
	local_payload["rows"][0]["context"]["anchors"] = [{
		"kind": "location",
		"location_id": "loc-1",
		"entity_id": "loc-1",
		"evidence_ref": {"source_kind": "scene", "source_id": "loc-1", "tick": 4, "owner_id": null},
		"evidence_tick": 4,
	}]
	var local_culture := _overlay_state(local_payload, "culture")
	var local_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"culture": local_culture},
		_cursor(),
		_centers(),
	)
	var local_row := _one(_rows(local_plan, "culture"))
	if local_row.get("point", null) != Vector2(100, 100):
		return "location culture anchor missing"
	if not str(local_row.get("label", "")).contains("50"):
		return "culture proportion missing"
	var local_draw: Dictionary = Plan.draw_plan(local_plan, "full")
	var culture_glyphs := 0
	for glyph in local_draw.get("glyphs", []):
		if str(glyph.get("kind", "")) == "culture":
			culture_glyphs += 1
	if culture_glyphs != 1:
		return "culture hatch badge missing"
	var distinct_payload := local_payload.duplicate(true)
	var second_row: Dictionary = distinct_payload["rows"][0].duplicate(true)
	second_row["context"]["row_id"] = "culture:cultural_features:repr-2"
	second_row["context"]["source_refs"][0]["source_id"] = "trait-2"
	second_row["trait_id"] = "cultural_features:repr-2"
	second_row["representation_id"] = "repr-2"
	distinct_payload["rows"].append(second_row)
	var distinct_culture := _overlay_state(distinct_payload, "culture")
	var distinct_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"culture": distinct_culture},
		_cursor(),
		_centers(),
	)
	var distinct_rows: Array = _rows(distinct_plan, "culture")
	if distinct_rows.size() != 2:
		return "distinct culture traits were merged"
	if str(distinct_rows[0].get("identity", "")) == str(distinct_rows[1].get("identity", "")):
		return "distinct culture identities collided"
	if not str(distinct_rows[0].get("label", "") + distinct_rows[1].get("label", "")).contains("repr-2"):
		return "second culture trait label lost"
	var zero_payload := local_payload.duplicate(true)
	zero_payload["rows"][0]["carrier_count"] = 0
	zero_payload["rows"][0]["carrier_ids"] = []
	zero_payload["rows"][0]["eligible_owner_count"] = 0
	zero_payload["rows"][0]["proportion"] = null
	var zero_culture := _overlay_state(zero_payload, "culture")
	var zero_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"culture": zero_culture},
		_cursor(),
		_centers(),
	)
	var zero_row := _one(_rows(zero_plan, "culture"))
	if zero_row.get("proportion", null) != null:
		return "zero culture denominator became a proportion"
	if not str(zero_row.get("label", "")).contains("0/0"):
		return "zero culture denominator not shown"
	var partial_payload := local_payload.duplicate(true)
	partial_payload["rows"][0]["proportion"] = null
	partial_payload["rows"][0]["unavailable_owner_count"] = 1
	var partial_culture := _overlay_state(partial_payload, "culture")
	var partial_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"culture": partial_culture},
		_cursor(),
		_centers(),
	)
	var partial_row := _one(_rows(partial_plan, "culture"))
	if not str(partial_row.get("label", "")).contains("unknown owners 1"):
		return "partial culture denominator hidden"
	var technology := _overlay_state(_load("overlay_technology.json"), "technology")
	var technology_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"technology": technology},
		_cursor(),
		_centers(),
	)
	if not bool(technology_plan.get("ok", false)):
		return "technology plan rejected"
	var technology_row := _one(_rows(technology_plan, "technology"))
	if technology_row.get("point", null) != Vector2(100, 100):
		return "technology holder anchor missing"
	if not technology_row.get("points", []).is_empty():
		return "unknown technology source gained an arrow"
	if bool(technology_row.get("has_diffusion_edge", false)):
		return "unknown source marked as diffusion edge"
	var technology_draw: Dictionary = Plan.draw_plan(technology_plan, "full")
	if _link_count(technology_draw, "knowledge_diffusion") != 0:
		return "unknown technology source drew an arrow"
	var attributable_payload := _technology_payload("attributable", "teaching", "agent-b", "knowledge-0")
	var attributable := _overlay_state(attributable_payload, "technology")
	var attributable_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"technology": attributable},
		_cursor(),
		_centers(),
	)
	var attributable_row := _one(_rows(attributable_plan, "technology"))
	if attributable_row.get("points", []).size() != 2:
		return "attributable technology edge missing"
	if str(attributable_row.get("link_style", "")) != "teaching_dashed":
		return "teaching modality style missing"
	var attributable_draw: Dictionary = Plan.draw_plan(attributable_plan, "full")
	if _link_count(attributable_draw, "knowledge_diffusion") != 1:
		return "attributable knowledge arrow missing"
	var rediscovery_payload := _technology_payload("rediscovery", "practice", null, null)
	var rediscovery := _overlay_state(rediscovery_payload, "technology")
	var rediscovery_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"technology": rediscovery},
		_cursor(),
		_centers(),
	)
	var rediscovery_row := _one(_rows(rediscovery_plan, "technology"))
	if not rediscovery_row.get("points", []).is_empty():
		return "rediscovery gained an arrow"
	if not str(rediscovery_row.get("label", "")).contains("rediscovery"):
		return "rediscovery badge missing"
	var future := Civ.RowModel.new()
	future.kind = "technology"
	future.context = Civ.RowContextModel.new()
	future.context.row_id = "technology:agent-a:knowledge-future"
	future.history = Civ.LayerContextModel.new()
	future.history.boundary_tick = 4
	future.knowledge_id = "knowledge-future"
	future.holder_id = "agent-a"
	future.status = "held"
	future.acquisition_boundary = 5
	future.attribution = "attributable"
	future.modality = "teaching"
	future.source_owner_id = "agent-b"
	future.source_knowledge_id = "knowledge-0"
	var future_state := {
		"status": "available",
		"layer": "technology",
		"evidence_class": "ANALYTICAL_INFERRED",
		"cursor": _cursor(),
		"rows": [future],
		"coverage": null,
	}
	var future_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"technology": future_state},
		_cursor(),
		_centers(),
	)
	if not _rows(future_plan, "technology").is_empty():
		return "future acquisition edge leaked into the plan"
	var combined_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"migration": migration, "trade": trade, "culture": local_culture},
		_cursor(),
		_centers(),
	)
	var combined_draw: Dictionary = Plan.draw_plan(combined_plan, "full")
	if _link_count(combined_draw, "knowledge_diffusion") != 0:
		return "speech-only flows drew a knowledge arrow"
	return ""


func _technology_payload(attribution: String, modality: String, source_owner: Variant, source_knowledge: Variant) -> Dictionary:
	var payload: Dictionary = _load("overlay_technology.json")
	payload["rows"][0]["attribution"] = attribution
	payload["rows"][0]["modality"] = modality
	payload["rows"][0]["source_owner_id"] = source_owner
	payload["rows"][0]["source_knowledge_id"] = source_knowledge
	return payload


func _flow_caps() -> String:
	var rows: Array = []
	for index in 401:
		rows.append({
			"kind": "migration",
			"row_id": "migration:%03d" % index,
			"identity": "migration:%03d" % index,
			"layer": "migration",
			"evidence_class": "OBJECTIVE",
			"label": "preparing",
			"point": Vector2(100, 100),
			"points": [Vector2(100, 100), Vector2(300, 100)],
			"link_style": "intention_dashed",
			"click": {},
		})
	var draw: Dictionary = Plan.draw_plan({"ok": true, "cursor": _cursor(), "rows": rows}, "full")
	if _link_count(draw, "journey_intention") != 400:
		return "flow segment cap not enforced"
	if int(draw.get("suppressed", {}).get("links", 0)) != 1:
		return "suppressed flow count missing"
	if not bool(draw.get("display_truncated", false)):
		return "flow truncation not disclosed"
	return ""


func _link_count(draw: Dictionary, kind: String) -> int:
	var count := 0
	for link in draw.get("links", []):
		if str(link.get("kind", "")) == kind:
			count += 1
	return count


func _one(rows: Array) -> Dictionary:
	return rows[0] if not rows.is_empty() else {}


func _beliefs() -> String:
	var analytical := _overlay_state(_load("overlay_social_groups.json"), "social_groups")
	var analytical_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"social_groups": analytical},
		_cursor(),
		_centers(),
	)
	var analytical_row := _one(_rows(analytical_plan, "social_groups"))
	if str(analytical_row.get("evidence_class", "")) != "ANALYTICAL":
		return "inferred community promoted to objective"
	if str(analytical_row.get("style", "")) != "inferred_community":
		return "inferred community style missing"
	if not str(analytical_row.get("label", "")).contains("missing interaction,trust"):
		return "missing lanes not disclosed"
	if str(analytical_row.get("label", "")).to_lower().contains("nation"):
		return "inferred community called a nation"
	if analytical_row.get("points", []).size() != 2:
		return "analytical member halos missing"
	var owner_a := _overlay_state(_subjective_group_payload("agent-a", "local-1", ["agent-a"]), "social_groups", 4, 4)
	var owner_b := _overlay_state(_subjective_group_payload("agent-b", "local-1", ["agent-b"]), "social_groups", 4, 4)
	var plan_a: Dictionary = Plan.build_semantic(_world(), {"social_groups": owner_a}, _cursor(), _centers())
	var plan_b: Dictionary = Plan.build_semantic(_world(), {"social_groups": owner_b}, _cursor(), _centers())
	var row_a := _one(_rows(plan_a, "social_groups"))
	var row_b := _one(_rows(plan_b, "social_groups"))
	if str(row_a.get("evidence_class", "")) != "SUBJECTIVE":
		return "owner group is not subjective"
	if row_a.get("point", null) != Vector2(100, 100):
		return "owner-a membership not resolved"
	if row_b.get("point", null) != Vector2(300, 100):
		return "owner-b membership not resolved"
	if str(row_a.get("identity", "")) == str(row_b.get("identity", "")):
		return "two owners merged the same local group identity"
	if str(row_a.get("color_key", "")) == str(row_b.get("color_key", "")):
		return "owner group colors collapsed to one key"
	var mismatch_state := {
		"status": "available",
		"layer": "social_groups",
		"evidence_class": "SUBJECTIVE_TO_SELECTED_AGENT",
		"owner_id": "agent-a",
		"cursor": _cursor(),
		"rows": [_fake_owner_group("agent-b")],
		"coverage": null,
	}
	var mismatch_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"social_groups": mismatch_state},
		_cursor(),
		_centers(),
	)
	if not _rows(mismatch_plan, "social_groups").is_empty():
		return "other owner's private group was accepted"
	var institution := _overlay_state(_load("overlay_institutions.json"), "institutions")
	var unplaced_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"institutions": institution},
		_cursor(),
		_centers(),
	)
	var unplaced_row := _one(_rows(unplaced_plan, "institutions"))
	if str(unplaced_row.get("evidence_class", "")) != "SUBJECTIVE":
		return "concept institution is not subjective"
	if str(unplaced_row.get("placement", "")) != "unplaced":
		return "witnessless institution gained an owner location"
	if str(unplaced_row.get("unplaced_reason", "")) != "nonspatial":
		return "witnessless institution is not nonspatial"
	if int(unplaced_row.get("click", {}).get("summary", {}).get("site_count", -1)) != 0:
		return "witnessless institution claims a site"
	if unplaced_row.get("click", {}).get("lineage_refs", []).size() != 0:
		return "ordinary concept source manufactured a lineage target"
	var one_site_payload := _institution_payload("concept", "recognized", [{
		"kind": "project",
		"location_id": "loc-1",
		"entity_id": "project-1",
		"evidence_ref": {"source_kind": "project", "source_id": "project-1", "tick": 3, "owner_id": "agent-a"},
		"evidence_tick": 3,
	}])
	var one_state := _overlay_state(one_site_payload, "institutions")
	var one_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"institutions": one_state, "projects": _map_state("projects")},
		_cursor(),
		_centers(),
	)
	var one_row := _one(_rows(one_plan, "institutions"))
	if one_row.get("site_points", []).size() != 1:
		return "grounded institution site missing"
	if one_row.get("point", null) != Vector2(100, 100):
		return "grounded institution anchor moved"
	if bool(one_row.get("historical_evidence", true)):
		return "present project marked historical"
	if not str(one_row.get("label", "")).contains("institution evidence at this site"):
		return "grounded institution label missing"
	var two_payload := _institution_payload("concept", "recognized", [
		{
			"kind": "project",
			"location_id": "loc-1",
			"entity_id": "project-1",
			"evidence_ref": {"source_kind": "project", "source_id": "project-1", "tick": 3, "owner_id": "agent-a"},
			"evidence_tick": 3,
		},
		{
			"kind": "repository",
			"location_id": "loc-2",
			"entity_id": "repo-0000",
			"evidence_ref": {"source_kind": "repository", "source_id": "repo-0000", "tick": 3, "owner_id": "agent-a"},
			"evidence_tick": 3,
		},
	])
	var repo_payload: Dictionary = _load("map_repositories.json")
	repo_payload["rows"][0]["location_id"] = "loc-2"
	repo_payload["rows"][0]["status"] = "destroyed"
	repo_payload["rows"][0]["context"]["anchors"][0]["location_id"] = "loc-2"
	var two_state := _overlay_state(two_payload, "institutions")
	var two_plan: Dictionary = Plan.build_semantic(
		_world(),
		{
			"institutions": two_state,
			"projects": _map_state("projects"),
			"repositories": _map_state_from_payload(repo_payload, "repositories"),
		},
		_cursor(),
		_centers(),
	)
	var two_row := _one(_rows(two_plan, "institutions"))
	if two_row.get("site_points", []).size() != 2:
		return "multiple institution sites were collapsed"
	if not bool(two_row.get("historical_evidence", false)):
		return "destroyed source did not mark historical evidence"
	if str(two_row.get("status", "")) != "recognized":
		return "destroyed source collapsed the institution"
	if not str(two_row.get("label", "")).contains("historical t="):
		return "historical evidence badge missing"
	var episode_payload := _institution_payload("episode", "stable", [])
	episode_payload["scope"]["evidence_class"] = "ANALYTICAL"
	episode_payload["scope"]["owner_id"] = null
	episode_payload["rows"][0]["history"]["scope"]["evidence_class"] = "ANALYTICAL"
	episode_payload["rows"][0]["history"]["scope"]["owner_id"] = null
	episode_payload["rows"][0]["native_owner_id"] = "agent-a"
	episode_payload["rows"][0]["context"]["row_id"] = "institution:episode:episode-1"
	episode_payload["rows"][0]["context"]["source_refs"][0] = {
		"source_kind": "institution_episode",
		"source_id": "episode-1",
		"tick": 3,
		"owner_id": null,
	}
	var episode_state := _overlay_state(episode_payload, "institutions")
	var episode_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"institutions": episode_state},
		_cursor(),
		_centers(),
	)
	var episode_row := _one(_rows(episode_plan, "institutions"))
	if str(episode_row.get("evidence_class", "")) != "ANALYTICAL":
		return "inferred episode is not analytical"
	if str(episode_row.get("evidence_class", "")) == "OBJECTIVE":
		return "inferred episode promoted to objective"
	var contested_payload := _institution_payload("office", "contested", [])
	var contested_state := _overlay_state(contested_payload, "institutions")
	var contested_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"institutions": contested_state},
		_cursor(),
		_centers(),
	)
	var contested_row := _one(_rows(contested_plan, "institutions"))
	if str(contested_row.get("style", "")) != "contested":
		return "contested office style missing"
	if contested_row.get("click", {}).get("summary", {}).has("current_occupant"):
		return "contested office invented a current occupant"
	var gap_payload := _institution_payload("concept", "recognized", [])
	gap_payload["coverage"]["state"] = "partial"
	gap_payload["coverage"]["reason"] = "capture_gap"
	gap_payload["coverage"]["missing_intervals"] = [{"start_tick": 2, "end_tick": 3}]
	var gap_state := _overlay_state(gap_payload, "institutions")
	var gap_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"institutions": gap_state},
		_cursor(),
		_centers(),
	)
	var gap_row := _one(_rows(gap_plan, "institutions"))
	if str(gap_row.get("style", "")) != "gap":
		return "missing institution evidence rendered as confirmed"
	var collapsed_payload := _institution_payload("concept", "collapsed", [])
	var collapsed_state := _overlay_state(collapsed_payload, "institutions")
	var collapsed_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"institutions": collapsed_state},
		_cursor(),
		_centers(),
	)
	var collapsed_row := _one(_rows(collapsed_plan, "institutions"))
	if str(collapsed_row.get("style", "")) != "collapsed":
		return "confirmed institution collapse style missing"
	var lineage_payload := _institution_payload("concept", "recognized", [])
	lineage_payload["rows"][0]["context"]["source_refs"].append({
		"source_kind": "lineage",
		"source_id": "lineage-ref-1",
		"tick": 3,
		"owner_id": "agent-a",
	})
	var lineage_state := _overlay_state(lineage_payload, "institutions")
	var lineage_plan: Dictionary = Plan.build_semantic(
		_world(),
		{"institutions": lineage_state},
		_cursor(),
		_centers(),
	)
	var lineage_row := _one(_rows(lineage_plan, "institutions"))
	if lineage_row.get("click", {}).get("lineage_refs", []).size() != 1:
		return "qualified lineage source ref was dropped"
	if lineage_row.get("click", {}).has("lineage_target"):
		return "lineage target was guessed from a source ref"
	return ""


func _subjective_group_payload(owner_id: String, group_id: String, members: Array) -> Dictionary:
	var payload: Dictionary = _load("overlay_social_groups.json")
	payload["scope"]["evidence_class"] = "SUBJECTIVE"
	payload["scope"]["owner_id"] = owner_id
	payload["rows"][0]["history"]["scope"]["evidence_class"] = "SUBJECTIVE"
	payload["rows"][0]["history"]["scope"]["owner_id"] = owner_id
	payload["rows"][0]["context"]["source_refs"] = [{
		"source_kind": "group",
		"source_id": "belief-1",
		"tick": 4,
		"owner_id": owner_id,
	}]
	payload["rows"][0]["context"]["row_id"] = "group:%s:belief-1" % owner_id
	payload["rows"][0]["group_id"] = group_id
	payload["rows"][0]["basis"] = "owner_belief"
	payload["rows"][0]["member_ids"] = members
	payload["rows"][0]["member_count"] = members.size()
	payload["rows"][0]["missing_lanes"] = []
	return payload


func _fake_owner_group(owner_id: String) -> Variant:
	var row := Civ.RowModel.new()
	row.kind = "social_groups"
	row.context = Civ.RowContextModel.new()
	row.context.row_id = "group:%s:belief" % owner_id
	var ref := Civ.SourceRefModel.new()
	ref.source_kind = "group"
	ref.source_id = "belief"
	ref.tick = 4
	ref.owner_id = owner_id
	row.context.source_refs = [ref]
	row.history = Civ.LayerContextModel.new()
	row.history.scope = Civ.ScopeModel.new()
	row.history.scope.layer = "social_groups"
	row.history.scope.evidence_class = "SUBJECTIVE_TO_SELECTED_AGENT"
	row.history.scope.owner_id = owner_id
	row.history.boundary_tick = 4
	row.group_id = "local-1"
	row.basis = "owner_belief"
	row.member_count = 1
	row.member_ids = [owner_id]
	row.missing_lanes = []
	return row


func _institution_payload(kind: String, status: String, anchors: Array) -> Dictionary:
	var payload: Dictionary = _load("overlay_institutions.json")
	payload["rows"][0]["kind"] = kind
	payload["rows"][0]["status"] = status
	payload["rows"][0]["context"]["anchors"] = anchors
	if kind == "office":
		payload["rows"][0]["institution_id"] = "office-1"
		payload["rows"][0]["native_id"] = "office-1"
		payload["rows"][0]["context"]["row_id"] = "institution:office:agent-a:office-1"
		payload["rows"][0]["context"]["source_refs"][0]["source_kind"] = "office"
		payload["rows"][0]["context"]["source_refs"][0]["source_id"] = "office-1"
	return payload


func _map_state_from_payload(payload: Dictionary, section: String) -> Dictionary:
	var parsed: Dictionary = Civ.parse_map(payload)
	var model = parsed["value"]
	return {
		"status": "available",
		"layer": section,
		"evidence_class": model.scope.evidence_class,
		"owner_id": model.scope.owner_id,
		"cursor": _cursor(),
		"rows": model.rows,
		"coverage": model.coverage,
		"truncated": model.truncated,
	}


func _rows(plan: Dictionary, kind: String) -> Array:
	var result: Array = []
	for row in plan.get("rows", []):
		if str(row.get("kind", "")) == kind:
			result.append(row)
	return result


func _row(plan: Dictionary, kind: String, identity: String) -> Dictionary:
	for row in plan.get("rows", []):
		if str(row.get("kind", "")) != kind:
			continue
		if str(row.get("identity", "")) == identity:
			return row
	return {}
