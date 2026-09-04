"""End-to-end tests for the `--given-lint` gate, driven through an inner
pytest run via `pytester` (in-process, so the plugin hooks are covered)."""

import json

import pytest

from pytest_given import attach, given, scenario, then, when
from pytest_given.plugin import state
from tests.ubiquitous_language import adopt_pytest_given, pg

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

    collector = state.session_collector(capture.config)
    steps = [step for scenario in collector.scenarios for step in walk(scenario.steps)]
    return result, steps


@scenario(t'{pg["Narration lint"]} is off unless it is asked for')
def test_disabled_by_default_records_no_sources_and_reports_nothing(pytester):
    with given(t'a suite with one flawed {pg["Step"].low}'):
        attach('suite', EMPTY_GIVEN)
    with when('the suite runs without the lint flag'):
        result, steps = _run_observed(pytester, EMPTY_GIVEN)
    with then('the run passes and says nothing about the lint'):
        result.assert_outcomes(passed=1)
        assert result.ret == 0
        assert 'narration lint' not in result.stdout.str()
    with then('no step source is recorded, so the AST surface costs nothing'):
        assert steps  # sanity: the scenario recorded its steps
        assert all(step.source is None for step in steps)


def test_an_error_finding_shows_in_the_summary_line(pytester):
    """The run must not read green while it exits non-zero.

    `session.exitstatus` is assigned from `pytest_sessionfinish`, which is too
    late for the terminal reporter's already-bound `exitstatus` argument — so
    the failure has to reach the summary line through the reporter's stats
    instead. A CI log that shows `1 passed` in green over exit 1 is worse than
    no summary at all.
    """
    result = _run(pytester, EMPTY_GIVEN, '--given-lint')
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(['*1 passed*1 error*'])


@scenario(
    t'An error-{pg["Severity"].low} {pg["Finding"].low} fails the run',
    story=adopt_pytest_given,
)
def test_enabled_error_finding_fails_the_run(pytester):
    with given(t'a suite whose given {pg["Step"].low} has an empty body'):
        attach('suite', EMPTY_GIVEN)
    with when('the suite runs with the lint enabled', activity=11):
        result = _run(pytester, EMPTY_GIVEN, '--given-lint')
    with then(t'the run exits failed, naming the {pg["Lint rule"].low} and the step'):
        # The test itself passed; the error is pytest-given's own, registered
        # so the summary line cannot read green over a non-zero exit.
        result.assert_outcomes(passed=1, errors=1)
        assert result.ret == pytest.ExitCode.TESTS_FAILED
        result.stdout.fnmatch_lines(
            [
                '*narration lint (1 finding, 1 error)*',
                '*ERROR*empty-step*test_sample.py::test_empty_given*'
                "*'a value'*has no code*",
            ]
        )


def test_enabled_clean_suite_exits_zero_and_captures_sources(pytester):
    result, steps = _run_observed(pytester, CLEAN, '--given-lint')
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()
    assert steps
    assert all(step.source is not None for step in steps)


@scenario(
    t'A {pg["Lint rule"].low} downgraded to warn reports without failing the run',
    story=adopt_pytest_given,
)
def test_warn_override_prints_but_does_not_fail(pytester):
    with given(t'a suite whose given {pg["Step"].low} has an empty body'):
        attach('suite', EMPTY_GIVEN)
    with when(
        t'the suite runs with that {pg["Lint rule"].low} set to warn', activity=11
    ):
        result = _run(
            pytester,
            EMPTY_GIVEN,
            '--given-lint',
            '-o',
            'given_lint_rules=empty-step=warn',
        )
    with then('the run still passes'):
        result.assert_outcomes(passed=1)
        assert result.ret == 0
    with then(t'the {pg["Finding"].low} is printed anyway'):
        # One fnmatch pattern means "some line matches"; the assert says the
        # same thing, and `then-without-check` can see it.
        assert any(
            'WARN' in line and 'empty-step' in line for line in result.stdout.lines
        )


def test_off_override_disables_the_rule(pytester):
    result = _run(
        pytester,
        EMPTY_GIVEN,
        '--given-lint',
        '-o',
        'given_lint_rules=empty-step=off',
    )
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()


def test_bare_ignore_glob_suppresses_the_finding(pytester):
    result = _run(
        pytester,
        EMPTY_GIVEN,
        '--given-lint',
        '-o',
        'given_lint_ignore=*::test_empty_given',
    )
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()


def test_rule_scoped_ignore_glob_suppresses_the_finding(pytester):
    result = _run(
        pytester,
        EMPTY_GIVEN,
        '--given-lint',
        '-o',
        'given_lint_ignore=empty-step: *::test_empty_given',
    )
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()


def test_stale_ignore_entry_fails_the_run(pytester):
    result = _run(
        pytester,
        CLEAN,
        '--given-lint',
        '-o',
        'given_lint_ignore=*::test_nothing',
    )
    result.assert_outcomes(passed=1, errors=1)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(['*stale-ignore*suppressed no finding*'])


