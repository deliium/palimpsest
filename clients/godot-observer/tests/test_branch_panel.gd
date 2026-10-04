extends RefCounted

const BranchPanelScript := preload("res://scripts/ui/branch_panel.gd")


func run() -> Array:
	var failures: Array = []
	var panel: BranchPanelScript = BranchPanelScript.new()
	# Headless: synthesize child nodes the script expects.
	var column := VBoxContainer.new()
	column.name = "Column"
	panel.add_child(column)
	var summary := Label.new()
	summary.name = "Summary"
	column.add_child(summary)
	var empty := Label.new()
	empty.name = "Empty"
	column.add_child(empty)
	var children := ItemList.new()
	children.name = "Children"
	column.add_child(children)
	var actions := HBoxContainer.new()
	actions.name = "Actions"
	column.add_child(actions)
	for name in ["ReturnPrevious", "OpenParent", "OpenChild", "LoadMore"]:
		var button := Button.new()
		button.name = name
		actions.add_child(button)
	panel._ready()
	panel.show_lineage(
		{
			"run_id": "run-root",
			"parent_run_id": "",
			"fork_tick": -1,
			"intervention_summary": "",
			"branch_id": "",
		},
		[],
		null,
		"",
		0,
	)
	if not empty.visible or "No child" not in empty.text:
		failures.append("root without children should show empty-state")
	if panel._return_btn.disabled == false:
		failures.append("empty nav stack should disable return")
	panel.show_lineage(
		{
			"run_id": "run-child",
			"parent_run_id": "run-root",
			"fork_tick": 4,
			"intervention_summary": "seed:abcd",
			"branch_id": "b1",
		},
		[{
			"child_run_id": "run-grand",
			"fork_tick": 8,
			"intervention_summary": "x",
		}],
		"run-grand",
		"",
		2,
	)
	if not panel._parent_btn.visible:
		failures.append("child run should show open parent")
	if panel._children.item_count != 1:
		failures.append("child list should render one row")
	if not panel._more_btn.visible:
		failures.append("next_cursor should show load more")
	if panel._return_btn.disabled:
		failures.append("nav depth > 0 should enable return")
	panel.show_lineage(
		{"run_id": "run-x", "parent_run_id": "", "fork_tick": -1},
		[],
		null,
		"unauthorized",
		0,
	)
	if not empty.visible or "unauthorized" not in empty.text:
		failures.append("capability failure should surface reason code")
	return failures
