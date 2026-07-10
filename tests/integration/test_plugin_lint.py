"""End-to-end tests for the `--given-lint` gate, driven through an inner
pytest run via `pytester` (in-process, so the plugin hooks are covered)."""

import json

import pytest

from pytest_given import plugin

CLEAN = """
from pytest_given import scenario, given, when, then

@scenario("Clean")
def test_clean():
    with given("a value"):
        x = 1
    with when("it is doubled"):
        x = x * 2
    with then("it is two"):
        assert x == 2
"""

EMPTY_GIVEN = """
from pytest_given import scenario, given, when, then

@scenario("Empty given")
def test_empty_given():
    with given("a value"):
        pass
    with when("computing"):
        x = 2
    with then("it is two"):
        assert x == 2
"""

FIXTURE_SUITE = """
import pytest
from pytest_given import scenario, given, when, then

@pytest.fixture
@given('a stocked machine')
def machine():
    return {'coffees': 2}

@scenario("Fixture root")
def test_fixture_root(machine):
    with when("buying a coffee"):
        machine['coffees'] -= 1
    with then("one is left"):
        assert machine['coffees'] == 1
"""


def _run(pytester, source, *args):
    pytester.makepyfile(test_sample=source)
    return pytester.runpytest(*args)


class _ConfigCapture:
    """Extra inner-run plugin that captures the inner session's Config, whose
    stash owns that session's collector."""

    config = None

    def pytest_configure(self, config):
        self.config = config


def _run_observed(pytester, source, *args):
    """Like `_run`, but also returns all steps (recursively) recorded by the
    inner session's collector — the only place `Step.source` is observable,
    since it is never serialized."""
    pytester.makepyfile(test_sample=source)
    capture = _ConfigCapture()
    result = pytester.runpytest(*args, plugins=[capture])

    def walk(steps):
        for step in steps:
            yield step
            yield from walk(step.children)

    collector = plugin._collector(capture.config)
    steps = [step for scenario in collector.scenarios for step in walk(scenario.steps)]
    return result, steps


def test_disabled_by_default_records_no_sources_and_reports_nothing(pytester):
    result, steps = _run_observed(pytester, EMPTY_GIVEN)
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()
    assert steps  # sanity: the scenario recorded its steps
    assert all(step.source is None for step in steps)


def test_enabled_error_finding_fails_the_run(pytester):
    result = _run(pytester, EMPTY_GIVEN, '--given-lint=true')
    result.assert_outcomes(passed=1)  # the test itself passed
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(
        [
            '*narration lint (1 finding, 1 error)*',
            "*ERROR*empty-step*test_sample.py::test_empty_given*'a value'*has no code*",
        ]
    )


def test_enabled_clean_suite_exits_zero_and_captures_sources(pytester):
    result, steps = _run_observed(pytester, CLEAN, '--given-lint=true')
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()
    assert steps
    assert all(step.source is not None for step in steps)


def test_warn_override_prints_but_does_not_fail(pytester):
    result = _run(
        pytester,
        EMPTY_GIVEN,
        '--given-lint=true',
        '-o',
        'given_lint_rules=empty-step=warn',
    )
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    result.stdout.fnmatch_lines(['*WARN*empty-step*'])


def test_off_override_disables_the_rule(pytester):
    result = _run(
        pytester,
        EMPTY_GIVEN,
        '--given-lint=true',
        '-o',
        'given_lint_rules=empty-step=off',
    )
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()


def test_bare_ignore_glob_suppresses_the_finding(pytester):
    result = _run(
        pytester,
        EMPTY_GIVEN,
        '--given-lint=true',
        '-o',
        'given_lint_ignore=*::test_empty_given',
    )
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()


def test_rule_scoped_ignore_glob_suppresses_the_finding(pytester):
    result = _run(
        pytester,
        EMPTY_GIVEN,
        '--given-lint=true',
        '-o',
        'given_lint_ignore=empty-step: *::test_empty_given',
    )
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()


def test_stale_ignore_entry_fails_the_run(pytester):
    result = _run(
        pytester,
        CLEAN,
        '--given-lint=true',
        '-o',
        'given_lint_ignore=*::test_nothing',
    )
    result.assert_outcomes(passed=1)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(['*stale-ignore*suppressed no finding*'])


def test_cli_false_overrides_ini_true(pytester):
    result = _run(pytester, EMPTY_GIVEN, '-o', 'given_lint=true', '--given-lint=false')
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()


def test_ini_alone_enables_the_lint(pytester):
    result = _run(pytester, EMPTY_GIVEN, '-o', 'given_lint=true')
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_unknown_rule_id_is_a_usage_error(pytester):
    result = _run(pytester, CLEAN, '-o', 'given_lint_rules=bogus-rule=warn')
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert 'bogus-rule' in (result.stderr.str() + result.stdout.str())


def test_unknown_level_is_a_usage_error(pytester):
    result = _run(pytester, CLEAN, '-o', 'given_lint_rules=empty-step=loud')
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert 'loud' in (result.stderr.str() + result.stdout.str())


def test_unknown_ignore_prefix_is_a_usage_error(pytester):
    result = _run(pytester, CLEAN, '-o', 'given_lint_ignore=bogus-rule: legacy-*')
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert 'bogus-rule' in (result.stderr.str() + result.stdout.str())


