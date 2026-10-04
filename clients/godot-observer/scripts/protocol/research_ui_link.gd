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
}


static func build_query(
	run_id: String = "",
	tick: Variant = null,
	event_id: String = "",
	sequence: Variant = null,
	agent_id: String = "",
	view: String = "overview",
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
) -> String:
	return BASE_PATH + build_query(run_id, tick, event_id, sequence, agent_id, view)


static func build_absolute_url(
	run_id: String = "",
	tick: Variant = null,
	event_id: String = "",
	sequence: Variant = null,
	agent_id: String = "",
	view: String = "overview",
) -> String:
	var path := build_path(run_id, tick, event_id, sequence, agent_id, view)
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
) -> void:
	var url := build_absolute_url(run_id, tick, event_id, sequence, agent_id, view)
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
