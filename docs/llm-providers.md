# LLM Providers

[← Previous Page](memory-reconstruction.md) · [Back to README](../README.md) · [Next Page →](physical-simulation.md)

Provider-neutral structured generation lives in the `llm` package. Public results are only structurally validated Pydantic values plus normalized metadata. They are **not** agent commands, action submissions, or world authority.

API lifespan, FastAPI dependencies, workers, and `compose.yaml` do **not** own a provider yet. Map settings → `ProviderFactoryConfig` in a cognition composition root (for example beside `AgentRuntime`), own lifecycle, translate an exact validated decision schema into a fresh `AgentCommand`, then use normal simulation admission. See [Cognition and agent runtime](cognition-runtime.md). Deterministic V1 imagination/motivation/intention policies are production; the **M3 providers** slice (API/`compose` lifecycle) remains open.

## Public request / result API

```python
from llm import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMRequestContext,
    MessageRole,
    StructuredOutput,
    create_llm_provider,
)

class Decision(StructuredOutput):
    kind: str

request = LLMRequest.create(
    messages=(LLMMessage(role=MessageRole.USER, content="choose"),),
    response_model=Decision,
    context=LLMRequestContext(
        run_id="run-1",
        agent_id="agent-1",
        tick=0,
        llm_request_id="req-1",
    ),
)
result = await provider.generate(request)
decision: Decision = result.output  # structure only — not a command
```

| Type | Role |
| --- | --- |
| `StructuredOutput` | Required Pydantic base (`strict`, `extra=forbid`, `frozen`, `allow_inf_nan=False`) |
| `LLMRequest[T]` | Immutable messages, `response_model`, local context, optional prompt ref/options |
| `LLMResult[T]` | Validated `output` + `LLMResultMetadata` (no raw provider text) |
| `LLMProvider` | `async generate(request) -> LLMResult[T]` |
| `LLMRequestContext` | Local `run_id` / `agent_id` / `tick` + opaque `llm_request_id` |

Pydantic validation proves **shape only**. It does not prove truth, policy validity, actor identity, authorization, or world authority. There is no `to_agent_command()` helper.

## Structured-output modes

Adapter configuration selects exactly one mode. Local strict JSON + schema validation always runs.

| Mode | Wire behavior |
| --- | --- |
| `json_schema` | OpenAI `response_format.json_schema` (strict) after schema preflight |
| `json_object` | `response_format.json_object` plus deterministic JSON system instruction |
| `prompt_only` | Instruction only; no `response_format` |

Unsupported options are omitted from the body (never sent as JSON `null`). Endpoint, credentials, provider identity, and mode are **not** overridable per request.

## Retry and error matrix

Public errors are `LLMError` with allowlisted fields only: `code`, `retryable`, `attempts`, optional `status`, and `last_code` on exhaustion. No bodies, URLs, schemas, prompts, ValidationError details, or httpx exception text.

| Code | Retryable by default |
| --- | --- |
| `connection`, `timeout`, `rate_limit`, `upstream` | yes |
| `output_format`, `output_schema` | yes (can disable via `RetryPolicy`) |
| `configuration`, `authentication`, `provider_protocol`, `refusal`, `incomplete`, `closed`, `retry_exhaustion` | no |

Also retry HTTP `408` / `429` and selected `5xx`. Do not retry ordinary `4xx`, size-limit failures, or malformed envelopes. Cancellation during request/sleep/close is never wrapped or retried. Retries reuse the same effective request; previous raw output is never fed back.

## Correlation privacy

| Field | Local only | May send upstream |
| --- | --- | --- |
| `run_id`, `agent_id`, `tick` | yes | **never** |
| `llm_request_id` | yes | optional header `X-LLM-Request-ID` (off by default) |

HTTP request IDs, world IDs, and authority identifiers are never sent to providers.

## Versioned prompts

Immutable package resources under `src/llm/prompts/<name>/<version>/` load via `importlib.resources`:

