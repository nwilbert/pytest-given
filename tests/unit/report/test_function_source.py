from pathlib import Path

from pytest_given.model import Narration, NodeId, Scenario, SourceLocation
from pytest_given.report.function_source import (
    FunctionSource,
    UnreadableSource,
    read_function_sources,
)

_TESTS = """\
import pytest


def make_test():
    @pytest.mark.slow
    def test_inner():
        pass

    return test_inner


@pytest.mark.parametrize('n', [1])
@pytest.mark.slow
async def test_async(n):
    assert n
"""


def _scenario(relpath: str, line: int, name: str = 'test_x') -> Scenario:
    return Scenario(
        id=NodeId(f'{relpath}::{name}'),
        narration=Narration(text='A scenario'),
        module='m',
        status='passed',
        source=SourceLocation(relpath=relpath, line=line),
    )


def _write(root: Path, relpath: str, text: str) -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def test_the_innermost_function_holding_the_line_is_read_with_its_decorators(
    tmp_path: Path,
) -> None:
    _write(tmp_path, 'tests/test_a.py', _TESTS)
    inner = _scenario('tests/test_a.py', 5, 'test_inner')

    sources = read_function_sources([inner], tmp_path)

    assert sources[inner.id] == FunctionSource(
        first_line=5,
        lines=('    @pytest.mark.slow', '    def test_inner():', '        pass'),
    )


def test_an_async_test_is_read_from_its_first_decorator(tmp_path: Path) -> None:
    _write(tmp_path, 'tests/test_a.py', _TESTS)
    decorated = _scenario('tests/test_a.py', 12, 'test_async')

    source = read_function_sources([decorated], tmp_path)[decorated.id]

    assert isinstance(source, FunctionSource)
    assert source.first_line == 12
    assert source.lines[0] == "@pytest.mark.parametrize('n', [1])"
    assert source.lines[-1] == '    assert n'


def test_the_file_is_decoded_with_its_encoding_declaration(tmp_path: Path) -> None:
    text = "# -*- coding: latin-1 -*-\ndef test_cafe():\n    assert 'café'\n"
    (tmp_path / 'test_b.py').write_bytes(text.encode('latin-1'))
    cafe = _scenario('test_b.py', 2, 'test_cafe')

    source = read_function_sources([cafe], tmp_path)[cafe.id]

    assert isinstance(source, FunctionSource)
    assert source.lines[-1] == "    assert 'café'"


def test_a_missing_file_leaves_a_reason_instead_of_failing(tmp_path: Path) -> None:
    gone = _scenario('tests/test_gone.py', 3)

    sources = read_function_sources([gone], tmp_path)

    assert sources[gone.id] == UnreadableSource(
        reason='tests/test_gone.py could not be read'
    )


def test_a_file_that_does_not_parse_leaves_a_reason(tmp_path: Path) -> None:
    _write(tmp_path, 'test_c.py', 'def test_broken(:\n')
    broken = _scenario('test_c.py', 1)

    sources = read_function_sources([broken], tmp_path)

    assert sources[broken.id] == UnreadableSource(reason='test_c.py does not parse')


def test_a_line_no_function_holds_leaves_a_reason(tmp_path: Path) -> None:
    _write(tmp_path, 'tests/test_a.py', _TESTS)
    stray = _scenario('tests/test_a.py', 1)

    sources = read_function_sources([stray], tmp_path)

    assert sources[stray.id] == UnreadableSource(
        reason='no function holds tests/test_a.py:1'
    )


def test_scenarios_sharing_a_file_each_get_their_function(tmp_path: Path) -> None:
    _write(tmp_path, 'tests/test_a.py', _TESTS)
    helper = _scenario('tests/test_a.py', 4, 'make_test')
    inner = _scenario('tests/test_a.py', 5, 'test_inner')

    sources = read_function_sources([helper, inner], tmp_path)

    helper_source = sources[helper.id]
    assert isinstance(helper_source, FunctionSource)
    assert (helper_source.first_line, len(helper_source.lines)) == (4, 6)
    inner_source = sources[inner.id]
    assert isinstance(inner_source, FunctionSource)
    assert (inner_source.first_line, len(inner_source.lines)) == (5, 3)
