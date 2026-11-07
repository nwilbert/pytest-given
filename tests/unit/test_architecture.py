"""The dependency direction AGENTS.md documents, held to the imports."""

import ast
import importlib
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import NamedTuple

import pytest

import pytest_given

PACKAGE = 'pytest_given'
PACKAGE_ROOT = Path(pytest_given.__file__).parent

LEAVES = frozenset({'markdown', 'git'})
LIBRARY = LEAVES | {
    'model',
    'capture',
    'lint',
    'report',
    'grouping',
    'delta',
    'citations',
}
# Each subpackage, and the subpackages it may import.
ALLOWED: dict[str, frozenset[str]] = {
    'markdown': frozenset(),
    'git': frozenset(),
    'model': LEAVES,
    'capture': LEAVES | {'model'},
    'lint': LEAVES | {'model'},
    'report': LEAVES | {'model'},
    'grouping': LEAVES | {'model', 'capture'},
    'delta': LEAVES | {'model'},
    'citations': LEAVES | {'model', 'report'},
    'plugin': LIBRARY,
    'cli': LIBRARY,
}
PYTEST_MODULES = frozenset({'pytest', '_pytest', 'pluggy'})


class Import(NamedTuple):
    source: Path
    line: int
    # The imported module, dotted and absolute.
    target: str
    in_function: bool

    @property
    def source_package(self) -> str:
        """The subpackage importing, `''` for the package root's own module."""
        parts = self.source.relative_to(PACKAGE_ROOT).parts
        return parts[0] if len(parts) > 1 else ''

    @property
    def target_parts(self) -> tuple[str, ...]:
        """The target below the package, empty for a third-party module."""
        head, *rest = self.target.split('.')
        return tuple(rest) if head == PACKAGE else ()

    def __str__(self) -> str:
        relative = self.source.relative_to(PACKAGE_ROOT).as_posix()
        return f'{relative}:{self.line} imports {self.target}'


def test_the_direction_names_every_subpackage() -> None:
    subpackages = {path.parent.name for path in PACKAGE_ROOT.glob('*/__init__.py')}
    assert subpackages == set(ALLOWED)


def test_a_subpackage_imports_only_what_the_direction_allows() -> None:
    violations = [
        str(found)
        for found in _imports()
        if found.source_package
        and found.target_parts
        and found.target_parts[0] != found.source_package
        and found.target_parts[0] not in ALLOWED[found.source_package]
    ]
    assert violations == []


def test_another_subpackage_is_imported_through_its_root() -> None:
    violations = [
        str(found)
        for found in _imports()
        if len(found.target_parts) > 1 and found.target_parts[0] != found.source_package
    ]
    assert violations == []


def test_imports_inside_the_package_are_relative() -> None:
    violations = [
        str(found)
        for found in _imports(relative=False)
        if found.target.split('.')[0] == PACKAGE
    ]
    assert violations == []


def test_every_import_is_module_level() -> None:
    violations = [
        str(found)
        for found in (*_imports(), *_imports(relative=False))
        if found.in_function
    ]
    assert violations == []


def test_only_the_plugin_imports_pytest() -> None:
    violations = [
        str(found)
        for found in _imports(relative=False)
        if found.target.split('.')[0] in PYTEST_MODULES
        and found.source_package != 'plugin'
    ]
    assert violations == []


@pytest.mark.parametrize(
    ('statement', 'targets'),
    [
        ('from .. import report', ['pytest_given.report']),
        ('from ..report import emit_sinks', ['pytest_given.report']),
        ('from ..report import slugs', ['pytest_given.report.slugs']),
        ('from ..report import link_text', ['pytest_given.report']),
        (
            'from ..report import emit_sinks, slugs',
            ['pytest_given.report', 'pytest_given.report.slugs'],
        ),
        ('from .catalog import Rule', ['pytest_given.lint.catalog']),
    ],
)
def test_an_imported_name_that_is_a_module_is_its_own_target(
    statement: str, targets: list[str]
) -> None:
    node = ast.parse(statement).body[0]
    assert isinstance(node, ast.ImportFrom)
    assert _targets(PACKAGE_ROOT / 'lint' / 'runner.py', node) == targets


def _imports(*, relative: bool = True) -> list[Import]:
    """Every relative import in the package, or every absolute one."""
    return [found for found, is_relative in _all_imports() if is_relative == relative]


@cache
def _all_imports() -> list[tuple[Import, bool]]:
    found: list[tuple[Import, bool]] = []
    for source in sorted(PACKAGE_ROOT.rglob('*.py')):
        tree = ast.parse(source.read_text(encoding='utf-8'))
        for node, in_function in _import_nodes(tree, in_function=False):
            is_relative = isinstance(node, ast.ImportFrom) and node.level > 0
            found.extend(
                (Import(source, node.lineno, target, in_function), is_relative)
                for target in _targets(source, node)
            )
    return found


def _import_nodes(
    node: ast.AST, *, in_function: bool
) -> Iterator[tuple[ast.Import | ast.ImportFrom, bool]]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Import | ast.ImportFrom):
            yield child, in_function
        else:
            scoped = isinstance(
                child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            )
            yield from _import_nodes(child, in_function=in_function or scoped)


def _targets(source: Path, node: ast.Import | ast.ImportFrom) -> list[str]:
    """Each imported module. A from-import's name that is a module of the
    package is a target of its own, as `from .. import report` and
    `from ..report import slugs` import that module."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if node.level == 0:
        assert node.module is not None
        module = node.module
    else:
        package = [PACKAGE, *source.relative_to(PACKAGE_ROOT).parent.parts]
        base = package[: len(package) - (node.level - 1)]
        module = '.'.join([*base, *([node.module] if node.module else [])])
    return list(
        dict.fromkeys(
            f'{module}.{alias.name}'
            if _imports_a_submodule(module, alias.name)
            else module
            for alias in node.names
        )
    )


def _imports_a_submodule(module: str, name: str) -> bool:
    """As Python resolves it: the package's own attribute first, so
    `from ..report import link_text` takes the function `report` exports
    under its module's name."""
    if f'{module}.{name}' not in _package_modules():
        return False
    attribute = getattr(importlib.import_module(module), name, None)
    return attribute is None or isinstance(attribute, ModuleType)


@cache
def _package_modules() -> frozenset[str]:
    """Named as written, since a case-insensitive filesystem would also find
    `capture/glossary.py` under the name `Glossary`."""
    modules: set[str] = set()
    for source in PACKAGE_ROOT.rglob('*.py'):
        parts = source.relative_to(PACKAGE_ROOT).with_suffix('').parts
        if parts[-1] == '__init__':
            parts = parts[:-1]
        modules.add('.'.join([PACKAGE, *parts]))
    return frozenset(modules)
