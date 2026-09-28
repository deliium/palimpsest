extends RefCounted
class_name ObserverOrigin


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
	var text := search.strip_edges()
	if text.begins_with("?"):
		text = text.substr(1)
	if text.is_empty():
		return ""
	for part in text.split("&", false):
		var pair := part.split("=", true, 1)
		if pair.is_empty():
			continue
		var key := str(pair[0]).uri_decode()
		if key != "run_id":
			continue
		if pair.size() < 2:
			return ""
		return str(pair[1]).uri_decode().strip_edges()
	return ""


static func is_missing(origin: String) -> bool:
	return origin.strip_edges().is_empty()
