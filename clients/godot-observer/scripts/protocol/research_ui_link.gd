extends RefCounted
class_name ResearchUiLink

## Credential-free Research UI URL builders (outbound Godot → /research/).
## Task 15 wires OS.shell_open / JavaScriptBridge; this module is the stub.

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
