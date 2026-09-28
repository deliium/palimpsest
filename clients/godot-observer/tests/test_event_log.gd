extends RefCounted

const EventLog := preload("res://scripts/ui/event_log.gd")
const Log := preload("res://scripts/log.gd")


class Body:
	var entity_id: String
	var agent_id: String
	var life_status: String


class Place:
	var location_id: String
	var display_name: String
	var name: String


class World:
	var agents: Array
	var locations: Array


class Event:
	var tick: int
	var sequence: int
	var type: String
	var actor_id: Variant
	var target_id: Variant
	var origin_location_id: Variant
	var destination_location_id: Variant


func run() -> Array:
	var failures: Array = []
	var log := EventLog.new()
	var world := World.new()
	var alice := Body.new()
	alice.entity_id = "body-alice"
	alice.agent_id = "Alice"
	alice.life_status = "alive"
	var bob := Body.new()
	bob.entity_id = "body-bob"
	bob.agent_id = "Bob"
	bob.life_status = "dead"
	var village := Place.new()
	village.location_id = "loc-village"
	village.display_name = "Village"
	village.name = "village"
	var forest := Place.new()
	forest.location_id = "loc-forest"
	forest.display_name = "Forest"
	forest.name = "forest"
	world.agents = [alice, bob]
	world.locations = [village, forest]
	log.set_world(world)
	var moved := _event(4, 0, "AGENT_MOVED", "body-alice", "", "loc-village", "loc-forest")
	var died := _event(4, 1, "AGENT_DIED", "", "body-bob", "loc-forest", "")
	var waited := _event(5, 0, "CUSTOM_SIGNAL", "body-alice", "", "", "")
	log.replace_window([moved, died, waited], 4, 1)
	var death_line := log.line_text(1)
	if "AGENT_DIED" not in death_line or "Bob" not in death_line or "died" not in death_line:
		failures.append("death line should name the target body")
	if death_line.begins_with("4:1") == false:
		failures.append("death line should include tick and sequence")
	if log.line_text(0).contains("Alice moved Village -> Forest") == false:
		failures.append("move description should use labels")
	if log.line_text(2).contains("CUSTOM_SIGNAL") == false:
		failures.append("unknown types should still render")
	log.set_filters("Bob", "", "")
	if log.visible_lines.size() != 1 or str(log.visible_lines[0]["type"]) != "AGENT_DIED":
		failures.append("agent filter should keep the matching body")
	log.set_filters("", "AGENT_MOVED", "")
	if log.visible_lines.size() != 1:
		failures.append("type filter should be an exact semantic type")
	log.set_filters("", "", "Forest")
	if log.visible_lines.is_empty():
		failures.append("location filter should match destination names")
	log.set_filters("", "", "")
	if log.visible_lines.size() != 3:
		failures.append("empty filters should show every loaded line")
	var clicked: Array = []
	log.seek_requested.connect(func(tick: int, sequence: int) -> void:
		clicked.append({"tick": tick, "sequence": sequence})
	)
	log.click_line(1)
	if clicked.size() != 1 or clicked[0]["tick"] != 4 or clicked[0]["sequence"] != 1:
		failures.append("click should emit tick and sequence")
	var text := "\n".join(Log.recent)
	if "seek_clicked" not in text or "filter_set" not in text:
		failures.append("log view should record seek_clicked and filter_set")
	return failures


func _event(
	tick: int,
	sequence: int,
	type_name: String,
	actor_id: String,
	target_id: String,
	origin_id: String,
	destination_id: String,
) -> Event:
	var event := Event.new()
	event.tick = tick
	event.sequence = sequence
	event.type = type_name
	event.actor_id = null if actor_id == "" else actor_id
	event.target_id = null if target_id == "" else target_id
	event.origin_location_id = null if origin_id == "" else origin_id
	event.destination_location_id = null if destination_id == "" else destination_id
	return event
