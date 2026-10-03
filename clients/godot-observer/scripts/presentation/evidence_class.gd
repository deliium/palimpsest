extends RefCounted
class_name EvidenceClass

## Wire / metadata values (longer form). On-screen labels stay short.
const OBJECTIVE := "OBJECTIVE"
const SUBJECTIVE := "SUBJECTIVE_TO_SELECTED_AGENT"
const ANALYTICAL := "ANALYTICAL_INFERRED"

const LABEL_OBJECTIVE := "OBJECTIVE"
const LABEL_SUBJECTIVE := "SUBJECTIVE"
const LABEL_ANALYTICAL := "ANALYTICAL"

## Overlay kind → evidence class. Presentation-only; never invents world facts.
const OVERLAY_CLASSES := {
	"communication_flows": OBJECTIVE,
	"subjective_labels": SUBJECTIVE,
	"relationships": SUBJECTIVE,
	"territorial_claims": SUBJECTIVE,
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
}


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


static func is_valid(evidence_class: String) -> bool:
	return (
		evidence_class == OBJECTIVE
		or evidence_class == SUBJECTIVE
		or evidence_class == ANALYTICAL
		or evidence_class == LABEL_OBJECTIVE
		or evidence_class == LABEL_SUBJECTIVE
		or evidence_class == LABEL_ANALYTICAL
	)
