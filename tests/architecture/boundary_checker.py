"""Focused AST checker for Palimpsest bounded-context dependency rules.

These checks prevent accidental dependency violations, not hostile
reflective Python. Successful runs emit no output.
"""

from __future__ import annotations

import ast
import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

LOGGER = logging.getLogger("palimpsest.architecture")

BOUNDED_PACKAGES: Final[frozenset[str]] = frozenset(
    {
        "world",
        "agents",
        "memory",
        "social",
        "llm",
        "simulation",
        "api",
        "analysis",
        "infrastructure",
    }
)

BOUNDED_LAYERS: Final[tuple[str, ...]] = (
    "world",
    "agents",
    "agents.cognition",
    "memory",
    "social",
    "llm",
    "simulation",
    "api",
    "analysis",
    "infrastructure",
)

ALLOWED_IMPORTS: Final[dict[str, frozenset[str]]] = {
    "world": frozenset(),
    "agents": frozenset({"world"}),
    "agents.cognition": frozenset({"world", "agents", "memory", "social", "llm"}),
    "memory": frozenset({"world", "agents"}),
    "social": frozenset({"world", "agents"}),
    "llm": frozenset(),
    "simulation": frozenset(
        {"world", "agents", "agents.cognition", "memory", "social", "llm"}
    ),
    "api": frozenset({"simulation", "infrastructure"}),
    "analysis": frozenset({"world", "simulation"}),
    "infrastructure": frozenset(),
}

PRIVATE_WORLD_MODULES: Final[frozenset[str]] = frozenset(
    {"world._state", "world._transitions", "world._operations"}
)
PRIVATE_WORLD_IMPORTERS: Final[frozenset[str]] = frozenset(
    {
        "world._state",
        "world._transitions",
        "world._operations",
        "simulation",
    }
)
RNG_ADAPTER_MODULE: Final[str] = "simulation.randomness"

FASTAPI_STACK: Final[frozenset[str]] = frozenset({"fastapi", "starlette", "uvicorn"})
ORM_STACK: Final[frozenset[str]] = frozenset({"sqlalchemy", "alembic", "asyncpg"})
PROVIDER_SDKS: Final[frozenset[str]] = frozenset(
    {
        "openai",
        "anthropic",
        "groq",
        "mistralai",
        "cohere",
        "litellm",
        "langchain",
        "llama_index",
        "crewai",
        "autogen",
    }
)
FORBIDDEN_RANDOM_FUNCS: Final[frozenset[str]] = frozenset(
    {
        "seed",
        "random",
        "randint",
        "randrange",
        "choice",
        "choices",
        "sample",
        "shuffle",
        "uniform",
        "gauss",
        "normalvariate",
        "expovariate",
        "vonmisesvariate",
        "gammavariate",
        "betavariate",
        "paretovariate",
        "weibullvariate",
        "triangular",
        "lognormvariate",
        "getrandbits",
        "randbytes",
        "SystemRandom",
    }
)
CLOCK_NAMES: Final[frozenset[str]] = frozenset(
    {"now", "utcnow", "today", "time", "monotonic", "time_ns", "monotonic_ns"}
)
UUID_FACTORY_NAMES: Final[frozenset[str]] = frozenset({"uuid1", "uuid4"})
DOMAIN_LAYERS: Final[frozenset[str]] = frozenset(
    {
        "world",
        "agents",
        "agents.cognition",
        "memory",
        "social",
        "llm",
        "simulation",
        "analysis",
    }
)


@dataclass(frozen=True)
class BoundaryViolation:
    """A single architecture rule failure with source location."""

    rule: str
    source_module: str
    imported_target: str
    file: Path
    line: int
    message: str

    def format(self) -> str:
        return (
            f"{self.file}:{self.line}: [{self.rule}] {self.source_module} -> "
            f"{self.imported_target}: {self.message}"
        )


def layer_of(module: str) -> str | None:
    """Return the bounded layer for ``module``, or None if it is outside the graph."""
    if module == "agents.cognition" or module.startswith("agents.cognition."):
        return "agents.cognition"
    root = module.split(".", 1)[0]
    if root in ALLOWED_IMPORTS and root != "agents":
        return root
    if root == "agents":
        return "agents"
    return None


def is_private_module(module: str) -> bool:
    return any(
        part.startswith("_") and part != "__init__" for part in module.split(".")
    )