def test_fixture_root_step_stays_unanchored_and_unflagged(pytester):
    result, steps = _run_observed(pytester, FIXTURE_SUITE, '--given-lint=true')
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    roots = [s for s in steps if s.fixture_name == 'machine']
    inline = [s for s in steps if s.fixture_name is None]
    assert roots
    assert all(s.source is None for s in roots)
    assert inline
    assert all(s.source is not None for s in inline)


def test_report_outputs_are_identical_with_and_without_lint(pytester, tmp_path):
    pytester.makepyfile(test_sample=CLEAN)
    off_json, off_md = tmp_path / 'off.json', tmp_path / 'off.md'
    on_json, on_md = tmp_path / 'on.json', tmp_path / 'on.md'
    pytester.runpytest(f'--given-json={off_json}', f'--given-md={off_md}')
    pytester.runpytest(
        f'--given-json={on_json}', f'--given-md={on_md}', '--given-lint=true'
    )
    assert on_md.read_bytes() == off_md.read_bytes()

    def normalized(path):
        data = json.loads(path.read_text(encoding='utf-8'))
        data['metadata']['timestamp'] = ''
        for scenario in data['scenarios']:
            scenario['duration_ms'] = 0
        return data

    assert normalized(on_json) == normalized(off_json)

    def step_keys(steps):
        for step in steps:
            yield from step
            yield from step_keys(step['children'])

    on_steps = json.loads(on_json.read_text(encoding='utf-8'))['scenarios'][0]['steps']
    assert 'source' not in set(step_keys(on_steps))


TWO_PHASE = """
from pytest_given import scenario, given, then

@scenario("Two phase")
def test_two_phase():
    with given("a value"):
        x = 1
    with then("it stays one"):
        assert x == 1
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

DIVERGENT_CASES = """
import pytest
from pytest_given import scenario, given, when, then

@scenario("Divergent")
@pytest.mark.parametrize("n", [1, 2])
def test_divergent(n):
    with given("a value"):
        x = n
    if n == 2:
        with when("doubling"):
            x = x * 2
    with then("it is positive"):
        assert x > 0
"""

TAGGED_GLOSSARY_CONFTEST = """
from pytest_given import Glossary

g = Glossary()
guest = g.actor('Guest')
"""

TAGGED_SUITE = """
from pytest_given import scenario, given, when, then

@scenario("Tagged", tags=["guest"])
def test_tagged():
    with given("a value"):
        x = 1
    with when("doubling"):
        x = x * 2
    with then("it is two"):
        assert x == 2
"""


def test_missing_phase_warns_by_default(pytester):
    result = _run(pytester, TWO_PHASE, '--given-lint=true')
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        ['*WARN*missing-phase*test_sample.py::test_two_phase*missing: when*']
    )


def test_missing_phase_error_override_fails_the_run(pytester):
    result = _run(
        pytester,
        TWO_PHASE,
        '--given-lint=true',
        '-o',
        'given_lint_rules=missing-phase=error',
    )
    result.assert_outcomes(passed=1)
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_missing_phase_honest_two_phase_is_ignorable(pytester):
    result = _run(
        pytester,
        TWO_PHASE,
        '--given-lint=true',
        '-o',
        'given_lint_ignore=missing-phase: *::test_two_phase',
    )
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()


def test_missing_phase_parametrized_scenario_reported_once(pytester):
    result = _run(pytester, PARAMETRIZED_TWO_PHASE, '--given-lint=true')
    result.assert_outcomes(passed=2)
    assert result.stdout.str().count('missing: when') == 1


def test_divergent_case_structure_warns_naming_the_case(pytester):
    result = _run(pytester, DIVERGENT_CASES, '--given-lint=true')
    result.assert_outcomes(passed=2)
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        ['*WARN*divergent-case-structure*test_sample.py::test_divergent*[[]2[]]*']
    )


def test_tag_shadows_term_warns_on_slug_collision(pytester):
    pytester.makeconftest(TAGGED_GLOSSARY_CONFTEST)
    result = _run(pytester, TAGGED_SUITE, '--given-lint=true')
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        ["*WARN*tag-shadows-term*guest*duplicates glossary term 'Guest'*"]
    )


def test_dead_term_is_off_by_default(pytester):
    pytester.makeconftest(TAGGED_GLOSSARY_CONFTEST)
    result = _run(pytester, TAGGED_SUITE, '--given-lint=true')
    assert 'dead-term' not in result.stdout.str()


def test_dead_term_opt_in_flags_unreferenced_term(pytester):
    pytester.makeconftest(TAGGED_GLOSSARY_CONFTEST)
    result = _run(
        pytester,
        TAGGED_SUITE,
        '--given-lint=true',
        '-o',
        'given_lint_rules=dead-term=warn',
    )
    result.stdout.fnmatch_lines(
        ["*WARN*dead-term*guest*term 'Guest' is referenced by no step and no story*"]
    )


def test_removed_phase_check_cli_flag_is_unrecognized(pytester):
    result = _run(pytester, TWO_PHASE, '--given-phase-check=warn')
    assert result.ret == pytest.ExitCode.USAGE_ERROR


def test_removed_phase_check_ini_key_is_unknown(pytester):
    result = _run(pytester, TWO_PHASE, '-o', 'given_phase_check=warn')
    result.assert_outcomes(passed=1)
    assert 'incomplete scenarios' not in result.stdout.str()
    assert 'Unknown config option: given_phase_check' in result.stdout.str()
