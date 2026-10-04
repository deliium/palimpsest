extends RefCounted

const Bookmarks := preload("res://scripts/protocol/bookmarks.gd")
const Log := preload("res://scripts/log.gd")


func run() -> Array:
	var failures: Array = []
	var stem := Bookmarks.safe_stem("Run/With Spaces!@#")
	if "/" in stem or " " in stem or "!" in stem:
		failures.append("safe_stem should sanitize filesystem chars")
	if not stem.contains("-"):
		failures.append("safe_stem should include hash suffix")
	var run_id := "test-bookmarks-%s" % Time.get_ticks_msec()
	var path := Bookmarks.path_for(run_id)
	if FileAccess.file_exists(path):
		DirAccess.remove_absolute(path)
	var items := Bookmarks.add(run_id, 1832, 1, "strange attack")
	if items.size() != 1 or int(items[0].get("tick", -1)) != 1832:
		failures.append("bookmark add should persist tick")
	var reloaded := Bookmarks.load_for(run_id)
	if reloaded.size() != 1:
		failures.append("bookmark reload failed")
	items = Bookmarks.update_note(run_id, 0, "updated")
	if str(items[0].get("note", "")) != "updated":
		failures.append("bookmark edit note failed")
	items = Bookmarks.remove_at(run_id, 0)
	if not items.is_empty():
		failures.append("bookmark delete failed")
	if "note_len=" not in "\n".join(Log.recent):
		failures.append("bookmark add should log note_len only")
	if FileAccess.file_exists(path):
		DirAccess.remove_absolute(path)
	return failures
