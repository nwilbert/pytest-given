"""Each scenario's test function, read from disk for `--given-md-source`.

The reading lives here so `render_md` stays a function of its inputs. A file
that can't be read yields a reason in place of the code, never an error: the
source is a review aid, and losing it must not cost the run its report.
"""

import ast
import tokenize
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
    """Every scenario's test function, keyed by scenario id, each file read once."""
    files: dict[str, _ParsedFile | UnreadableSource] = {}
    excerpts: dict[NodeId, SourceExcerpt] = {}
    for scenario in scenarios:
        if scenario.source is None:
            excerpts[scenario.id] = UnreadableSource(
                reason='the scenario has no source location'
            )
            continue
        relpath, line = scenario.source.relpath, scenario.source.line
        if relpath not in files:
            files[relpath] = _parse(root / relpath, relpath)
        parsed = files[relpath]
        if isinstance(parsed, UnreadableSource):
            excerpts[scenario.id] = parsed
        else:
            excerpts[scenario.id] = parsed.function_at(line) or UnreadableSource(
                reason=f'no function holds {relpath}:{line}'
            )
    return excerpts


@dataclass(frozen=True)
class _ParsedFile:
    lines: list[str]
    # (first line, last line) of each function, decorators included.
    spans: list[tuple[int, int]]

    def function_at(self, line: int) -> FunctionSource | None:
        """The innermost function holding `line`: a test defined inside a
        helper resolves to the test, not the helper."""
        holding = [(start, end) for start, end in self.spans if start <= line <= end]
        if not holding:
            return None
        start, end = min(holding, key=lambda span: span[1] - span[0])
        return FunctionSource(
            first_line=start, lines=tuple(self.lines[start - 1 : end])
        )


def _parse(path: Path, relpath: str) -> _ParsedFile | UnreadableSource:
    # `tokenize.open` decodes as Python does, honoring an encoding declaration,
    # and folds every newline to `\n`, the only line break `ast` counts.
    try:
        with tokenize.open(path) as file:
            text = file.read()
    except OSError, SyntaxError, ValueError:
        return UnreadableSource(reason=f'{relpath} could not be read')
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return UnreadableSource(reason=f'{relpath} does not parse')
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            assert node.end_lineno is not None, 'ast.parse sets every end position'
            first = min([node.lineno, *(dec.lineno for dec in node.decorator_list)])
            spans.append((first, node.end_lineno))
    return _ParsedFile(lines=text.split('\n'), spans=spans)
