"""Versioned prompt resources: digests, substitution safety, and logging hygiene."""

from __future__ import annotations

import hashlib
import logging
from importlib.resources import files

import pytest

from llm import (
    LLMMessage,
    LoadedPrompt,
    MessageRole,
    PromptError,
    PromptReason,
    PromptReference,
    RenderedPrompt,
    canonical_rendered_digest,
    load_prompt,
    render_prompt,
)

pytestmark = pytest.mark.unit

# Pinned resource digests for structured/v1 templates (raw file bytes).
SYSTEM_TEMPLATE_SHA256 = (
    "28e6bb3d869577c566c2529fad0ae3b12523d3de25626f6f252e7cd7cfe10d2e"
)
USER_TEMPLATE_SHA256 = (
    "aa34bb53fb7082d83926ff26feafd31e0318aac665de56c0c7a2221ae28b8203"
)
MANIFEST_SHA256 = "e0bf751f0715efb6dd05f8200b2689fb78401b969129b09d894610c6583414f7"

# Pinned rendered digest for the fixture variables below.
RENDERED_DIGEST = "26e60c89663b03524ee2fff94428f9e0e4383adb82927fd65aaa4f543692f856"

_FIXTURE_VARIABLES = {
    "schema_name": "Decision",
    "schema_json": (
        '{"type":"object","properties":{"kind":{"type":"string"}},'
        '"required":["kind"],"additionalProperties":false}'
    ),
    "request": "Choose the next action kind.",
}


def test_v1_resource_digests_are_pinned() -> None:
    root = files("llm.prompts").joinpath("structured", "v1")
    assert (
        hashlib.sha256(root.joinpath("system.txt").read_bytes()).hexdigest()
        == SYSTEM_TEMPLATE_SHA256
    )
    assert (
        hashlib.sha256(root.joinpath("user.txt").read_bytes()).hexdigest()
        == USER_TEMPLATE_SHA256
    )
    assert (
        hashlib.sha256(root.joinpath("manifest.json").read_bytes()).hexdigest()
        == MANIFEST_SHA256
    )


def test_load_and_render_structured_v1() -> None:
    loaded = load_prompt("structured", "v1")
    assert isinstance(loaded, LoadedPrompt)
    assert loaded.name == "structured"
    assert loaded.version == "v1"
    assert loaded.variables == ("schema_name", "schema_json", "request")
    assert tuple(entry.sha256 for entry in loaded.templates) == (
        SYSTEM_TEMPLATE_SHA256,
        USER_TEMPLATE_SHA256,
    )

    rendered = render_prompt("structured", "v1", _FIXTURE_VARIABLES)
    assert isinstance(rendered, RenderedPrompt)
    assert rendered.reference == PromptReference(
        name="structured", version="v1", digest=RENDERED_DIGEST
    )
    assert rendered.reference.digest == RENDERED_DIGEST
    assert len(rendered.messages) == 2
    assert rendered.messages[0] == LLMMessage(
        role=MessageRole.SYSTEM,
        content=(
            "You are a structured JSON generation assistant.\n"
            "Return exactly one JSON object that conforms to the provided schema.\n"
            "Do not include markdown fences, commentary, or trailing text."
        ),
    )
    assert rendered.messages[1].role is MessageRole.USER
    assert "Decision" in rendered.messages[1].content
    assert "Choose the next action kind." in rendered.messages[1].content
    assert "cognition" not in rendered.messages[0].content.lower()
    assert "policy" not in rendered.messages[0].content.lower()


def test_canonical_rendered_digest_matches_reference() -> None:
    rendered = render_prompt("structured", "v1", _FIXTURE_VARIABLES)
    recomputed = canonical_rendered_digest(
        rendered.reference.name,
        rendered.reference.version,
        tuple((message.role.value, message.content) for message in rendered.messages),
    )
    assert recomputed == RENDERED_DIGEST == rendered.reference.digest


@pytest.mark.parametrize(
    ("name", "version", "reason"),
    [
        ("../structured", "v1", PromptReason.INVALID_NAME),
        ("structured/v1", "v1", PromptReason.INVALID_NAME),
        ("structured", "../v1", PromptReason.INVALID_VERSION),
        ("structured", "v1/../../x", PromptReason.INVALID_VERSION),
        (".", "v1", PromptReason.INVALID_NAME),
        ("structured", "..", PromptReason.INVALID_VERSION),
        ("missing", "v1", PromptReason.PROMPT_NOT_FOUND),
        ("structured", "v9", PromptReason.PROMPT_NOT_FOUND),
    ],
)
def test_rejects_unsafe_or_unknown_prompt_identity(
    name: str, version: str, reason: PromptReason
) -> None:
    with pytest.raises(PromptError) as captured:
        load_prompt(name, version)
    assert captured.value.reason is reason
    assert name not in str(captured.value)
    assert name not in repr(captured.value)


@pytest.mark.parametrize(
    ("variables", "reason"),
    [
        (
            {"schema_name": "Decision", "schema_json": "{}"},
            PromptReason.MISSING_VARIABLE,
        ),
        (
            {
                "schema_name": "Decision",
                "schema_json": "{}",
                "request": "x",
                "extra": "y",
            },
            PromptReason.UNEXPECTED_VARIABLE,
        ),
        (
            {
                "schema_name": "Decision",
                "schema_json": "{}",
                "request": 1,
            },
            PromptReason.NON_STRING_VARIABLE,
        ),
    ],
)
def test_render_rejects_variable_set_problems(
    variables: dict[str, object], reason: PromptReason
) -> None:
    with pytest.raises(PromptError) as captured:
        render_prompt("structured", "v1", variables)
    assert captured.value.reason is reason
    assert "Decision" not in str(captured.value)
    assert "Decision" not in repr(captured.value)


def test_errors_never_include_variable_values() -> None:
    secret = "super-secret-schema-body"
    with pytest.raises(PromptError) as captured:
        render_prompt(
            "structured",
            "v1",
            {
                "schema_name": "Decision",
                "schema_json": secret,
                "request": secret,
                "extra": secret,
            },
        )
    assert captured.value.reason is PromptReason.UNEXPECTED_VARIABLE
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)


def test_logging_allows_only_trusted_metadata(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="llm.prompts")
    render_prompt("structured", "v1", _FIXTURE_VARIABLES)
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "structured" in text
    assert "v1" in text
    assert RENDERED_DIGEST in text
    assert _FIXTURE_VARIABLES["schema_json"] not in text
    assert "Choose the next action kind." not in text
    assert "{{" not in text


def test_logging_omits_invalid_caller_names(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="llm.prompts")
    invalid = "../etc/passwd"
    with pytest.raises(PromptError) as captured:
        load_prompt(invalid, "v1")
    assert captured.value.reason is PromptReason.INVALID_NAME
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "invalid_name" in text
    assert invalid not in text
    assert "passwd" not in text


def test_public_exports_available_from_llm_package() -> None:
    assert callable(load_prompt)
    assert callable(render_prompt)
    assert callable(canonical_rendered_digest)
    assert PromptReason.DIGEST_MISMATCH.value == "digest_mismatch"
