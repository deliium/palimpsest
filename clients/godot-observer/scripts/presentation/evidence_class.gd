extends RefCounted
class_name EvidenceClass

## Wire / metadata values (longer form). On-screen labels stay short.
const OBJECTIVE := "OBJECTIVE"
const SUBJECTIVE := "SUBJECTIVE_TO_SELECTED_AGENT"
const ANALYTICAL := "ANALYTICAL_INFERRED"

const LABEL_OBJECTIVE := "OBJECTIVE"
const LABEL_SUBJECTIVE := "SUBJECTIVE"
const LABEL_ANALYTICAL := "ANALYTICAL"

const OVERLAY_LABELS := {
	"border_physical": "Physical",
	"border_claims": "Claims",
	"border_agreements": "Agreements",
	"border_patterns": "Patterns",
	"migration_route": "Migration route",
	"migration_cause": "Migration cause",
	"migration_wave": "Migration wave",
	"migration_integration": "Migration integration",
	"infrastructure_node": "Infrastructure node",
	"infrastructure_edge": "Infrastructure edge",
	"infrastructure_damaged": "Infrastructure damaged",
	"infrastructure_destroyed": "Infrastructure destroyed",
	"route_open": "Route open",
	"route_restricted": "Route restricted",
	"route_closed": "Route closed",
	"trade_corridors": "Trade corridors",
	"trade_major_locations": "Major exchange locations",
	"trade_cross_society": "Cross-society flows",
	"trade_coverage": "Trade coverage",
}

## Overlay kind → evidence class. Presentation-only; never invents world facts.
const OVERLAY_CLASSES := {
	"communication_flows": OBJECTIVE,
	"subjective_labels": SUBJECTIVE,
	"relationships": SUBJECTIVE,
	"territorial_claims": SUBJECTIVE,
	"border_physical": OBJECTIVE,
	"border_claims": SUBJECTIVE,
	"border_agreements": SUBJECTIVE,
	"border_patterns": ANALYTICAL,
	"migration_route": OBJECTIVE,
	"migration_cause": SUBJECTIVE,
	"migration_wave": ANALYTICAL,
	"migration_integration": ANALYTICAL,
	"infrastructure_node": OBJECTIVE,
	"infrastructure_edge": OBJECTIVE,
	"infrastructure_damaged": OBJECTIVE,
	"infrastructure_destroyed": OBJECTIVE,
	"route_open": OBJECTIVE,
	"route_restricted": OBJECTIVE,
	"route_closed": OBJECTIVE,
	"trade_corridors": ANALYTICAL,
	"trade_major_locations": ANALYTICAL,
	"trade_cross_society": ANALYTICAL,
	"trade_coverage": ANALYTICAL,
	"narrative_hops": SUBJECTIVE,
	"spatial_control": ANALYTICAL,
	"emergent_group_formation": ANALYTICAL,
	"emergent_social_norms": ANALYTICAL,
	"persistent_social_conventions": ANALYTICAL,
	"distributed_reputation": ANALYTICAL,
	"cultural_narrative_lineage": ANALYTICAL,
	"communication_strategy": ANALYTICAL,
	"communication_strategy_audit": ANALYTICAL,
	"cultural_transmission": ANALYTICAL,
	"skill_learning": ANALYTICAL,
	"population": OBJECTIVE,
	"generation": OBJECTIVE,
	"cohort": OBJECTIVE,
	"age_stage": OBJECTIVE,
	"kinship": OBJECTIVE,
	"caregiving": OBJECTIVE,
	"mentorship_subjective": SUBJECTIVE,
	"mentorship_analytical": ANALYTICAL,
}


static func from_wire(value: String) -> String:
	match value:
		"objective":
			return OBJECTIVE
		"subjective":
			return SUBJECTIVE
		"analytical":
			return ANALYTICAL
		_:
			return ""


static func short_label(evidence_class: String) -> String:
	match evidence_class:
		OBJECTIVE:
			return LABEL_OBJECTIVE
		SUBJECTIVE:
			return LABEL_SUBJECTIVE
		ANALYTICAL:
			return LABEL_ANALYTICAL
		_:
			if evidence_class == LABEL_OBJECTIVE or evidence_class == LABEL_SUBJECTIVE or evidence_class == LABEL_ANALYTICAL:
				return evidence_class
			return LABEL_ANALYTICAL


static func for_overlay(kind: String) -> String:
	if OVERLAY_CLASSES.has(kind):
		return str(OVERLAY_CLASSES[kind])
	return ANALYTICAL


static func label_for_overlay(kind: String) -> String:
	if OVERLAY_LABELS.has(kind):
		return str(OVERLAY_LABELS[kind])
	return short_label(for_overlay(kind))


static func is_valid(evidence_class: String) -> bool:
	return (
		evidence_class == OBJECTIVE
		or evidence_class == SUBJECTIVE
		or evidence_class == ANALYTICAL
		or evidence_class == LABEL_OBJECTIVE
		or evidence_class == LABEL_SUBJECTIVE
		or evidence_class == LABEL_ANALYTICAL
	)
