"""Runs the script the reviewing skill ships in its references.

To the packaging tests a reference is prose; to its reader it is code that
walks the report schema, and nothing else holds the two together. Each test
here builds a report through the model, runs the shipped script over it the
way a reviewer would, and asserts on what it produced — so a renamed field
breaks the suite rather than someone's review.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from pytest_given.cli.skills import BUNDLED_SKILLS_ROOT
from pytest_given.model import (
    Metadata,
    Narration,
    NodeId,
    ReportData,
    Scenario,
    SourceLocation,
    report_to_dict,
)

_DEMO_TEST = """\
from pytest_given import given, scenario, then


@scenario('A demo scenario')
def test_demo():
    with given('a demo'):
        value = 1
    with then('it is one'):
        assert value == 1
"""

_DEMO_LINE = _DEMO_TEST.splitlines().index('def test_demo():') + 1


def _meta() -> Metadata:
    return Metadata(project='p', timestamp='t', pytest_version='8', plugin_version='0')


def _write_report(directory: Path, report: ReportData) -> Path:
    path = directory / 'report.json'
    path.write_text(json.dumps(report_to_dict(report)), encoding='utf-8')
    return path


def _run(reference: str, cwd: Path, *args: str) -> str:
    """Run the one python block of a bundled reference, from `cwd`."""
    text = (
        BUNDLED_SKILLS_ROOT / 'pytest-given-reviewing' / 'references' / reference
    ).read_text(encoding='utf-8')
    blocks = re.findall(r'```python\n(.*?)```', text, re.DOTALL)
    assert len(blocks) == 1, f'{reference} must hold exactly one python block'
    script = cwd / 'script.py'
    script.write_text(blocks[0], encoding='utf-8')
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_pairs_script_dumps_each_narration_beside_its_test(tmp_path: Path) -> None:
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests' / 'test_demo.py').write_text(_DEMO_TEST, encoding='utf-8')
    _write_report(
        tmp_path,
        ReportData(
            metadata=_meta(),
            scenarios=[
                Scenario(
                    id=NodeId('tests/test_demo.py::test_demo'),
                    narration=Narration(text='A demo scenario'),
                    module='tests.test_demo',
                    tags=['demo'],
                    status='passed',
                    source=SourceLocation(
                        relpath='tests/test_demo.py', line=_DEMO_LINE
                    ),
                )
            ],
        ),
    )

    _run('pairs.md', tmp_path, 'report.json', 'dump')

    dump = (tmp_path / 'dump' / 'tests__test_demo.py.txt').read_text(encoding='utf-8')
    assert 'TITLE: A demo scenario' in dump
    assert '[passed]' in dump
    assert '[tags: demo]' in dump
    # The whole test, decorator included, under real line numbers.
    assert f'{_DEMO_LINE - 1}\t@scenario' in dump
    assert "with then('it is one'):" in dump
