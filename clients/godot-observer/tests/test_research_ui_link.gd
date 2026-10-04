extends RefCounted


func run() -> Array:
	var failures: Array = []
	var path := ResearchUiLink.build_path(
		"run-1",
		3,
		"evt-9",
		1,
		"alice",
		"traces",
	)
	if not path.begins_with("/research/?"):
		failures.append("path missing /research/ prefix")
	if "run_id=run-1" not in path:
		failures.append("run_id missing")
	if "tick=3" not in path:
		failures.append("tick missing")
	if "event_id=evt-9" not in path:
		failures.append("event_id missing")
	if "sequence=1" not in path:
		failures.append("sequence missing")
	if "agent_id=alice" not in path:
		failures.append("agent_id missing")
	if "view=traces" not in path:
		failures.append("view missing")

	var unknown := ResearchUiLink.build_path("run-2", null, "", null, "", "not-a-view")
	if "view=" in unknown:
		failures.append("unknown view should default without view= param")
	if "run_id=run-2" not in unknown:
		failures.append("run_id dropped on unknown view")

	var matrix := ResearchUiLink.build_query("", null, "", null, "", "matrix")
	if matrix != "?view=matrix":
		failures.append("matrix view without run_id should be allowed")

	var abs_path := ResearchUiLink.build_absolute_url("run-3")
	if not abs_path.contains("/research/"):
		failures.append("absolute url missing research path")
	if abs_path.contains("token=") or abs_path.contains("secret"):
		failures.append("credential-like keys leaked into research url")

	return failures
