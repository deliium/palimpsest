# Implementation Plan: Vendor-Independent LLM Provider Abstraction

Branch: main (no new branch)
Created: 2026-09-21
Refined: 2026-09-21

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M3 - Cognition and Providers"
Rationale: Establishes the provider-neutral, validated LLM boundary required before concrete cognition policies can be added. This plan completes only the provider-abstraction portion; M3 remains incomplete until cognition policies are delivered.

## Scope

Implement an async, provider-neutral `LLMProvider` that accepts immutable typed requests and returns only structurally validated Pydantic output plus normalized metadata. V1 will include one OpenAI-compatible HTTP adapter configurable for OpenAI-compatible services, Ollama, and vLLM. Anthropic remains a future adapter behind the same contract.

Raw provider bytes, text, mappings, headers, and exceptions may exist only inside the adapter while parsing and validation run. They must not appear in public results, errors, logs, retries, action commands, or world mutation paths. Structurally valid output remains semantically untrusted and non-authoritative.

## Architecture Decisions

- Replace synchronous `LLMClient.complete()` and raw-text `LLMResponse` with `async LLMProvider.generate(request: LLMRequest[T]) -> LLMResult[T]`.
- Require output schemas to inherit a project-owned strict `StructuredOutput` Pydantic base with frozen values, forbidden extra fields, strict validation, and non-finite number rejection.
- Represent requests with immutable ordered messages, prompt identity, generation options, and `LLMRequestContext` containing local `run_id`, `agent_id`, `tick`, and opaque `llm_request_id` correlation.
- Keep `run_id`, `agent_id`, and `tick` local. Never send them to providers. Only a validated opaque `llm_request_id` may be sent in one documented header, configurable off by default.
- Treat endpoint credentials, capability mode, and provider identity as adapter configuration, not request-overridable values. Resolve request options once before the first attempt and reuse them unchanged.
- Implement explicit structured-output modes (`json_schema`, `json_object`, and `prompt_only`) rather than inferring capabilities from provider names, model names, or URLs. Local strict validation is mandatory in every mode.
- Separate pure OpenAI-compatible wire encoding/decoding from async HTTP transport, retries, lifecycle, and logging.
- Use standard-library logging inside `llm`, consistent with other bounded packages. Do not import `infrastructure`; emit only allowlisted metadata through stable event messages.
- Store prompts as immutable versioned package resources under `src/llm/prompts/<name>/<version>/` and load them with `importlib.resources`.
- Leave `WorldEngine`, `CognitionStrategy`, and action admission unchanged. Future cognition must translate an exact validated decision schema into a fresh `AgentCommand` and then use normal simulation admission.

## Out of Scope

- Complex cognition, memory retrieval, psychological policy, tool calling, or an agent cognition loop.
- Making the existing synchronous `CognitionStrategy` async as part of provider work.
- A production Anthropic adapter or separate native Ollama/vLLM adapters; V1 targets their OpenAI-compatible endpoints.
- API lifespan allocation, `app.state` provider storage, FastAPI dependencies, routes, workers, or `compose.yaml` provider wiring before a real cognition consumer exists.
- Live network tests, startup provider probes, or making `/health` depend on provider availability.
- Automatic capability detection or fallback after provider rejection.

## Commit Plan
- **Commit 1** (after tasks 1-3): `feat(llm): define structured provider and prompt contracts`
- **Commit 2** (after tasks 4-6): `feat(llm): add configurable openai-compatible provider`
- **Commit 3** (after tasks 7-9): `test(llm): enforce provider trust and quality gates`
- **Commit 4** (after task 10): `docs(llm): document provider boundary and configuration`

## Tasks

### Phase 1: Provider-Neutral Contracts

