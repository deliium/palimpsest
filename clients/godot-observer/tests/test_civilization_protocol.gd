extends RefCounted

const Civ := preload("res://scripts/protocol/civilization.gd")
const Evidence := preload("res://scripts/presentation/evidence_class.gd")
const BASE := "res://fixtures/protocol/civilization/"


func run() -> Array:
	var failures: Array = []
	_expect(failures, _map(), "map")
	_expect(failures, _catalogue(), "catalogue")
	_expect(failures, _overlays(), "overlays")
	_expect(failures, _markers(), "markers")
	_expect(failures, _malformed(), "malformed")
	return failures


func _load(name: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(BASE + name))


func _map() -> String:
	var payload: Dictionary = _load("map_locations.json")
	var parsed: Dictionary = Civ.parse_map(payload)
	if not bool(parsed.get("ok", false)):
		return "map failed: %s" % parsed.get("reason_code", "")
	var model = parsed["value"]
	if model.section != "locations" or model.rows.size() != 2:
		return "map rows missing"
	if model.scope.evidence_class != Evidence.OBJECTIVE or model.scope.owner_id != null:
		return "map scope not objective"
	if model.rows[0].kind != "locations" or model.rows[0].location_id.is_empty():
		return "map row kind/location missing"
	if model.resolved_cursor.boundary_tick != 4:
		return "map boundary missing"
	for section in ["locations", "repositories", "regions", "routes", "projects", "records"]:
		var extra: Dictionary = Civ.parse_map(_load("map_%s.json" % section))
		if not bool(extra.get("ok", false)):
			return "map %s failed: %s" % [section, extra.get("reason_code", "")]
		if extra["value"].rows.is_empty() or extra["value"].rows[0].kind != section:
			return "map %s row kind missing" % section
	var negative: Dictionary = payload.duplicate(true)
	negative["rows"][0]["living_body_count"] = -1
	if bool(Civ.parse_map(negative).get("ok", false)):
		return "negative living count accepted"
	var future: Dictionary = payload.duplicate(true)
	future["rows"][0]["context"]["source_refs"][0]["tick"] = 5
	if bool(Civ.parse_map(future).get("ok", false)):
		return "future map source accepted"
	var wrong_revision: Dictionary = payload.duplicate(true)
	wrong_revision["source_revision"] = 3
	if bool(Civ.parse_map(wrong_revision).get("ok", false)):
		return "map revision mismatch accepted"
	return ""


func _catalogue() -> String:
	var payload: Dictionary = _load("catalogue.json")
	var parsed: Dictionary = Civ.parse_catalogue(payload)
	if not bool(parsed.get("ok", false)):
		return "catalogue failed: %s" % parsed.get("reason_code", "")
	var model = parsed["value"]
	if model.availability != "available" or model.boundaries.is_empty():
		return "catalogue availability/boundaries missing"
	if "settlements" not in model.boundaries[0].layers:
		return "catalogue layer missing"
	var unknown_layer: Dictionary = payload.duplicate(true)
	unknown_layer["boundaries"][0]["layers"] = ["unknown"]
	if bool(Civ.parse_catalogue(unknown_layer).get("ok", false)):
		return "unknown catalogue layer accepted"
	var bad_page: Dictionary = payload.duplicate(true)
	bad_page["next_cursor"] = "cursor"
	if bool(Civ.parse_catalogue(bad_page).get("ok", false)):
		return "truncation mismatch accepted"
	var bad_scope: Dictionary = payload.duplicate(true)
	bad_scope["scope"]["owner_id"] = "agent-a"
	if bool(Civ.parse_catalogue(bad_scope).get("ok", false)):
		return "analytical owner accepted"
	return ""


