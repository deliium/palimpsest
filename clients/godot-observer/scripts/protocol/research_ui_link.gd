extends RefCounted
class_name ResearchUiLink

## Credential-free Research UI URL builders + outbound open (Godot → /research/).

const BASE_PATH := "/research/"
const VIEWS := {
	"overview": true,
	"graphs": true,
	"agent": true,
	"analytics": true,
	"traces": true,
	"compare": true,
	"matrix": true,
	"population": true,
	"cohorts": true,
	"lineage": true,
	"teaching": true,
	"technology": true,
	"culture": true,
	"language": true,
	"narratives": true,
	"migration": true,
	"economy": true,
	"projects": true,
	"societies": true,
	"institutions": true,
	"contact": true,
}


static func build_query(
	run_id: String = "",
	tick: Variant = null,
	event_id: String = "",
	sequence: Variant = null,
	agent_id: String = "",
	view: String = "overview",
	options: Dictionary = {},
) -> String:
	var parts: PackedStringArray = []
	if not run_id.is_empty():
		parts.append("run_id=%s" % run_id.uri_encode())
	if tick != null:
		parts.append("tick=%s" % str(int(tick)))
	if not event_id.is_empty():
		parts.append("event_id=%s" % event_id.uri_encode())
	if sequence != null:
		parts.append("sequence=%s" % str(int(sequence)))
	if not agent_id.is_empty():
		parts.append("agent_id=%s" % agent_id.uri_encode())
	for key in [
		"generation_index", "cohort_generation_index", "cohort_entry_tick",
		"cohort_id", "location_id", "institution_id", "narrative_id",
		"technology_id", "owner_id", "identity_owner", "evidence_class",
		"entity_source", "native_kind", "lineage_family", "lineage_node_key",
		"lineage_publication_id", "civilization_row_id",
		"civilization_publication_id",
	]:
		if options.has(key):
			var raw: Variant = options[key]
			if raw == null:
				continue
			var text := str(raw).strip_edges()
			if text.is_empty():
				continue
			parts.append("%s=%s" % [key, text.uri_encode()])
	var resolved_view := view.strip_edges().to_lower()
	if not VIEWS.has(resolved_view):
		resolved_view = "overview"
	if resolved_view != "overview":
		parts.append("view=%s" % resolved_view.uri_encode())
	if parts.is_empty():
		return ""
	return "?" + "&".join(parts)


static func build_path(
	run_id: String = "",
	tick: Variant = null,
	event_id: String = "",
	sequence: Variant = null,
	agent_id: String = "",
	view: String = "overview",
	options: Dictionary = {},
) -> String:
	return BASE_PATH + build_query(run_id, tick, event_id, sequence, agent_id, view, options)


static func build_absolute_url(
	run_id: String = "",
	tick: Variant = null,
	event_id: String = "",
	sequence: Variant = null,
	agent_id: String = "",
	view: String = "overview",
	options: Dictionary = {},
) -> String:
	var path := build_path(run_id, tick, event_id, sequence, agent_id, view, options)
	var origin := ObserverOrigin.resolve()
	if origin.is_empty():
		return path
	return origin.rstrip("/") + path


static func open(
	run_id: String = "",
	tick: Variant = null,
	event_id: String = "",
	sequence: Variant = null,
	agent_id: String = "",
	view: String = "overview",
	options: Dictionary = {},
) -> void:
	var url := build_absolute_url(run_id, tick, event_id, sequence, agent_id, view, options)
	if url.is_empty():
		return
	if OS.has_feature("web"):
		var js := "window.open(%s, '_blank', 'noopener,noreferrer')" % JSON.stringify(url)
		JavaScriptBridge.eval(js, true)
	else:
		OS.shell_open(url)
	ObserverLog.info(
		"research_ui_link",
		"research_ui_link_opened view=%s run_id=%s" % [view, run_id],
	)