```python
from llm import load_prompt, render_prompt

loaded = load_prompt("structured", "v1")
rendered = render_prompt(loaded, {"schema_name": "Decision", "schema_hint": "{...}"})
messages = rendered.messages  # tuple[LLMMessage, ...]
reference = rendered.reference  # PromptReference(name, version, digest)
```

Manifest digests are pinned in tests. Safe string substitution only; invalid names/values never appear in errors or logs.

`llm/prompts/reflection/v1/` is the reflection selector (`reflection.selection.v1`). The payload is candidate ids, counts, and closed codes. The schema has no prose claim field. `DISABLED` and `DETERMINISTIC` never call the provider. A missing provider, `allow_provider=False`, a transport error, a schema failure, or a foreign id applies the deterministic candidate set and sets `fallback_used`. The provider never becomes an `AgentCommand` and never mutates world state. Logs on this path are `reflection_llm_start`, `reflection_llm_complete`, and `reflection_llm_rejected` with mode, counts, and `reason_code` only.

## Local OpenAI-compatible / Ollama / vLLM

V1 ships one HTTP adapter (`OpenAICompatibleProvider`) aimed at OpenAI-compatible endpoints, including local Ollama and vLLM `/v1` servers. No vendor SDKs.

| Setting | Purpose |
| --- | --- |
| `PALIMPSEST_LLM_ADAPTER_KIND` | `disabled` (default) or `openai_compatible` |
| `PALIMPSEST_LLM_MODEL` | Required when enabled |
| `PALIMPSEST_LLM_BASE_URL` | Exact `http(s)` URL with `/v1` path; no userinfo/query/fragment; local HTTP hosts only |
| `PALIMPSEST_LLM_API_KEY` | Optional bearer; never logged |
| `PALIMPSEST_LLM_STRUCTURED_OUTPUT_MODE` | `json_schema` / `json_object` / `prompt_only` |
| `PALIMPSEST_LLM_TEMPERATURE` | Optional; `0` is preserved |
| `PALIMPSEST_LLM_MAX_ATTEMPTS` | Total attempts |
| `PALIMPSEST_LLM_PER_ATTEMPT_TIMEOUT_SECONDS` | Per-attempt timeout |
| `PALIMPSEST_LLM_TOTAL_DEADLINE_SECONDS` | Optional overall deadline |
| `PALIMPSEST_LLM_MAX_*_BYTES` | Request / response / header byte limits |
| `PALIMPSEST_LLM_SEND_CORRELATION_HEADER` | Default `false` |

`create_llm_provider(ProviderFactoryConfig(...), sleep=..., monotonic=...)` builds a disabled or OpenAI-compatible provider without reading the environment or opening a network connection. Map `Settings` → config in a future cognition composition root — not in `api` today.

### Lifecycle ownership

- **Owned client** (`client=None`): lazy `httpx.AsyncClient` with redirects and ambient proxies disabled; `close()` once
- **Injected client**: never closed by the provider
- `generate` after close → `LLMError(closed)`

## Deterministic fake and exact replay

Use `tests/fakes/llm.py` (`FakeLLMProvider`, `FakeClock`) for network-free tests: per-`llm_request_id` scripted successes/failures, concurrent isolation, no payload logs.

Exact external LLM replay for simulation requires **recorded responses or deterministic stubs**. Local seed derivation alone is not enough.

## Logging policy

Logger: `llm.openai_compatible` (stdlib). Prompt loader may emit DEBUG reason codes only.

| Level | Events |
| --- | --- |
| DEBUG | start / attempt / retry metadata |
| INFO | success metadata (safe usage names, finish reason, attempts) |
| WARNING | retryable safe codes |
| ERROR | terminal safe codes |

**Forbidden in every log level:** endpoint URLs, credentials, headers, prompts, rendered text, schemas, validated outputs, agent IDs as free-form dumps, upstream free-form metadata, exception text, `exc_info` on provider failures.

## See also

- [Architecture](architecture.md)
- [Cognition and agent runtime](cognition-runtime.md)
- [Memory reconstruction](memory-reconstruction.md)
- [Configuration](configuration.md)
- [Development](development.md)
