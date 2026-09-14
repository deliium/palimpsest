# Project Rules

## Axioms

1. World state is authoritative; agents never receive mutable `WorldState`.
2. LLM output is untrusted input and cannot mutate world state directly.
3. Memory is agent-scoped; no automatic cross-agent memory sharing.
4. Randomness is injected from an explicit simulation seed; no global RNG in domain code.
5. Cross-module imports use public facades / `__all__` only.
6. Domain modules do not import `infrastructure`; composition roots wire adapters.
7. Settings use the `PALIMPSEST_` prefix only; imports must not require secrets.
8. Integration tests may only target disposable databases named with `palimpsest_test`, and must fail closed on ambiguous migration targets.
9. Operational timestamps and request IDs are infrastructure metadata, never domain IDs or seeds.
10. Do not introduce excluded technologies (Kafka, Celery, microservices, extra vector DBs, etc.) in this foundation.

## Coding Standards

- Prefer frozen / defensively detached values for immutable domain contracts
- Boundary models reject unknown fields
- Keep logging secret-safe: never log DSNs, credentials, prompts, bodies, memories, or embeddings
- Add tests with the change; use Hypothesis for deterministic/invariant properties where practical