func _overlays() -> String:
	var settlements: Dictionary = Civ.parse_overlay(_load("overlay_settlements.json"))
	if not bool(settlements.get("ok", false)):
		return "settlements overlay failed: %s" % settlements.get("reason_code", "")
	var model = settlements["value"]
	if model.rows.size() != 2 or model.rows[0].kind != "settlements":
		return "settlement rows missing"
	if model.rows[0].history.scope.layer != "settlements":
		return "row history scope missing"
	if model.resolved_cursor.boundary_tick != model.requested_tick:
		return "overlay exact boundary missing"
	var institutions: Dictionary = Civ.parse_overlay(_load("overlay_institutions.json"))
	if not bool(institutions.get("ok", false)):
		return "institutions overlay failed: %s" % institutions.get("reason_code", "")
	if institutions["value"].scope.evidence_class != Evidence.SUBJECTIVE:
		return "subjective scope mapping missing"
	var unavailable: Dictionary = Civ.parse_overlay(_load("overlay_unavailable.json"))
	if not bool(unavailable.get("ok", false)):
		return "unavailable overlay failed"
	if unavailable["value"].availability != "unavailable" or unavailable["value"].rows.size() != 0:
		return "unavailable overlay rows/status"
	for layer in ["migration", "trade", "culture", "technology", "social_groups"]:
		var extra: Dictionary = Civ.parse_overlay(_load("overlay_%s.json" % layer))
		if not bool(extra.get("ok", false)):
			return "overlay %s failed: %s" % [layer, extra.get("reason_code", "")]
		if extra["value"].rows.is_empty() or extra["value"].rows[0].kind != layer:
			return "overlay %s row kind missing" % layer
	var payload: Dictionary = _load("overlay_settlements.json")
	var owner: Dictionary = payload.duplicate(true)
	owner["scope"]["owner_id"] = "agent-a"
	if bool(Civ.parse_overlay(owner).get("ok", false)):
		return "analytical owner accepted"
	var status: Dictionary = payload.duplicate(true)
	status["rows"][0]["status"] = "invented"
	if bool(Civ.parse_overlay(status).get("ok", false)):
		return "unknown settlement status accepted"
	var boundary: Dictionary = payload.duplicate(true)
	boundary["resolved_cursor"]["boundary_tick"] = 5
	if bool(Civ.parse_overlay(boundary).get("ok", false)):
		return "resolved boundary mismatch accepted"
	var coverage: Dictionary = payload.duplicate(true)
	coverage["coverage"]["reason"] = "capture_gap"
	if bool(Civ.parse_overlay(coverage).get("ok", false)):
		return "complete coverage with reason accepted"
	var anchored_payload: Dictionary = _load("overlay_culture.json")
	anchored_payload["rows"][0]["context"]["anchors"] = [{
		"kind": "location",
		"location_id": "loc-1",
		"entity_id": null,
		"evidence_ref": {"source_kind": "scene", "source_id": "loc-1", "tick": 4, "owner_id": null},
		"evidence_tick": 4,
	}]
	var anchored: Dictionary = Civ.parse_overlay(anchored_payload)
	if not bool(anchored.get("ok", false)):
		return "typed anchor rejected"
	if anchored["value"].rows[0].context.anchors[0].location_id != "loc-1":
		return "typed anchor missing"
	anchored_payload["rows"][0]["context"]["anchors"][0]["evidence_tick"] = 5
	if bool(Civ.parse_overlay(anchored_payload).get("ok", false)):
		return "future anchor evidence accepted"
	return ""


func _markers() -> String:
	var parsed: Dictionary = Civ.parse_markers(_load("markers_positive.json"))
	if not bool(parsed.get("ok", false)):
		return "markers failed: %s" % parsed.get("reason_code", "")
	var model = parsed["value"]
	if model.markers.size() != 2 or model.next_cursor == null:
		return "marker page/continuation missing"
	if model.markers[0].seek_boundary != 4 or model.markers[0].layer != "technology":
		return "marker boundary/layer missing"
	if model.missing_intervals.size() != 1:
		return "missing interval band missing"
	var page2: Dictionary = Civ.parse_markers(_load("markers_positive_page2.json"))
	if not bool(page2.get("ok", false)) or page2["value"].markers.size() != 2:
		return "second marker page failed"
	var payload: Dictionary = _load("markers_positive.json")
	var bad_owner: Dictionary = payload.duplicate(true)
	bad_owner["markers"][0]["owner_id"] = null
	if bool(Civ.parse_markers(bad_owner).get("ok", false)):
		return "subjective marker without owner accepted"
	var future: Dictionary = payload.duplicate(true)
	future["markers"][0]["source_refs"][0]["tick"] = 4
	if bool(Civ.parse_markers(future).get("ok", false)):
		return "future marker evidence accepted"
	var outside: Dictionary = payload.duplicate(true)
	outside["markers"][0]["seek_boundary"] = 6
	if bool(Civ.parse_markers(outside).get("ok", false)):
		return "marker outside window accepted"
	var band: Dictionary = payload.duplicate(true)
	band["missing_intervals"][0]["end_tick"] = 7
	if bool(Civ.parse_markers(band).get("ok", false)):
		return "missing band outside window accepted"
	return ""


func _malformed() -> String:
	if bool(Civ.parse_map({"schema_version": "observer-civilization-map-v2"}).get("ok", false)):
		return "foreign map schema accepted"
	var overlay: Dictionary = Civ.parse_overlay({"schema_version": Civ.OVERLAY_SCHEMA})
	if bool(overlay.get("ok", false)) or str(overlay.get("reason_code", "")) != "civilization_invalid":
		return "empty overlay accepted"
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])