- [x] Task 1: Define strict async request/result contracts and enable their architecture boundary.
  - Replace `LLMClient`/`LLMResponse` with a generic async `LLMProvider` protocol and immutable `LLMRequest[T]`/`LLMResult[T]` contracts in `src/llm/contracts.py` and `src/llm/models.py`.
  - Define `StructuredOutput` as the required Pydantic base with `strict=True`, `extra="forbid"`, `frozen=True`, and `allow_inf_nan=False`; reject permissive subclasses, unsupported unconstrained schemas, instances supplied instead of model classes, and validation results whose exact type differs from the requested model.
  - Define ordered immutable `LLMMessage` values using the V1 portable roles `system` and `user`, bounded non-blank content, a safe prompt name/version/digest reference, immutable request options, and `LLMRequestContext` with bounded non-blank `run_id`, `agent_id`, non-negative non-boolean `tick`, and header-safe `llm_request_id`.
  - State in types and docstrings that Pydantic validation establishes structure only, never truth, policy validity, actor identity, authorization, or world authority. Do not provide `to_agent_command()` or generic domain-decoding helpers.
  - Narrow the Pydantic architecture exception to `llm` in both import-linter and the AST checker while preserving the ban for `world`, `agents`, `memory`, `social`, `simulation`, and `analysis`.
  - Migrate existing typecheck/unit fixtures off `LLMClient` and `LLMResponse`. Remove the obsolete synchronous LLM-backed cognition fixture rather than changing `CognitionStrategy`; add positive and negative mypy fixtures for generic result inference and rejection as `AgentCommand`.
  - Files: `src/llm/contracts.py`, `src/llm/models.py`, `src/llm/__init__.py`, `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_boundary_checker.py`, `tests/typecheck/cognition_strategies.py`, `tests/typecheck/llm_providers.py`, `tests/unit/test_cognition_strategies.py`, `tests/unit/test_llm_trust_boundary.py`, `tests/unit/test_v1_typing.py`.
  - Logging: contracts and validation models remain log-free. Their representations must not expose prompt content, output values, or credentials; only explicitly safe identifiers may appear in diagnostics.
  - Dependencies: none.

- [x] Task 2: Define safe errors, effective-option precedence, capability modes, and retry policy.
  - Add explicit provider-neutral errors for configuration, timeout, connection, authentication/authorization, rate limit, upstream failure, provider protocol, output format, output schema, refusal/filtering, incomplete generation, closed provider, and retry exhaustion.
  - Public errors expose only stable code, retryability, total attempts, and optional status. Convert Pydantic and `httpx` failures without retaining bodies, URLs, offending inputs, raw exception text, unsafe causes/context, or `ValidationError` details.
  - Define immutable provider defaults, per-request options, and one `EffectiveOptions` resolution rule: a non-`None` request value overrides provider defaults; otherwise use the configured default or omit the field. Preserve valid falsey values such as `temperature=0`.
  - Keep endpoint, credentials, provider identity, and structured-output mode non-overridable per request. Omit unsupported options rather than sending JSON `null`.
  - Define `max_attempts` as total attempts, per-attempt timeout, optional total deadline, deterministic backoff, and bounded delta-seconds `Retry-After`. Propagate cancellation during request, sleep, and close unchanged.
  - Retry connection establishment, explicitly selected timeout classes, 408/429, selected 5xx statuses, and configured format/schema failures. Do not retry configuration, authentication/authorization, refusal/filtering, unsupported capability/schema, malformed provider envelopes, ordinary 4xx responses, or size-limit failures.
  - Never feed previous raw output into a retry. Reuse the exact effective request/context and expose only the last safe code/status on exhaustion.
  - Files: `src/llm/errors.py`, `src/llm/models.py`, `src/llm/__init__.py`, `tests/unit/test_llm_errors.py`, `tests/unit/test_llm_options.py`.
  - Logging: error objects provide an allowlisted log projection; retries log safe reason codes and counts only, never exception strings or tracebacks from provider/Pydantic failures.
  - Dependencies: Task 1.

### Phase 2: Versioned Prompt Infrastructure

- [x] Task 3: Implement immutable, package-safe versioned prompt resources.
  - Create `src/llm/prompts/` as the `importlib.resources.files("llm.prompts")` anchor and add a neutral V1 structured-generation prompt under `src/llm/prompts/structured/v1/` without cognition policy.
  - Define a strict manifest with prompt name, version, ordered role/template entries, required variable names, and template SHA-256 digests. Restrict names/versions to safe single path segments and reject traversal, unknown fields, duplicate roles, missing resources, and digest mismatches.
  - Use UTF-8 and an explicit LF/final-newline policy. Define a canonical rendered digest over prompt name, version, ordered roles, and rendered bytes; pin expected V1 resource and rendered digests in tests so published versions cannot change silently.
  - Implement safe substitution for declared string variables only. Reject missing/unexpected variables, non-string values, malformed or traversal-like placeholders, and unresolved placeholders without including values in errors.
  - Convert a rendered prompt deterministically into the Task 1 message and prompt-reference contracts and re-export public prompt types/loaders from `llm.__init__`.
  - Verify prompt resources in the built wheel before changing Hatch configuration; add package-data configuration only if the wheel test proves it is necessary.
  - Files: `src/llm/prompts/__init__.py`, `src/llm/prompts/loader.py`, `src/llm/prompts/structured/v1/manifest.json`, `src/llm/prompts/structured/v1/system.txt`, `src/llm/prompts/structured/v1/user.txt`, `src/llm/__init__.py`, `pyproject.toml` if required, `tests/unit/test_llm_prompts.py`, `tests/unit/test_packaging.py`.
  - Logging: prompt loading may log only trusted prompt name/version/digest and stable validation reason codes at `DEBUG`; never log templates, rendered text, variables, schemas, or caller-supplied invalid names.
  - Dependencies: Task 1.

