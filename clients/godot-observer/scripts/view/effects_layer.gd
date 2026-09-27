extends Node2D

const ObserverLog := preload("res://scripts/log.gd")


func _ready() -> void:
	ObserverLog.debug("view", "scene_ready layer=%s" % name)
