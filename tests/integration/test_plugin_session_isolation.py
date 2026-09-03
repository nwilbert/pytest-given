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
    result = pytester.runpytest('--given-lint')
    result.assert_outcomes(passed=2, errors=1)
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


OUTER_NESTED_IN_STEP = '''
import pytest
from pytest_given import scenario, when, then

NESTED = """
from pytest_given import scenario, then

@scenario("Nested")
def test_nested():
    with then("the nested suite runs"):
        assert True
"""


@scenario("A nested run inside a step")
def test_nested_in_step(tmp_path):
    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "test_nested.py").write_text(NESTED)
    with when("a nested pytest runs mid-scenario"):
        assert pytest.main([str(sub), "-p", "no:cacheprovider"]) == 0
    with then("the outer scenario still records steps afterward"):
        assert True
'''


def test_active_collector_restored_after_nested_run_inside_step(pytester):
    """A nested run clears the process-global active-collector ContextVar via
    its per-test teardown; the outer session's active collector must be put
    back when the nested run unconfigures, or the outer scenario's next step
    raises 'no active scenario or fixture'."""
    pytester.makepyfile(test_outer=OUTER_NESTED_IN_STEP)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


OUTER_ABORTED_NESTED = """
import pytest
from pytest_given import scenario, given, when, then


def test_before_runs_nested_pytest_that_aborts(tmp_path):
    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "test_nested.py").write_text("def test_ok():\\n    assert True\\n")
    # Dies while parsing arguments, before pytest_configure: the nested run
    # never reaches pytest_unconfigure.
    ret = pytest.main([str(sub), "--no-such-flag", "-p", "no:cacheprovider"])
    assert ret == pytest.ExitCode.USAGE_ERROR


@scenario("After the aborted nested run")
def test_after():
    with given("a value"):
        pass
    with when("computing"):
        x = 2
    with then("it is two"):
        assert x == 2
"""


def test_lint_still_anchors_steps_after_nested_run_aborts_at_argparse(pytester):
    """A nested run that dies during argument parsing never reaches
    `pytest_unconfigure`, so the rootdir it displaced must be put back by a
    config cleanup instead. Without that, every later step records
    `source=None` and the whole AST-rule surface goes silently dark."""
    pytester.makepyfile(test_outer=OUTER_ABORTED_NESTED)
    result = pytester.runpytest('--given-lint')
    result.assert_outcomes(passed=2, errors=1)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(
        ["*ERROR*empty-step*test_outer.py::test_after*'a value'*has no code*"]
    )


COLLECTOR_LEAK_CONFTEST = """
from pytest_given.capture import get_active_collector

leaked = []


def pytest_runtest_logfinish(nodeid):
    if get_active_collector() is not None:
        leaked.append(nodeid)


def pytest_sessionfinish(session):
    assert not leaked, f"active collector left set after: {leaked}"
"""

COLLECTOR_LEAK_TESTS = """
from pytest_given import scenario, given


@scenario("An annotated scenario")
def test_annotated():
    with given("a step"):
        pass


def test_unannotated():
    assert True
"""


def test_teardown_clears_the_active_collector_after_an_annotated_scenario(pytester):
    """`pytest_runtest_teardown` must clear the process-global active-collector
    ContextVar for an annotated scenario, not only for an unannotated one.

    The call-phase logreport has already run `finish_scenario` by teardown, so
    `active_scenario_id` is None — a guard keyed on it never matches, and the
    finished session\'s Collector, with every Scenario and Step it recorded,
    stays reachable from the ContextVar for the rest of the process (and into
    any later in-process run). Observed from `pytest_runtest_logfinish`, which
    runs after teardown and outside any test\'s own setup."""
    pytester.makeconftest(COLLECTOR_LEAK_CONFTEST)
    pytester.makepyfile(test_outer=COLLECTOR_LEAK_TESTS)
    result = pytester.runpytest()
    result.assert_outcomes(passed=2)
    assert result.ret == pytest.ExitCode.OK
