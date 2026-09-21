"""Immutable package-resource prompt loading and safe rendering.

Prompts are versioned package data under ``llm.prompts``. Loading verifies
manifest integrity and template digests. Rendering substitutes only declared
string variables and produces Task 1 message/prompt-reference contracts.

Logging emits only trusted prompt name/version/digest and stable reason codes.
Templates, rendered text, variables, schemas, and invalid caller names are
never logged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import abc as resources_abc
from importlib.resources import files
from typing import Final, NoReturn

from llm.models import LLMMessage, MessageRole, PromptReference

__all__ = [
    "LoadedPrompt",
    "PromptError",
    "PromptReason",
    "PromptTemplate",
    "RenderedPrompt",
    "canonical_rendered_digest",
    "load_prompt",
    "render_prompt",
]

_LOG: Final[logging.Logger] = logging.getLogger("llm.prompts")

_MAX_SEGMENT_CHARS: Final[int] = 64
_SAFE_SEGMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
)
_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(r"\{\{([^{}]*)\}\}")
_MANIFEST_KEYS: Final[frozenset[str]] = frozenset(
    {"name", "version", "messages", "variables"}
)
_MESSAGE_KEYS: Final[frozenset[str]] = frozenset({"role", "template", "sha256"})
_ROLE_BY_VALUE: Final[dict[str, MessageRole]] = {
    MessageRole.SYSTEM.value: MessageRole.SYSTEM,
    MessageRole.USER.value: MessageRole.USER,
}
_RENDER_DOMAIN: Final[bytes] = b"llm.prompt.rendered.v1"


class PromptReason(StrEnum):
    """Stable validation failure codes for prompt loading and rendering."""

    INVALID_NAME = "invalid_name"
    INVALID_VERSION = "invalid_version"
    PROMPT_NOT_FOUND = "prompt_not_found"
    MANIFEST_INVALID = "manifest_invalid"
    UNKNOWN_FIELD = "unknown_field"
    DUPLICATE_ROLE = "duplicate_role"
    MISSING_RESOURCE = "missing_resource"
    DIGEST_MISMATCH = "digest_mismatch"
    ENCODING_INVALID = "encoding_invalid"
    NEWLINE_POLICY = "newline_policy"
    MISSING_VARIABLE = "missing_variable"
    UNEXPECTED_VARIABLE = "unexpected_variable"
    NON_STRING_VARIABLE = "non_string_variable"
    MALFORMED_PLACEHOLDER = "malformed_placeholder"
    UNRESOLVED_PLACEHOLDER = "unresolved_placeholder"
    INVALID_ROLE = "invalid_role"


class PromptError(Exception):
    """Safe prompt validation failure with a stable reason code only."""

    def __init__(self, reason: PromptReason) -> None:
        if not isinstance(reason, PromptReason):
            raise TypeError("reason must be PromptReason")
        self.reason = reason
        super().__init__(reason.value)
        self.__cause__ = None
        self.__context__ = None
        self.__suppress_context__ = True

    def __repr__(self) -> str:
        return f"PromptError(reason={self.reason.value!r})"


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """One verified role/template pair from a prompt manifest."""

    role: MessageRole
    template_name: str
    sha256: str
    text: str

    def __repr__(self) -> str:
        return (
            "PromptTemplate("
            f"role={self.role.value!r}, template_name={self.template_name!r}, "
            f"sha256={self.sha256!r})"
        )


@dataclass(frozen=True, slots=True)
class LoadedPrompt:
    """Verified prompt resources ready for safe variable substitution."""

    name: str
    version: str
    variables: tuple[str, ...]
    templates: tuple[PromptTemplate, ...]

    def __repr__(self) -> str:
        return (
            "LoadedPrompt("
            f"name={self.name!r}, version={self.version!r}, "
            f"variables={len(self.variables)}, templates={len(self.templates)})"
        )


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    """Deterministic messages plus prompt identity after substitution."""

    messages: tuple[LLMMessage, ...]
    reference: PromptReference

    def __repr__(self) -> str:
        return (
            "RenderedPrompt("
            f"name={self.reference.name!r}, version={self.reference.version!r}, "
            f"digest={self.reference.digest!r}, messages={len(self.messages)})"
        )


def _length_prefixed(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def canonical_rendered_digest(
    name: str,
    version: str,
    messages: Sequence[tuple[str, str]],
) -> str:
    """SHA-256 over name, version, ordered roles, and rendered UTF-8 bytes."""
    hasher = hashlib.sha256()
    hasher.update(_length_prefixed(_RENDER_DOMAIN))
    hasher.update(_length_prefixed(name.encode("utf-8")))
    hasher.update(_length_prefixed(version.encode("utf-8")))
    for role, content in messages:
        hasher.update(_length_prefixed(role.encode("utf-8")))
        hasher.update(_length_prefixed(content.encode("utf-8")))
    return hasher.hexdigest()


def _fail(reason: PromptReason, *, trusted_name: str | None = None) -> NoReturn:
    if trusted_name is None:
        _LOG.debug("prompt_validation_failed reason=%s", reason.value)
    else:
        _LOG.debug(
            "prompt_validation_failed reason=%s name=%s",
            reason.value,
            trusted_name,
        )
    raise PromptError(reason)


def _require_segment(value: object, reason: PromptReason) -> str:
    if not isinstance(value, str):
        _fail(reason)
    if not value or value.strip() != value or not value.strip():
        _fail(reason)
    if len(value) > _MAX_SEGMENT_CHARS:
        _fail(reason)
    if _SAFE_SEGMENT_RE.fullmatch(value) is None:
        _fail(reason)
    if value in {".", ".."} or "/" in value or "\\" in value:
        _fail(reason)
    return value


def _require_digest(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"^[a-f0-9]{64}$", value):
        _fail(PromptReason.MANIFEST_INVALID)
    return value


def _prompts_root() -> resources_abc.Traversable:
    return files("llm.prompts")


def _read_bytes(resource: resources_abc.Traversable) -> bytes:
    try:
        return resource.read_bytes()
    except (FileNotFoundError, IsADirectoryError, OSError, PermissionError):
        _fail(PromptReason.MISSING_RESOURCE)


def _decode_template(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail(PromptReason.ENCODING_INVALID)
    if "\r" in text:
        _fail(PromptReason.NEWLINE_POLICY)
    if not text.endswith("\n"):
        _fail(PromptReason.NEWLINE_POLICY)
    # File policy requires a final newline; message content cannot carry it.
    return text[:-1]


def _parse_manifest(raw: bytes) -> dict[str, object]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail(PromptReason.ENCODING_INVALID)
    if "\r" in text:
        _fail(PromptReason.NEWLINE_POLICY)
    if not text.endswith("\n"):
        _fail(PromptReason.NEWLINE_POLICY)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        _fail(PromptReason.MANIFEST_INVALID)
    if not isinstance(payload, dict):
        _fail(PromptReason.MANIFEST_INVALID)
    return payload


def load_prompt(name: str, version: str) -> LoadedPrompt:
    """Load and verify a versioned prompt from package resources."""
    # Reject traversal/malformed segments before any filesystem join.
    safe_name = _require_segment(name, PromptReason.INVALID_NAME)
    safe_version = _require_segment(version, PromptReason.INVALID_VERSION)

    root = _prompts_root().joinpath(safe_name, safe_version)
    manifest_path = root.joinpath("manifest.json")
    if not manifest_path.is_file():
        _fail(PromptReason.PROMPT_NOT_FOUND)

    payload = _parse_manifest(_read_bytes(manifest_path))
    unknown = set(payload) - _MANIFEST_KEYS
    if unknown:
        _fail(PromptReason.UNKNOWN_FIELD, trusted_name=safe_name)
    missing = _MANIFEST_KEYS - set(payload)
    if missing:
        _fail(PromptReason.MANIFEST_INVALID, trusted_name=safe_name)

    manifest_name = _require_segment(payload["name"], PromptReason.MANIFEST_INVALID)
    manifest_version = _require_segment(
        payload["version"], PromptReason.MANIFEST_INVALID
    )
    if manifest_name != safe_name or manifest_version != safe_version:
        _fail(PromptReason.MANIFEST_INVALID, trusted_name=safe_name)

    variables_raw = payload["variables"]
    if not isinstance(variables_raw, list) or not variables_raw:
        _fail(PromptReason.MANIFEST_INVALID, trusted_name=safe_name)
    variables: list[str] = []
    seen_vars: set[str] = set()
    for item in variables_raw:
        var = _require_segment(item, PromptReason.MANIFEST_INVALID)
        if var in seen_vars:
            _fail(PromptReason.MANIFEST_INVALID, trusted_name=safe_name)
        seen_vars.add(var)
        variables.append(var)

    messages_raw = payload["messages"]
    if not isinstance(messages_raw, list) or not messages_raw:
        _fail(PromptReason.MANIFEST_INVALID, trusted_name=safe_name)

    templates: list[PromptTemplate] = []
    seen_roles: set[MessageRole] = set()
    for entry in messages_raw:
        if not isinstance(entry, dict):
            _fail(PromptReason.MANIFEST_INVALID, trusted_name=safe_name)
        unknown_entry = set(entry) - _MESSAGE_KEYS
        if unknown_entry:
            _fail(PromptReason.UNKNOWN_FIELD, trusted_name=safe_name)
        if set(entry) != _MESSAGE_KEYS:
            _fail(PromptReason.MANIFEST_INVALID, trusted_name=safe_name)

        role_value = entry["role"]
        if not isinstance(role_value, str) or role_value not in _ROLE_BY_VALUE:
            _fail(PromptReason.INVALID_ROLE, trusted_name=safe_name)
        role = _ROLE_BY_VALUE[role_value]
        if role in seen_roles:
            _fail(PromptReason.DUPLICATE_ROLE, trusted_name=safe_name)
        seen_roles.add(role)

        template_name = _require_segment(
            entry["template"], PromptReason.MANIFEST_INVALID
        )
        if not template_name.endswith(".txt"):
            _fail(PromptReason.MANIFEST_INVALID, trusted_name=safe_name)
        expected_digest = _require_digest(entry["sha256"])

        template_path = root.joinpath(template_name)
        if not template_path.is_file():
            _fail(PromptReason.MISSING_RESOURCE, trusted_name=safe_name)
        raw = _read_bytes(template_path)
        actual_digest = hashlib.sha256(raw).hexdigest()
        if actual_digest != expected_digest:
            _fail(PromptReason.DIGEST_MISMATCH, trusted_name=safe_name)
        text = _decode_template(raw)
        _validate_placeholders(text, frozenset(variables), trusted_name=safe_name)
        templates.append(
            PromptTemplate(
                role=role,
                template_name=template_name,
                sha256=expected_digest,
                text=text,
            )
        )

    loaded = LoadedPrompt(
        name=safe_name,
        version=safe_version,
        variables=tuple(variables),
        templates=tuple(templates),
    )
    _LOG.debug(
        "prompt_loaded name=%s version=%s templates=%s",
        loaded.name,
        loaded.version,
        len(loaded.templates),
    )
    return loaded


def _validate_placeholders(
    text: str, allowed: frozenset[str], *, trusted_name: str
) -> None:
    for match in _PLACEHOLDER_RE.finditer(text):
        inner = match.group(1)
        if _SAFE_SEGMENT_RE.fullmatch(inner) is None:
            _fail(PromptReason.MALFORMED_PLACEHOLDER, trusted_name=trusted_name)
        if inner in {".", ".."} or "/" in inner or "\\" in inner:
            _fail(PromptReason.MALFORMED_PLACEHOLDER, trusted_name=trusted_name)
        if inner not in allowed:
            _fail(PromptReason.MALFORMED_PLACEHOLDER, trusted_name=trusted_name)
    # Reject nested/broken brace forms that are not complete {{name}} tokens.
    if "{{" in text or "}}" in text:
        # After removing valid placeholders, no braces of this form may remain.
        stripped = _PLACEHOLDER_RE.sub("", text)
        if "{{" in stripped or "}}" in stripped:
            _fail(PromptReason.MALFORMED_PLACEHOLDER, trusted_name=trusted_name)


def _substitute(text: str, values: Mapping[str, str], *, trusted_name: str) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            _fail(PromptReason.UNRESOLVED_PLACEHOLDER, trusted_name=trusted_name)
        return values[key]

    rendered = _PLACEHOLDER_RE.sub(replace, text)
    # Values may contain '}}'; only leftover '{{' / '{{...}}' are unresolved.
    if _PLACEHOLDER_RE.search(rendered) is not None or "{{" in rendered:
        _fail(PromptReason.UNRESOLVED_PLACEHOLDER, trusted_name=trusted_name)
    return rendered


def render_prompt(
    name: str,
    version: str,
    variables: Mapping[str, object],
) -> RenderedPrompt:
    """Load a prompt, substitute declared string variables, and build contracts."""
    if not isinstance(variables, Mapping):
        _fail(PromptReason.NON_STRING_VARIABLE)
    loaded = load_prompt(name, version)
    declared = set(loaded.variables)
    provided = set(variables)
    missing = declared - provided
    if missing:
        _fail(PromptReason.MISSING_VARIABLE, trusted_name=loaded.name)
    unexpected = provided - declared
    if unexpected:
        _fail(PromptReason.UNEXPECTED_VARIABLE, trusted_name=loaded.name)

    string_values: dict[str, str] = {}
    for key in loaded.variables:
        value = variables[key]
        if not isinstance(value, str):
            _fail(PromptReason.NON_STRING_VARIABLE, trusted_name=loaded.name)
        string_values[key] = value

    messages: list[LLMMessage] = []
    digest_parts: list[tuple[str, str]] = []
    for entry in loaded.templates:
        content = _substitute(
            entry.text, string_values, trusted_name=loaded.name
        )
        message = LLMMessage(role=entry.role, content=content)
        messages.append(message)
        digest_parts.append((entry.role.value, content))

    digest = canonical_rendered_digest(loaded.name, loaded.version, digest_parts)
    reference = PromptReference(
        name=loaded.name, version=loaded.version, digest=digest
    )
    rendered = RenderedPrompt(messages=tuple(messages), reference=reference)
    _LOG.debug(
        "prompt_rendered name=%s version=%s digest=%s",
        reference.name,
        reference.version,
        reference.digest,
    )
    return rendered
