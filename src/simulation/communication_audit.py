"""Read-only classification of detached communication audit evidence."""

from collections.abc import Mapping

from world.events import WorldEvent

__all__ = ["classify_communication_audit"]


def classify_communication_audit(
    audit: object, events: Mapping[str, WorldEvent]
) -> str:
    """Classify recorded assertions without participating in live cognition."""
    stance = getattr(audit, "stance", None)
    stance = getattr(stance, "value", stance)
    strategy = getattr(audit, "strategy", None)
    strategy = getattr(strategy, "value", strategy)
    if stance in {"refuse", "withhold"}:
        return "not_asserted"
    if stance == "hedge":
        return "uncertain_inference"
    if strategy in {
        "deliberate_false_statement",
        "exaggeration",
        "selective_disclosure",
    }:
        return "deliberate_deception"
    if stance != "assert_match":
        return "unmatched"
    cited = getattr(audit, "cited_event_id", None)
    if type(cited) is not str or (event := events.get(cited)) is None:
        return "unmatched"
    raw_source = getattr(audit, "source_atom_tokens", ())
    source = (
        {item for item in raw_source if type(item) is str}
        if isinstance(raw_source, tuple)
        else set()
    )
    details = event.details
    kind = details.kind
    if kind in {"talk", "ask", "tell"}:
        utterance = getattr(details, "utterance", None)
        content = getattr(utterance, "content", None)
        concepts = getattr(content, "concepts", ())
        public = set(concepts) if isinstance(concepts, tuple) else set()
    else:
        public = {kind}
        if event.actor_id is not None:
            public.add(event.actor_id.value)
        if event.target_id is not None:
            public.add(event.target_id.value)
        destination = getattr(event.occurrence, "destination_location_id", None)
        if destination is not None:
            public.add(destination.value)
    return "veridical" if source <= public else "memory_error"