@scenario(
    t'Either {pg["Narration lint"].low} flag overrides the ini for one run',
    story=adopt_pytest_given,
)
def test_the_flag_overrides_the_ini_in_both_directions(pytester):
    with given(t'a suite with one flawed {pg["Step"].low}'):
        attach('suite', EMPTY_GIVEN)
    with when('the suite runs with the lint enabled by ini but off by flag'):
        off = _run(pytester, EMPTY_GIVEN, '-o', 'given_lint=true', '--no-given-lint')
    with then('the lint does not run'):
        assert off.ret == 0
        assert 'narration lint' not in off.stdout.str()
    with when('the suite runs with the lint disabled by ini but on by flag'):
        on = _run(pytester, EMPTY_GIVEN, '-o', 'given_lint=false', '--given-lint')
    with then('the lint runs and its error finding fails the run'):
        assert on.ret == pytest.ExitCode.TESTS_FAILED
        on.stdout.fnmatch_lines(['*narration lint*'])


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
    result, steps = _run_observed(pytester, FIXTURE_SUITE, '--given-lint')
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
    pytester.runpytest(f'--given-json={on_json}', f'--given-md={on_md}', '--given-lint')
    assert on_md.read_bytes() == off_md.read_bytes()

    def normalized(path):
        data = json.loads(path.read_text(encoding='utf-8'))
        data['metadata']['timestamp'] = ''
        for recorded in data['scenarios']:
            recorded['duration_ms'] = 0
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
    result = _run(pytester, TWO_PHASE, '--given-lint')
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        ['*WARN*missing-phase*test_sample.py::test_two_phase*missing: when*']
    )


def test_missing_phase_error_override_fails_the_run(pytester):
    result = _run(
        pytester,
        TWO_PHASE,
        '--given-lint',
        '-o',
        'given_lint_rules=missing-phase=error',
    )
    result.assert_outcomes(passed=1, errors=1)
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_missing_phase_honest_two_phase_is_ignorable(pytester):
    result = _run(
        pytester,
        TWO_PHASE,
        '--given-lint',
        '-o',
        'given_lint_ignore=missing-phase: *::test_two_phase',
    )
    assert result.ret == 0
    assert 'narration lint' not in result.stdout.str()


def test_missing_phase_parametrized_scenario_reported_once(pytester):
    result = _run(pytester, PARAMETRIZED_TWO_PHASE, '--given-lint')
    result.assert_outcomes(passed=2)
    assert result.stdout.str().count('missing: when') == 1


def test_tag_shadows_term_warns_on_slug_collision(pytester):
    pytester.makeconftest(TAGGED_GLOSSARY_CONFTEST)
    result = _run(pytester, TAGGED_SUITE, '--given-lint')
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        ["*WARN*tag-shadows-term*guest*duplicates glossary term 'Guest'*"]
    )


def test_dead_term_is_off_by_default(pytester):
    pytester.makeconftest(TAGGED_GLOSSARY_CONFTEST)
    result = _run(pytester, TAGGED_SUITE, '--given-lint')
    assert 'dead-term' not in result.stdout.str()


def test_dead_term_opt_in_flags_unreferenced_term(pytester):
    pytester.makeconftest(TAGGED_GLOSSARY_CONFTEST)
    result = _run(
        pytester,
        TAGGED_SUITE,
        '--given-lint',
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


@scenario(
    t'An error {pg["Finding"].low} leaves a more specific exit code alone',
    story=adopt_pytest_given,
)
def test_lint_error_does_not_mask_a_more_specific_exit_code(pytester):
    with given('a suite whose lint would fail, deselected so nothing is collected'):
        attach('suite', EMPTY_GIVEN)
    with when('the run collects no test but still trips a stale ignore', activity=11):
        pytester.makeini(
            '[pytest]\ngiven_lint = true\ngiven_lint_ignore = ["never-matches-*"]\n'
        )
        pytester.makepyfile(test_sample=EMPTY_GIVEN)
        result = pytester.runpytest_inprocess('-k', 'no-such-test')
    with then('the run keeps NO_TESTS_COLLECTED rather than reporting a test failure'):
        # pytest binds exitstatus before sessionfinish, so overwriting it
        # unconditionally would report 5 as a plain 1.
        assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED


@scenario(
    t'A failure inside the lint keeps the {pg["Report"].low} it was handed',
    tags=['validation'],
)
def test_a_lint_failure_is_reported_and_keeps_the_written_report(pytester):
    """The lint runs after the sinks are written and owns none of them. Its
    failure has to reach the terminal summary — an exception out of
    `pytest_sessionfinish` is a bare traceback with no exit code — without
    discarding a report that is on disk and correct."""
    with given('a clean suite and a lint pass that raises'):
        pytester.makepyfile(CLEAN)
        # Patched for the duration of the inner sessionfinish only: the module
        # object is shared with the outer run, whose own lint must still work.
        pytester.makeconftest(
            """
            import pytest
            from pytest_given.model import PytestGivenError
            from pytest_given.plugin import session as given_session

            @pytest.hookimpl(wrapper=True, tryfirst=True)
            def pytest_sessionfinish(session, exitstatus):
                original = given_session._run_lint
                def boom(*_args):
                    raise PytestGivenError('lint exploded')
                given_session._run_lint = boom
                try:
                    return (yield)
                finally:
                    given_session._run_lint = original
            """
        )
    with when('the suite runs with an HTML sink'):
        result = pytester.runpytest('--given-html=report.html', '--given-lint')
    with then('the failure is summarized rather than raised as a traceback'):
        assert 'lint exploded' in result.stdout.str()
        assert result.ret == pytest.ExitCode.TESTS_FAILED
    with then('the report that was already written is still there'):
        assert (pytester.path / 'report.html').is_file()