### Phase 3: OpenAI-Compatible V1 Provider

- [x] Task 4: Build a pure OpenAI-compatible structured-output codec.
  - Add a provider-private codec that converts typed requests and effective options into an OpenAI-compatible `chat/completions` body without network access or provider SDKs.
  - Implement explicit `json_schema`, `json_object`, and `prompt_only` modes. Emit the standard OpenAI `response_format` shape for applicable modes, include deterministic JSON instructions in weaker modes, and preflight schema compatibility before transport.
  - Force one completion and decode exactly one assistant choice. Reject zero/multiple choices, null/non-string/multipart content, tool/function calls, error-shaped success bodies, refusals, filtering, and incomplete finish reasons according to Task 2 policy.
  - Strictly parse exactly one bounded top-level JSON object. Reject duplicate keys, markdown fences, trailing data, `NaN`/`Infinity`, non-object roots, and oversized schemas/content before exact `StructuredOutput` validation; discard raw text and untyped mappings immediately afterward.
  - Normalize metadata from local configuration: provider/model names are local, finish reason is a closed enum, upstream request IDs are optional bounded safe strings, and usage contains bounded non-negative non-boolean integers only. Return final-attempt usage only.
  - Files: `src/llm/providers/__init__.py`, `src/llm/providers/openai_compatible_codec.py`, `tests/unit/test_openai_compatible_codec.py`.
  - Logging: the pure codec is log-free. Safe failures use Task 2 codes and never expose provider content, headers, schemas, or rejected values.
  - Dependencies: Tasks 1-3.

- [x] Task 5: Implement bounded async HTTP transport, retries, lifecycle, correlation, and metadata-only logs.
  - Implement `OpenAICompatibleProvider` with `httpx.AsyncClient`, moving `httpx` into runtime dependencies and updating `uv.lock` before production imports are introduced.
  - Require `base_url` to include any API prefix and normalize only its trailing slash; append relative `chat/completions` so `/v1/` is preserved. Disable redirects and ambient proxy/environment behavior for owned clients.
  - Send only optional bearer credentials and, when enabled, the validated opaque `llm_request_id` header. Never send `run_id`, `agent_id`, tick, HTTP request IDs, world IDs, or authority identifiers upstream.
  - Enforce request/schema/message/header and streamed response byte limits before materializing unbounded content. Classify status, timeout, connection, protocol, and size failures through Task 2.
  - Implement retries with injected async sleeper and monotonic duration source; do not use global randomness, wall-clock defaults, or nondeterministic jitter. Preserve one effective request and correlation ID across attempts.
  - Define ownership precisely: an owned client is lazily constructed without network I/O and closed exactly once; an injected client is never closed by the provider; close is idempotent; generation after close fails safely.
  - Use `logging.getLogger("llm.openai_compatible")` and stable metadata-only messages. Do not import `infrastructure`, use `exc_info`, or log agent IDs, endpoint URLs, headers, prompt/output/schema content, upstream free-form metadata, or exception text.
  - Files: `src/llm/providers/openai_compatible.py`, `src/llm/providers/__init__.py`, `src/llm/__init__.py`, `pyproject.toml`, `uv.lock`, `tests/unit/test_openai_compatible_provider.py`, `tests/unit/test_llm_correlation.py`.
  - Logging: assert `DEBUG` start/attempt/retry details, `INFO` success metadata, `WARNING` retryable safe codes, and `ERROR` terminal safe codes in the same task as instrumentation. Use safe usage names that cannot be confused with authentication tokens.
  - Dependencies: Tasks 2 and 4.

