import ast
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).parents[2]
_EXAMPLE = _ROOT / 'examples' / 'coffeeshop' / 'test_coffeeshop.py'
_PYTHON_BLOCK = re.compile(r'^```python\n(.*?)^```', re.MULTILINE | re.DOTALL)


# The quick start cites the coffeeshop scenario as its rendered report, so the
# snippet must be that scenario's code.
@pytest.mark.parametrize(
    'document', ['README.md', 'docs/site/getting-started.md', 'docs/site/bdd.md']
)
def test_quick_start_scenario_is_the_coffeeshop_one(document: str) -> None:
    text = (_ROOT / document).read_text(encoding='utf-8')
    [snippet] = [
        block
        for block in _PYTHON_BLOCK.findall(text)
        if 'def test_buy_coffee(' in block
    ]
    assert _scenario_dump(snippet) == _scenario_dump(
        _EXAMPLE.read_text(encoding='utf-8')
    )


def _scenario_dump(source: str) -> str:
    [scenario] = [
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == 'test_buy_coffee'
    ]
    return ast.dump(scenario)
