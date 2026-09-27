extends Node2D

const ObserverLog := preload("res://scripts/log.gd")


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)


func show_world(_world: Variant, _zone_centers: Dictionary = {}) -> void:
	pass