- [x] Task 6: Add typed settings and a standalone provider factory without premature runtime composition.
  - Extend `src/infrastructure/settings.py` with disabled-by-default `PALIMPSEST_LLM_*` settings for adapter kind, model, base URL, optional API key, structured-output mode, temperature, timeouts, attempt limits, byte limits, and correlation-header behavior.
  - Validate exact HTTP(S) scheme, required host/model when enabled, allowed local HTTP endpoints, `/v1` paths, no userinfo (including encoded userinfo), query, or fragment, and non-blank API keys. Reject booleans for numeric settings and enforce finite/bounded values.
  - Prevent full endpoints, path/query values, keys, and rejected inputs from appearing in `repr`, `str`, `SettingsError`, logging projections, or validation details. Build safe settings errors from Pydantic errors with input/context excluded and expose only boolean/enum/count diagnostics through `bootstrap_fields()`.
  - Add `src/llm/factory.py` that accepts provider-owned configuration values and constructs the disabled or OpenAI-compatible provider without importing `infrastructure`, reading environment state, allocating a network connection, or probing an endpoint.
  - Keep `src/api/app.py`, `src/api/dependencies.py`, API import rules, and `compose.yaml` unchanged. Document that a future cognition consumer will own settings-to-factory mapping and lifecycle composition.
  - Files: `src/infrastructure/settings.py`, `src/llm/factory.py`, `src/llm/__init__.py`, `.env.example`, `tests/unit/test_settings.py`, `tests/unit/test_llm_factory.py`.
  - Logging: settings/factory log only adapter kind, model-safe identifier, mode, timeout/attempt/limit values, enabled state, and `has_api_key`; never log endpoint values, credentials, prompts, schemas, or output.
  - Dependencies: Tasks 1, 2, and 5.

### Phase 4: Deterministic Tests and Trust Gates

- [x] Task 7: Provide a deterministic scripted provider for network-free tests.
  - Add a reusable fake implementing the exact public `LLMProvider` contract with per-`llm_request_id` queues and explicit invocation ordinals. Reject duplicate concurrently active IDs, unexpected IDs, exhausted scripts, and response models incompatible with scripted `StructuredOutput` values.
  - Script validated outputs or typed failures only; retry behavior remains owned by the real provider rather than duplicated in the fake.
  - Defensively copy scripted values and recorded safe metadata so caller mutation cannot alter history. Do not retain credentials, rendered prompt content, schemas, or output dumps in generic call records.
  - Add a deterministic fake sleeper/monotonic source for exact delay, duration, cancellation, and concurrent-isolation assertions.
  - Files: `tests/fakes/__init__.py`, `tests/fakes/llm.py`, `tests/unit/test_fake_llm_provider.py`.
  - Logging: fakes emit no payload logs; unexpected-call messages identify only safe correlation/model metadata and stable test failure codes.
  - Dependencies: Tasks 1-3.

- [x] Task 8: Complete the network-free interoperability, validation, packaging, and redaction matrix.
  - Cover exact wire bodies for OpenAI-compatible JSON Schema/JSON object/prompt-only modes and local Ollama/vLLM endpoint profiles without requiring vendor SDKs or live services.
  - Test option precedence, `temperature=0`, path-prefix preservation, IPv6/local URLs, disabled redirects/proxies, missing optional metadata, envelope failures, duplicate JSON keys, non-standard constants, response limits, retry matrix/backoff/exhaustion, cancellation, owned/injected closure, and generation after close.
  - Prove concurrent calls cannot consume each other's scripts and that local run/agent/tick context remains unchanged across attempts but absent from all outbound headers and bodies.
  - Strengthen `src/infrastructure/logging.py` defense-in-depth redaction for API keys, authorization, messages, schemas, variables, request/response bodies, validated outputs, endpoint URLs, and nested containers without relying on redaction as the provider's primary safety mechanism.
  - Assert logs and public errors contain no prompt/output/schema content, endpoint URL, secret, upstream free-form metadata, Pydantic input, original `httpx` exception, or unsafe cause chain.
  - Keep tests network-free with injected/`httpx.MockTransport` transports. Any subprocess packaging command must be forced offline, use the running interpreter, avoid backend/interpreter downloads, install the wheel with `--no-deps`, execute outside the checkout, and prove prompt resources load/render from the installed wheel.
  - Files: `src/infrastructure/logging.py`, `tests/unit/test_logging.py`, `tests/unit/test_openai_compatible_codec.py`, `tests/unit/test_openai_compatible_provider.py`, `tests/unit/test_llm_correlation.py`, `tests/unit/test_llm_prompts.py`, `tests/unit/test_packaging.py`, `tests/conftest.py` if a narrowly scoped in-process network guard is practical.
  - Logging: capture and assert the full safe event/level matrix in this task. A socket guard must not break `ASGITransport`, and it must not be claimed to cover subprocesses.
  - Dependencies: Tasks 3-7.

