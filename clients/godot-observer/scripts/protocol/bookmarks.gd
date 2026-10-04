extends RefCounted
class_name ObserverBookmarks

const ObserverLog := preload("res://scripts/log.gd")

## Local researcher bookmarks under user://observer_bookmarks/.
## Web/HTML5 may drop user:// in private/incognito sessions — not authoritative history.


static func safe_stem(run_id: String) -> String:
	var raw := run_id.strip_edges()
	var slug := ""
	for index in raw.length():
		var ch := raw.substr(index, 1)
		var code := ch.unicode_at(0)
		var ok := (
			(code >= 97 and code <= 122)
			or (code >= 65 and code <= 90)
			or (code >= 48 and code <= 57)
			or ch == "-"
			or ch == "_"
		)
		slug += ch.to_lower() if ok else "-"
	while slug.find("--") >= 0:
		slug = slug.replace("--", "-")
	slug = slug.strip_edges().trim_prefix("-").trim_suffix("-")
	if slug.is_empty():
		slug = "run"
	if slug.length() > 48:
		slug = slug.substr(0, 48)
	var digest := raw.md5_text().substr(0, 8)
	return "%s-%s" % [slug, digest]


static func path_for(run_id: String) -> String:
	return "user://observer_bookmarks/%s.json" % safe_stem(run_id)


static func load_for(run_id: String) -> Array:
	var path := path_for(run_id)
	if not FileAccess.file_exists(path):
		ObserverLog.debug("bookmarks", "load_empty run_id=%s" % run_id)
		return []
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		ObserverLog.warn("bookmarks", "load_failed reason_code=open_failed")
		return []
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		return []
	if str(parsed.get("run_id", "")) != run_id:
		ObserverLog.warn("bookmarks", "load_failed reason_code=run_id_mismatch")
		return []
	var items: Array = []
	var raw: Variant = parsed.get("bookmarks", [])
	if raw is Array:
		for item in raw:
			if typeof(item) != TYPE_DICTIONARY:
				continue
			items.append({
				"tick": int(item.get("tick", 0)),
				"sequence": item.get("sequence", null),
				"note": str(item.get("note", "")),
				"created_at_utc": str(item.get("created_at_utc", "")),
			})
	ObserverLog.debug("bookmarks", "load_ok count=%s" % items.size())
	return items


static func save_for(run_id: String, bookmarks: Array) -> bool:
	var dir := DirAccess.open("user://")
	if dir == null:
		ObserverLog.warn("bookmarks", "save_failed reason_code=user_fs_missing")
		return false
	if not dir.dir_exists("observer_bookmarks"):
		dir.make_dir("observer_bookmarks")
	var path := path_for(run_id)
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		ObserverLog.warn("bookmarks", "save_failed reason_code=open_failed")
		return false
	var payload := {
		"run_id": run_id,
		"bookmarks": bookmarks,
	}
	file.store_string(JSON.stringify(payload))
	ObserverLog.debug("bookmarks", "save_ok count=%s" % bookmarks.size())
	return true


static func add(run_id: String, tick: int, sequence: Variant, note: String) -> Array:
	var items := load_for(run_id)
	var entry := {
		"tick": tick,
		"sequence": sequence,
		"note": note,
		"created_at_utc": Time.get_datetime_string_from_system(true),
	}
	items.append(entry)
	save_for(run_id, items)
	ObserverLog.debug(
		"bookmarks",
		"add tick=%s sequence=%s note_len=%s" % [
			tick,
			str(sequence),
			note.length(),
		],
	)
	return items


static func update_note(run_id: String, index: int, note: String) -> Array:
	var items := load_for(run_id)
	if index < 0 or index >= items.size():
		return items
	items[index]["note"] = note
	save_for(run_id, items)
	ObserverLog.debug("bookmarks", "edit index=%s note_len=%s" % [index, note.length()])
	return items


static func remove_at(run_id: String, index: int) -> Array:
	var items := load_for(run_id)
	if index < 0 or index >= items.size():
		return items
	var removed: Dictionary = items[index]
	items.remove_at(index)
	save_for(run_id, items)
	ObserverLog.debug(
		"bookmarks",
		"delete tick=%s sequence=%s" % [
			int(removed.get("tick", 0)),
			str(removed.get("sequence", null)),
		],
	)
	return items
