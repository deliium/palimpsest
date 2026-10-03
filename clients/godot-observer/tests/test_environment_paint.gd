extends RefCounted

const Protocol := preload("res://scripts/protocol/models.gd")
const LocationLayer := preload("res://scripts/view/location_layer.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _environment_counts(), "environment paint counts")
	return failures


func _environment_counts() -> String:
	var layer := LocationLayer.new()
	var world = Protocol.WorldModel.new()
	world.tick = 3
	world.season = "winter"
	var location := Protocol.LocationModel.new()
	location.location_id = "loc-camp"
	location.name = "Camp"
	location.display_name = "Camp"
	world.locations.append(location)
	var hazard := Protocol.HazardModel.new()
	hazard.location_id = "loc-camp"
	hazard.hazard_kind = "cold_snap"
	hazard.remaining_ticks = 2
	world.hazards.append(hazard)
	var depleted := Protocol.ResourceModel.new()
	depleted.resource_id = "res-empty"
	depleted.name = "Empty"
	depleted.kind = "wood"
	depleted.location_id = "loc-camp"
	depleted.quantity = 0.0
	depleted.unit = "units"
	world.resources.append(depleted)
	var scarce_loc := Protocol.LocationModel.new()
	scarce_loc.location_id = "loc-grove"
	scarce_loc.name = "Grove"
	scarce_loc.display_name = "Grove"
	world.locations.append(scarce_loc)
	var scarce := Protocol.ResourceModel.new()
	scarce.resource_id = "res-low"
	scarce.name = "Berries"
	scarce.kind = "food"
	scarce.location_id = "loc-grove"
	scarce.quantity = 1.0
	scarce.unit = "units"
	world.resources.append(scarce)
	layer.show_world(world)
	if not layer._depleted.has("loc-camp"):
		layer.free()
		return "depleted outline missing"
	if not layer._scarce.has("loc-grove"):
		layer.free()
		return "scarce outline missing"
	if layer._scarce.has("loc-camp"):
		layer.free()
		return "depleted location should not also be scarce"
	var logged := "\n".join(preload("res://scripts/log.gd").recent)
	if "environment_painted tick=3 season=winter hazard_count=1 depleted_count=1" not in logged:
		layer.free()
		return "environment_painted log missing counts"
	layer.free()
	return ""


func _expect(failures: Array, message: String, label: String) -> void:
	if message != "":
		failures.append("%s: %s" % [label, message])