- [x] Task 9: Finalize architecture, action-admission, and project-context guarantees.
  - Keep vendor SDKs prohibited and assert provider/prompt modules cannot import `world`, `agents`, `simulation`, `persistence`, `api`, or `infrastructure`, private authority modules, or nondeterministic clocks/randomness.
  - Verify public provider signatures cannot accept `World`, `WorldState`, `WorldEngine`, `ActionSubmission`, `ActionRequest`, or mutable world aggregates.
  - Extend trust tests so `LLMResult`, `StructuredOutput`, model dumps, raw strings, mappings, and provider-shaped authority payloads are rejected by `require_agent_command`, `ActionSubmission`, admission, and world-operation boundaries.
  - Assert no public result exposes raw text/provider payloads and no adapter offers direct conversion to commands. Keep the future cognition translation stage explicit and separate.
  - Update `.ai-factory/ARCHITECTURE.md` and `.ai-factory/DESCRIPTION.md` to describe the implemented provider-neutral structured boundary and unchanged composition/runtime scope. Do not alter `.ai-factory/RULES.md` or mark M3 complete.
  - Run Ruff, mypy, unit tests, architecture tests, and wheel/resource tests at this checkpoint so every implementation commit is independently valid.
  - Files: `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_boundary_checker.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_llm_provider_isolation.py`, `tests/architecture/test_world_authority.py`, `tests/unit/test_llm_trust_boundary.py`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/DESCRIPTION.md`.
  - Logging: architecture tests enforce standard-library, metadata-only provider logs and prohibit sensitive fields or unsafe exception logging; no authority test logs world or model payloads.
  - Dependencies: Tasks 1-8.

### Phase 5: Mandatory Documentation Checkpoint

- [ ] Task 10: Run the mandatory `$aif-docs` checkpoint for provider usage and trust boundaries.
  - Invoke `$aif-docs` after implementation approval to create/update `docs/llm-providers.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/development.md`, and the README documentation index as appropriate.
  - Document the public request/result API, strict schema contract, structured-output mode matrix, retry/error matrix, correlation privacy rules, prompt immutability/versioning, local OpenAI-compatible/Ollama/vLLM configuration, lifecycle ownership, deterministic fake usage, and recorded-response requirement for exact replay.
  - Update previous/next navigation and See Also links for every affected documentation page according to the existing docs ordering. Keep complex cognition and runtime composition explicitly deferred and M3 incomplete.
  - Files: documentation files selected and owned by `$aif-docs`; expected scope includes `README.md`, `docs/llm-providers.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/development.md`, and affected neighboring navigation pages.
  - Logging: document the `DEBUG`/`INFO`/`WARNING`/`ERROR` event policy and forbidden fields. The docs task itself adds no runtime logging.
  - Dependencies: Task 9.

## Acceptance Criteria

- `LLMProvider.generate()` is async and generic over project-owned strict Pydantic output models; public results contain no raw response text, arbitrary provider mapping, or unsafe exception.
- Requests use immutable ordered messages, explicit prompt identity, deterministic option precedence, and bounded local run/agent/tick/invocation correlation.
- Only optional `llm_request_id` correlation may be sent upstream; run, agent, tick, HTTP, world, and authority identifiers never leave the process.
- OpenAI-compatible `json_schema`, `json_object`, and `prompt_only` modes have deterministic wire shapes and always perform local strict JSON/schema validation.
- The V1 adapter supports configurable OpenAI-compatible, Ollama, and vLLM endpoints while preserving `/v1/` path prefixes, disabling redirects/ambient proxies, and importing no vendor SDK.
- Transport, provider-envelope, refusal, incomplete-output, format, schema, and exhaustion failures use explicit safe errors and bounded deterministic retry behavior; cancellation is never wrapped or retried.
- Provider/model/finish/usage/request metadata is normalized, bounded, and treated as untrusted input; raw upstream values are never logged wholesale.
- Versioned prompts are immutable package resources with pinned digests, safe substitution, and successful loading/rendering from an installed wheel outside the checkout.
- Deterministic fake-provider tests use no network and cover success, concurrency, schema mismatch, typed failures, and exhausted scripts.
- Owned and injected client lifecycles are distinct, idempotent, and tested without startup network operations.
- Full endpoint URLs, credentials, prompt/output/schema content, unsafe validation inputs, and provider exception chains are absent from settings errors, provider errors, and every log level.
- Existing cognition/typecheck fixtures are migrated without making `CognitionStrategy` async or implementing cognition policy.
- Provider modules have no world mutation capability, and architecture/admission tests prove provider values cannot bypass explicit future cognition translation and normal action admission.
- Unit and wheel-resource tests cannot download interpreters, build backends, dependencies, or contact live providers.
- Every implementation checkpoint passes Ruff, mypy, unit tests, architecture tests, and wheel/package-resource tests.
- Documentation is completed through `$aif-docs`, and M3 remains open because cognition is still deferred.
