extends RefCounted
class_name ObserverOrigin

const _MAX_SAFE_INT := 9007199254740991


static func resolve() -> String:
	if OS.has_feature("web"):
		return page_origin()
	var configured: Variant = ProjectSettings.get_setting("palimpsest/observer_origin", "")
	if configured == null:
		return ""
	return str(configured).strip_edges()


static func page_origin() -> String:
	if not OS.has_feature("web"):
		return ""
	var raw: Variant = JavaScriptBridge.eval("window.location.origin", true)
	if raw == null:
		return ""
	return str(raw).strip_edges()


static func web_search() -> String:
	if not OS.has_feature("web"):
		return ""
	var raw: Variant = JavaScriptBridge.eval("window.location.search", true)
	if raw == null:
		return ""
	return str(raw)


static func web_run_id(search: String) -> String:
	var state := web_debugger_state(search)
	return str(state.get("run_id", ""))


static func _canonical_nonneg_int(value: String) -> Variant:
	var text := value.strip_edges()
	if text.is_empty():
		return null
	if text != "0" and (text.begins_with("0") or text.begins_with("-")):
		return null
	if not text.is_valid_int():
		return null
	var parsed := int(text)
	if parsed < 0 or parsed > _MAX_SAFE_INT:
		return null
	return parsed


static func _stable_id(value: String) -> bool:
	var text := value.strip_edges()
	if text.is_empty() or text.length() > 128:
		return false
	return text == value


static func web_debugger_state(search: String) -> Dictionary:
	## Parse credential-free deep-link params. UI event N = sequence.
	var text := search.strip_edges()
	if text.begins_with("?"):
		text = text.substr(1)
	var out := {
		"run_id": "",
		"layout_id": "",
		"civilization_layers": "",
		"civilization_detail": "",
		"civilization_seek_cycles": "",
		"tick": null,
		"sequence": null,
		"event_id": "",
		"agent_id": "",
		"location_id": "",
		"institution_id": "",
		"narrative_id": "",
		"technology_id": "",
		"generation_index": null,
		"cohort_generation_index": null,
		"cohort_entry_tick": null,
		"cohort_id": "",
		"owner_id": "",
		"identity_owner": "",
		"evidence_class": "",
		"entity_source": "",
		"native_kind": "",
		"lineage_family": "",
		"lineage_node_key": "",
		"lineage_publication_id": "",
		"civilization_row_id": "",
		"civilization_publication_id": "",
		"open_debugger": false,
		"reason_code": "",
	}
	if text.is_empty():
		return out
	var secret_keys := {
		"token": true,
		"credential": true,
		"credentials": true,
		"secret": true,
		"api_key": true,
		"apikey": true,
		"authorization": true,
		"password": true,
		"access_token": true,
	}
	var known := {
		"run_id": true, "layout_id": true, "civilization_layers": true,
		"civilization_detail": true, "civilization_seek_cycles": true,
		"tick": true, "sequence": true, "event_id": true, "event": true,
		"agent_id": true, "agent": true, "debugger": true,
		"location_id": true, "institution_id": true, "narrative_id": true,
		"technology_id": true, "generation_index": true,
		"cohort_generation_index": true, "cohort_entry_tick": true,
		"cohort_id": true, "owner_id": true, "identity_owner": true,
		"evidence_class": true, "entity_source": true, "native_kind": true,
		"lineage_family": true, "lineage_node_key": true,
		"lineage_publication_id": true, "civilization_row_id": true,
		"civilization_publication_id": true,
	}
	var raw := {}
	var counts := {}
	for part in text.split("&", false):
		var pair := part.split("=", true, 1)
		if pair.is_empty():
			continue
		var key := str(pair[0]).uri_decode()
		var lowered := key.to_lower()
		if secret_keys.has(lowered):
			out["reason_code"] = "query_string_secret"
			return out
		if counts.has(lowered) and known.has(lowered):
			out["reason_code"] = "duplicate_query_key"
			return out
		counts[lowered] = int(counts.get(lowered, 0)) + 1
		var value := ""
		if pair.size() >= 2:
			value = str(pair[1]).uri_decode().strip_edges()
		raw[key] = value
	for key in raw.keys():
		var value := str(raw[key])
		match key:
			"run_id":
				if not _stable_id(value):
					out["reason_code"] = "invalid_run_id"
					return out
				out["run_id"] = value
			"layout_id":
				out["layout_id"] = value
			"civilization_layers":
				out["civilization_layers"] = value
			"civilization_detail":
				out["civilization_detail"] = value
			"civilization_seek_cycles":
				out["civilization_seek_cycles"] = value
			"tick", "sequence", "generation_index",
			"cohort_generation_index", "cohort_entry_tick":
				var parsed: Variant = _canonical_nonneg_int(value)
				if parsed == null and not value.is_empty():
					out["reason_code"] = "invalid_%s" % key
					return out
				out[key] = parsed
			"event_id", "event":
				if str(out["event_id"]).is_empty():
					out["event_id"] = value
			"agent_id", "agent":
				if str(out["agent_id"]).is_empty():
					out["agent_id"] = value
			"debugger":
				out["open_debugger"] = value.to_lower() in ["1", "true", "causal", "yes"]
			"location_id", "institution_id", "narrative_id", "technology_id",
			"cohort_id", "owner_id", "identity_owner", "evidence_class",
			"entity_source", "native_kind", "lineage_family",
			"lineage_node_key", "lineage_publication_id",
			"civilization_row_id", "civilization_publication_id":
				out[key] = value
	if out["tick"] == null and out["sequence"] != null:
		out["reason_code"] = "incomplete_event_cursor"
		return out
	var focus_keys: Array = []
	for key in ["agent_id", "location_id", "institution_id", "narrative_id", "technology_id"]:
		if str(out[key]) != "":
			focus_keys.append(key)
	if focus_keys.size() > 1:
		out["reason_code"] = "ambiguous_entity_focus"
		return out
	var cohort_parts := 0
	for key in ["cohort_generation_index", "cohort_entry_tick"]:
		if out[key] != null:
			cohort_parts += 1
	if str(out["cohort_id"]) != "":
		cohort_parts += 1
	if cohort_parts != 0 and cohort_parts != 3:
		out["reason_code"] = "incomplete_cohort_selection"
		return out
	var evidence := str(out["evidence_class"]).to_lower()
	if evidence != "" and not evidence in ["objective", "subjective", "analytical"]:
		out["reason_code"] = "invalid_evidence_class"
		return out
	out["evidence_class"] = evidence
	var source := str(out["entity_source"]).to_lower()
	if source != "" and not source in ["lineage", "civilization"]:
		out["reason_code"] = "invalid_entity_source"
		return out
	out["entity_source"] = source
	if not str(out["lineage_node_key"]).is_empty():
		var key_re := RegEx.new()
		key_re.compile("^[0-9a-f]{64}$")
		if key_re.search(str(out["lineage_node_key"])) == null:
			out["reason_code"] = "invalid_lineage_node_key"
			return out
	return out


static func is_missing(origin: String) -> bool:
	return origin.strip_edges().is_empty()
