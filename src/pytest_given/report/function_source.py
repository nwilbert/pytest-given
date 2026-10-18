"""Each scenario's test function, read from disk for `--given-md-source`.

The reading lives here so `render_md` stays a function of its inputs. A file
that can't be read yields a reason in place of the code, never an error: the
source is a review aid, and losing it must not cost the run its report.
"""

import ast
import tokenize
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ..model import NodeId, Scenario


@dataclass(frozen=True)
class FunctionSource:
    first_line: int
    lines: tuple[str, ...]


@dataclass(frozen=True)
class UnreadableSource:
    reason: str


type SourceExcerpt = FunctionSource | UnreadableSource


def read_function_sources(
    scenarios: Iterable[Scenario], root: Path
) -> dict[NodeId, SourceExcerpt]:
    """Every scenario's test function, keyed by scenario id."""
    by_file: dict[str, list[tuple[NodeId, int]]] = defaultdict(list)
    for scenario in scenarios:
        assert scenario.source is not None, 'a live run gives every scenario a source'
        by_file[scenario.source.relpath].append((scenario.id, scenario.source.line))
    excerpts: dict[NodeId, SourceExcerpt] = {}
    for relpath, anchors in by_file.items():
        functions = _functions(root, relpath)
        for scenario_id, line in anchors:
            excerpts[scenario_id] = (
                functions
                if isinstance(functions, UnreadableSource)
                else _innermost(functions, relpath, line)
            )
    return excerpts


def _innermost(
    functions: list[FunctionSource], relpath: str, line: int
) -> SourceExcerpt:
    """The functions holding a line nest, so the shortest is the innermost: a
    test defined inside a helper resolves to the test, not the helper."""
    holding = [
        function
        for function in functions
        if function.first_line <= line < function.first_line + len(function.lines)
    ]
    if not holding:
        return UnreadableSource(reason=f'no function holds {relpath}:{line}')
    return min(holding, key=lambda function: len(function.lines))


def _functions(root: Path, relpath: str) -> list[FunctionSource] | UnreadableSource:
    # `tokenize.open` decodes as Python does, honoring an encoding declaration,
    # and folds every newline to `\n`, the only line break `ast` counts.
    try:
        with tokenize.open(root / relpath) as file:
            text = file.read()
    except OSError, SyntaxError, ValueError:
        return UnreadableSource(reason=f'{relpath} could not be read')
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return UnreadableSource(reason=f'{relpath} does not parse')
    lines = text.split('\n')
    functions: list[FunctionSource] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            assert node.end_lineno is not None, 'ast.parse sets every end position'
            first = min([node.lineno, *(dec.lineno for dec in node.decorator_list)])
            functions.append(
                FunctionSource(
                    first_line=first, lines=tuple(lines[first - 1 : node.end_lineno])
                )
            )
    return functions
