extends RefCounted
class_name ObserverOrigin


static func resolve() -> String:
	if OS.has_feature("web"):
		var raw: Variant = JavaScriptBridge.eval("window.location.origin", true)
		if raw == null:
			return ""
		return str(raw).strip_edges()
	var configured: Variant = ProjectSettings.get_setting("palimpsest/observer_origin", "")
	if configured == null:
		return ""
	return str(configured).strip_edges()


static func is_missing(origin: String) -> bool:
	return origin.strip_edges().is_empty()
