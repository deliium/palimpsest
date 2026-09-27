extends Node2D

@onready var _locations: Node2D = $LocationLayer
@onready var _connections: Node2D = $ConnectionLayer
@onready var _objects: Node2D = $ObjectLayer
@onready var _agents: Node2D = $AgentLayer


func show_world(world: Variant) -> void:
	_locations.show_world(world)
	var centers := {}
	for location in world.locations:
		centers[location.location_id] = _locations.zone_center(location.location_id)
	_connections.show_world(world, centers)
	_objects.show_world(world, centers)
	_agents.show_world(world, centers)
