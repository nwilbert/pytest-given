"""A nested in-process pytest run (pytester, pytest.main) must not clobber
the outer session's collector — each session owns its instance via
`config.stash`, so scenarios recorded before the nested run survive it."""

import json

OUTER = '''
import pytest
from pytest_given import scenario, when, then

NESTED = """
from pytest_given import scenario, then

@scenario("Nested")
def test_nested():
    with then("the nested suite runs"):
        assert True
"""


@scenario("Before the nested run")
def test_before():
    with when("the outer suite starts"):
        x = 1
    with then("the scenario is recorded"):
        assert x == 1


def test_middle_runs_nested_pytest(tmp_path):
    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "test_nested.py").write_text(NESTED)
    assert pytest.main([str(sub), "-p", "no:cacheprovider"]) == 0


@scenario("After the nested run")
def test_after():
    with then("the scenario is recorded too"):
        assert True
'''


def test_outer_report_survives_nested_inprocess_run(pytester, tmp_path):
    pytester.makepyfile(test_outer=OUTER)
    out = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={out}')
    result.assert_outcomes(passed=3)
    data = json.loads(out.read_text(encoding='utf-8'))
    names = [scenario['narration']['text'] for scenario in data['scenarios']]
    assert names == ['Before the nested run', 'After the nested run']