def check_tree(src_root: Path) -> list[BoundaryViolation]:
    """Check every Python module under ``src_root`` against the dependency rules."""
    violations: list[BoundaryViolation] = []
    edges: dict[str, set[str]] = {layer: set() for layer in ALLOWED_IMPORTS}
    files = tuple(_iter_python_files(src_root))
    for path in files:
        module = _module_name(src_root, path)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        visitor = _ModuleVisitor(src_root=src_root, path=path, module=module)
        visitor.visit(tree)
        for source_layer, target_layer in visitor.layer_edges:
            edges[source_layer].add(target_layer)
        violations.extend(visitor.violations)
    violations.extend(_cycles(src_root, edges))
    LOGGER.debug(
        "architecture check %s",
        "failed" if violations else "passed",
        extra={"root": str(src_root), "violations": len(violations)},
    )
    return violations


def format_violations(violations: Iterable[BoundaryViolation]) -> str:
    return "\n".join(item.format() for item in violations)


def _iter_python_files(src_root: Path) -> Iterator[Path]:
    for path in sorted(src_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _module_name(src_root: Path, path: Path) -> str:
    relative = path.relative_to(src_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


class _ModuleVisitor(ast.NodeVisitor):
    def __init__(self, *, src_root: Path, path: Path, module: str) -> None:
        self.src_root = src_root
        self.path = path
        self.module = module
        self.layer = layer_of(module)
        self.violations: list[BoundaryViolation] = []
        self._random_module_aliases: set[str] = set()
        self._random_func_aliases: set[str] = set()
        self._datetime_aliases: set[str] = set()
        self._time_aliases: set[str] = set()
        self._uuid_module_aliases: set[str] = set()
        self._uuid_func_aliases: set[str] = set()
        self._clock_func_aliases: set[str] = set()
        self._public_all: set[str] = set()
        self.layer_edges: set[tuple[str, str]] = set()

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                self._public_all.update(_string_list(node.value))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (
            isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
            and node.value
        ):
            self._public_all.update(_string_list(node.value))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            imported = alias.name
            bound = alias.asname or imported.split(".", 1)[0]
            self._register_stdlib_alias(imported, bound)
            self._check_import(imported, node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None and node.level == 0:
            return
        resolved = self._resolve_from_module(node)
        if node.module == "random" and node.level == 0:
            self._handle_random_from_import(node)
        if node.module in {"datetime", "time", "uuid"} and node.level == 0:
            self._handle_clock_from_import(node)
        if any(alias.name == "*" for alias in node.names):
            self._check_import(resolved, node.lineno)
            if resolved == "random" or resolved.startswith("random."):
                self._add(
                    "nondeterministic-call",
                    resolved,
                    node.lineno,
                    "star-import of random is forbidden",
                )
            return
        for alias in node.names:
            imported = f"{resolved}.{alias.name}" if resolved else alias.name
            self._check_import(imported, node.lineno)
            if self._is_public_facade() and (
                resolved in PRIVATE_WORLD_MODULES or alias.name.startswith("_")
            ):
                self._add(
                    "private-reexport",
                    imported,
                    node.lineno,
                    "public facade must not re-export private authority names",
                )
            if alias.name in self._public_all and is_private_module(resolved):
                self._add(
                    "private-reexport",
                    imported,
                    node.lineno,
                    f"{alias.name!r} listed in __all__ from private {resolved}",
                )

    def visit_Call(self, node: ast.Call) -> None:
        self._check_call(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_defaults(node.args)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_defaults(node.args)
        self.generic_visit(node)

    def _check_defaults(self, args: ast.arguments) -> None:
        for default in [*args.defaults, *args.kw_defaults]:
            if default is None:
                continue
            if isinstance(default, ast.Call):
                self._check_call(default)

    def _check_call(self, node: ast.Call) -> None:
        func = node.func
        if self.layer not in DOMAIN_LAYERS:
            self._check_default_factory(node)
            return
        if isinstance(func, ast.Name):
            if func.id in self._random_func_aliases:
                self._add(
                    "nondeterministic-call",
                    func.id,
                    node.lineno,
                    "global random function calls are forbidden",
                )
            if func.id in self._uuid_func_aliases:
                self._add(
                    "nondeterministic-call",
                    func.id,
                    node.lineno,
                    "UUID factories cannot provide domain identifiers",
                )
            if func.id in self._clock_func_aliases:
                self._add(
                    "nondeterministic-call",
                    func.id,
                    node.lineno,
                    "wall-clock values cannot default or stamp domain contracts",
                )
        if isinstance(func, ast.Attribute):
            chain = _attr_chain(func)
            if chain is not None:
                head = chain[0]
                tail = chain[-1]
                dotted = ".".join(chain)
                if head in self._random_module_aliases and (
                    tail in FORBIDDEN_RANDOM_FUNCS
                ):
                    self._add(
                        "nondeterministic-call",
                        dotted,
                        node.lineno,
                        "global random module functions are forbidden; "
                        "use random.Random",
                    )
                if head in self._datetime_aliases and tail in CLOCK_NAMES:
                    self._add(
                        "nondeterministic-call",
                        dotted,
                        node.lineno,
                        "wall-clock values cannot default or stamp domain contracts",
                    )
                if head in self._time_aliases and tail in CLOCK_NAMES:
                    self._add(
                        "nondeterministic-call",
                        dotted,
                        node.lineno,
                        "wall-clock values cannot default or stamp domain contracts",
                    )
                if head in self._uuid_module_aliases and tail in UUID_FACTORY_NAMES:
                    self._add(
                        "nondeterministic-call",
                        dotted,
                        node.lineno,
                        "UUID factories cannot provide domain identifiers",
                    )
        self._check_default_factory(node)

    def _check_default_factory(self, node: ast.Call) -> None:
        if self.layer not in DOMAIN_LAYERS:
            return
        for keyword in node.keywords:
            if keyword.arg != "default_factory" or keyword.value is None:
                continue
            value = keyword.value
            name = _dotted_name(value)
            if name is None:
                continue
            tail = name.rsplit(".", 1)[-1]
            forbidden = UUID_FACTORY_NAMES | CLOCK_NAMES | FORBIDDEN_RANDOM_FUNCS
            if tail in forbidden:
                self._add(
                    "nondeterministic-call",
                    name,
                    node.lineno,
                    "nondeterministic default_factory is forbidden in domain contracts",
                )

    def _register_stdlib_alias(self, imported: str, bound: str) -> None:
        root = imported.split(".", 1)[0]
        if root == "random":
            self._random_module_aliases.add(bound)
        elif root == "datetime":
            self._datetime_aliases.add(bound)
        elif root == "time":
            self._time_aliases.add(bound)
        elif root == "uuid":
            self._uuid_module_aliases.add(bound)

    def _handle_random_from_import(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            bound = alias.asname or alias.name
            if alias.name == "Random":
                continue
            if alias.name in FORBIDDEN_RANDOM_FUNCS or alias.name == "*":
                self._random_func_aliases.add(bound)

    def _handle_clock_from_import(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            bound = alias.asname or alias.name
            if module == "datetime":
                self._datetime_aliases.add(bound)
                if alias.name in CLOCK_NAMES:
                    self._clock_func_aliases.add(bound)
            elif module == "time":
                self._time_aliases.add(bound)
                if alias.name in CLOCK_NAMES:
                    self._clock_func_aliases.add(bound)
            elif module == "uuid":
                self._uuid_module_aliases.add(bound)
                if alias.name in UUID_FACTORY_NAMES:
                    self._uuid_func_aliases.add(bound)

    def _resolve_from_module(self, node: ast.ImportFrom) -> str:
        module = node.module or ""
        if node.level == 0:
            return module
        parts = self.module.split(".")
        package_parts = parts if self.path.name == "__init__.py" else parts[:-1]
        climb = node.level - 1
        if climb:
            package_parts = package_parts[: max(0, len(package_parts) - climb)]
        prefix = ".".join(package_parts)
        if module:
            return f"{prefix}.{module}" if prefix else module
        return prefix

    def _is_public_facade(self) -> bool:
        return self.path.name == "__init__.py" and not is_private_module(self.module)

    def _check_import(self, imported: str, line: int) -> None:
        if not imported:
            return
        root = imported.split(".", 1)[0]
        if root == "random":
            self._check_random_import(imported, line)
        self._check_framework(imported, line)
        imported_layer = layer_of(imported)
        if imported_layer is not None and self.layer is not None:
            if imported_layer != self.layer:
                self.layer_edges.add((self.layer, imported_layer))
        if imported_layer is None or self.layer is None:
            return
        if imported_layer == self.layer and not imported.startswith("agents.cognition"):
            self._check_private_world(imported, line)
            return
        if self.layer == "agents" and imported_layer == "agents.cognition":
            self._add(
                "agents-cognition-boundary",
                imported,
                line,
                "base agents modules must not import agents.cognition",
            )
            return
        allowed = ALLOWED_IMPORTS.get(self.layer, frozenset())
        if imported_layer != self.layer and imported_layer not in allowed:
            self._add(
                "import-allowlist",
                imported,
                line,
                f"layer {self.layer!r} may not import {imported_layer!r}",
            )
        self._check_private_world(imported, line)
        self._check_cross_package_private(imported, line)

    def _check_random_import(self, imported: str, line: int) -> None:
        self._random_module_aliases.add("random")
        if self.module != RNG_ADAPTER_MODULE and not self.module.startswith(
            f"{RNG_ADAPTER_MODULE}."
        ):
            self._add(
                "nondeterministic-call",
                imported,
                line,
                "direct random use is restricted to simulation.randomness",
            )

    def _check_framework(self, imported: str, line: int) -> None:
        root = imported.split(".", 1)[0]
        if root in FASTAPI_STACK and self.layer != "api":
            self._add(
                "framework-leakage",
                imported,
                line,
                "FastAPI/Starlette/Uvicorn may only be imported by api",
            )
        if root in ORM_STACK and self.layer != "infrastructure":
            self._add(
                "framework-leakage",
                imported,
                line,
                "SQLAlchemy/Alembic/asyncpg may only be imported by infrastructure",
            )
        if root in PROVIDER_SDKS:
            self._add(
                "provider-sdk",
                imported,
                line,
                "LLM provider SDKs are forbidden; llm must stay provider-neutral",
            )

    def _check_private_world(self, imported: str, line: int) -> None:
        target = _private_world_target(imported)
        if target is None:
            return
        if not _importer_may_use_private_world(self.module):
            self._add(
                "private-world-authority",
                imported,
                line,
                "only simulation and private world modules may import authority APIs",
            )

    def _check_cross_package_private(self, imported: str, line: int) -> None:
        imported_layer = layer_of(imported)
        if imported_layer is None or imported_layer == self.layer:
            return
        if not is_private_module(imported):
            return
        if _private_world_target(imported) is not None:
            return
        self._add(
            "public-facade",
            imported,
            line,
            "cross-module imports must target public facade modules or __all__ names",
        )

    def _add(self, rule: str, imported: str, line: int, message: str) -> None:
        self.violations.append(
            BoundaryViolation(
                rule=rule,
                source_module=self.module,
                imported_target=imported,
                file=self.path,
                line=line,
                message=message,
            )
        )


def _private_world_target(imported: str) -> str | None:
    for private in PRIVATE_WORLD_MODULES:
        if imported == private or imported.startswith(f"{private}."):
            return private
    return None


def _importer_may_use_private_world(module: str) -> bool:
    if module in PRIVATE_WORLD_MODULES:
        return True
    if (
        module.startswith("world._state.")
        or module.startswith("world._transitions.")
        or module.startswith("world._operations.")
    ):
        return True
    return layer_of(module) == "simulation"


def _string_list(node: ast.AST) -> set[str]:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: set[str] = set()
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                values.add(elt.value)
        return values
    return set()


def _dotted_name(node: ast.AST) -> str | None:
    chain = _attr_chain(node)
    if chain is None:
        return None
    return ".".join(chain)


def _attr_chain(node: ast.AST) -> list[str] | None:
    if isinstance(node, ast.Name):
        return [node.id]
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        parts.reverse()
        return parts
    return None


def _cycles(src_root: Path, edges: dict[str, set[str]]) -> list[BoundaryViolation]:
    violations: list[BoundaryViolation] = []
    visited: set[str] = set()
    stack: list[str] = []
    on_stack: set[str] = set()

    def visit(node: str) -> None:
        visited.add(node)
        stack.append(node)
        on_stack.add(node)
        for nxt in sorted(edges.get(node, ())):
            if nxt not in visited:
                visit(nxt)
            elif nxt in on_stack:
                cycle = [*stack[stack.index(nxt) :], nxt]
                chain = " -> ".join(cycle)
                violations.append(
                    BoundaryViolation(
                        rule="cycle",
                        source_module=cycle[0],
                        imported_target=chain,
                        file=src_root,
                        line=1,
                        message=f"bounded-package cycle {chain}",
                    )
                )
        stack.pop()
        on_stack.remove(node)

    for layer in sorted(edges):
        if layer not in visited:
            visit(layer)
    return violations
