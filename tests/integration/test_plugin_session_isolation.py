"""A nested in-process pytest run (pytester, pytest.main) must not clobber
the outer session's state: the collector is session-owned via `config.stash`,
and the module-global capture rootdir and story registry are saved and
restored around the nested run's config lifecycle."""

import json

import pytest

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


OUTER_LINTED = '''
import pytest
from pytest_given import scenario, given, when, then

NESTED = """
from pytest_given import scenario, then

@scenario("Nested")
def test_nested():
    with then("the nested suite runs"):
        assert True
"""


def test_before_runs_nested_pytest(tmp_path):
    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "test_nested.py").write_text(NESTED)
    assert pytest.main([str(sub), "-p", "no:cacheprovider"]) == 0


@scenario("After the nested run")
def test_after():
    with given("a value"):
        pass
    with when("computing"):
        x = 2
    with then("it is two"):
        assert x == 2
'''


def test_lint_still_anchors_steps_after_nested_inprocess_run(pytester):
    """Step-source capture must resolve against the outer rootdir even after a
    nested run re-pointed it: the empty given executed after the nested run
    only reaches the AST rules if its `Step.source` was captured."""
    pytester.makepyfile(test_outer=OUTER_LINTED)
    result = pytester.runpytest('--given-lint=true')
    result.assert_outcomes(passed=2)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(
        ["*ERROR*empty-step*test_outer.py::test_after*'a value'*has no code*"]
    )


OUTER_STORY = '''
import pytest
from pytest_given import scenario, story, then

# A story declared at test-module level: it registers during the outer
# session's collection and stays registered for the run.
OUTER_STORY = story("Shared Title")

NESTED_CONFTEST = """
from pytest_given import story

# Same id as the outer story: the nested run must not see the outer
# session's registration, or this collides at conftest-import time.
NESTED_STORY = story("Shared Title")
"""


def test_middle_runs_nested_pytest(tmp_path):
    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "conftest.py").write_text(NESTED_CONFTEST)
    (sub / "test_nested.py").write_text("def test_ok():\\n    assert True\\n")
    assert pytest.main([str(sub), "-p", "no:cacheprovider"]) == 0


@scenario("After the nested run")
def test_after():
    with then("the outer story registration is untouched"):
        assert True
'''


def test_story_registry_isolated_across_nested_inprocess_run(pytester):
    """A nested run declaring a story whose id collides with an outer
    module-level story must not fail: the story registry is displaced before
    the nested run imports its conftests, so the outer registration is invisible
    to the nested session (and the nested one does not leak back)."""
    pytester.makepyfile(test_outer=OUTER_STORY)
    result = pytester.runpytest()
    result.assert_outcomes(passed=2)
