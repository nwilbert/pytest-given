"""End-to-end tests for the `--given-phase-check` gate, driven through an inner
pytest run via `pytester` (in-process, so the plugin hooks are covered)."""

import pytest

TWO_PHASE = """
from pytest_given import scenario, given, then

@scenario("Two phase")
def test_two_phase():
    with given("a value"):
        x = 1
    with then("it stays one"):
        assert x == 1
"""

THREE_PHASE = """
from pytest_given import scenario, given, when, then

@scenario("Three phase")
def test_three_phase():
    with given("a value"):
        x = 1
    with when("it is doubled"):
        x = x * 2
    with then("it is two"):
        assert x == 2
"""

FAILING_TWO_PHASE = """
from pytest_given import scenario, given, then

@scenario("Failing two phase")
def test_failing():
    with given("a value"):
        x = 1
    with then("it is two"):
        assert x == 2
"""

PARAMETRIZED_TWO_PHASE = """
import pytest
from pytest_given import scenario, given, then

@scenario("Parametrized two phase")
@pytest.mark.parametrize("n", [1, 2])
def test_param(n):
    with given("a value"):
        x = n
    with then("it is truthy"):
        assert x
"""


def _run(pytester, tmp_path, source, *args):
    pytester.makepyfile(test_sample=source)
    json_path = tmp_path / 'report.json'
    return pytester.runpytest(f'--given-json={json_path}', *args)


def test_off_by_default_reports_nothing(pytester, tmp_path):
    result = _run(pytester, tmp_path, TWO_PHASE)
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    assert 'incomplete scenarios' not in result.stdout.str()


def test_warn_names_the_incomplete_scenario(pytester, tmp_path):
    result = _run(pytester, tmp_path, TWO_PHASE, '--given-phase-check=warn')
    result.assert_outcomes(passed=1)
    assert result.ret == 0  # warn never changes the exit code
    result.stdout.fnmatch_lines(
        ['*incomplete scenarios (1)*', '*test_two_phase*missing: when*']
    )


def test_error_fails_the_run_on_an_incomplete_scenario(pytester, tmp_path):
    result = _run(pytester, tmp_path, TWO_PHASE, '--given-phase-check=error')
    result.assert_outcomes(passed=1)  # the test itself passed
    assert result.ret == pytest.ExitCode.TESTS_FAILED  # the gate failed the run
    result.stdout.fnmatch_lines(['*incomplete scenarios (1)*'])


def test_error_passes_a_complete_suite(pytester, tmp_path):
    result = _run(pytester, tmp_path, THREE_PHASE, '--given-phase-check=error')
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    assert 'incomplete scenarios' not in result.stdout.str()


def test_ignore_list_exempts_a_scenario(pytester, tmp_path):
    result = _run(
        pytester,
        tmp_path,
        TWO_PHASE,
        '--given-phase-check=error',
        '-o',
        'given_phase_check_ignore=*::test_two_phase',
    )
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    assert 'incomplete scenarios' not in result.stdout.str()


def test_level_read_from_ini(pytester, tmp_path):
    result = _run(pytester, tmp_path, TWO_PHASE, '-o', 'given_phase_check=warn')
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    result.stdout.fnmatch_lines(['*incomplete scenarios (1)*'])


def test_cli_overrides_ini(pytester, tmp_path):
    result = _run(
        pytester,
        tmp_path,
        TWO_PHASE,
        '-o',
        'given_phase_check=off',
        '--given-phase-check=error',
    )
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_invalid_level_is_a_usage_error(pytester, tmp_path):
    result = _run(pytester, tmp_path, TWO_PHASE, '-o', 'given_phase_check=bogus')
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert 'given_phase_check' in (result.stderr.str() + result.stdout.str())


def test_failing_incomplete_scenario_is_not_flagged(pytester, tmp_path):
    result = _run(pytester, tmp_path, FAILING_TWO_PHASE, '--given-phase-check=error')
    result.assert_outcomes(failed=1)
    assert 'incomplete scenarios' not in result.stdout.str()


def test_parametrized_scenario_reported_once(pytester, tmp_path):
    result = _run(
        pytester, tmp_path, PARAMETRIZED_TWO_PHASE, '--given-phase-check=warn'
    )
    result.assert_outcomes(passed=2)
    assert result.stdout.str().count('missing: when') == 1
