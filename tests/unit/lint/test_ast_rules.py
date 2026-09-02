"""Unit tests for the AST-surface lint rules (`lint/ast_rules.py`)."""

import dataclasses
import textwrap

import pytest

from pytest_given import attach, given, scenario, then, when
from pytest_given.lint import DEFAULTS, RuleId, run_ast_rules
from pytest_given.model import (
    Narration,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    Scenario,
    SourceLocation,
    Step,
    TermId,
)
from tests.ubiquitous_language import adopt_pytest_given, pg

# --- AST pass: anchoring, when_then pairs, rules 1-2 ---


def _write(tmp_path, src: str) -> str:
    src = textwrap.dedent(src)
    (tmp_path / 'test_x.py').write_text(src, encoding='utf-8')
    return src


def _line(src: str, needle: str) -> int:
    for i, text in enumerate(src.splitlines(), start=1):
        if needle in text:
            return i
    raise AssertionError(f'{needle!r} not found')


def _step(phase, text, line, children=()):
    return Step(
        phase=phase,
        narration=Narration(text=text),
        children=list(children),
        source=SourceLocation(relpath='test_x.py', line=line)
        if line is not None
        else None,
    )


def _scenario(steps):
    return Scenario(
        id=NodeId('test_x.py::test_a'),
        narration=Narration(text='S'),
        module='m',
        steps=steps,
    )


def _rule_findings(findings, rule):
    return [f for f in findings if f.rule == RuleId(rule)]


@scenario(
    t'{pg["Narration lint"]} flags a {pg["Step"].low} whose body does nothing',
    story=adopt_pytest_given,
)
def test_empty_step_fires_on_pass_only_body(tmp_path) -> None:
    with given(t'a given {pg["Step"].low} whose body is only `pass`'):
        src = _write(
            tmp_path,
            """\
            def test_a():
                with given('a value'):
                    pass
            """,
        )
        attach('step body', src)
        with_line = _line(src, "with given('a value')")
        empty = _scenario([_step('given', 'a value', with_line)])
    with when(t'the AST {pg["Lint rule"]("rules")} parse that source', activity=11):
        findings = run_ast_rules([empty], tmp_path)
    with then(t'an empty-step {pg["Finding"].low} points at the {pg["Step"].low} line'):
        [finding] = findings
        assert finding.rule == RuleId('empty-step')
        assert finding.subject == 'test_x.py::test_a'
        assert finding.location == SourceLocation(relpath='test_x.py', line=with_line)
        assert finding.message == ("given 'a value' has no code")
    with then(t'its {pg["Severity"].low} is error'):
        assert DEFAULTS[finding.rule] == 'error'


def test_empty_step_fires_on_docstring_and_ellipsis_only_body(tmp_path) -> None:
    src = _write(
        tmp_path,
        '''\
        def test_a():
            with given('a value'):
                """Docstring only."""
                ...
        ''',
    )
    scenario = _scenario([_step('given', 'a value', _line(src, 'with given'))])
    [finding] = run_ast_rules([scenario], tmp_path)
    assert finding.rule == RuleId('empty-step')


def test_empty_step_passes_with_real_statement(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given('a value'):
                x = 1
        """,
    )
    scenario = _scenario([_step('given', 'a value', _line(src, 'with given'))])
    assert run_ast_rules([scenario], tmp_path) == []


def test_empty_step_parent_with_nested_step_child_does_not_fire(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given('outer'):
                with given('inner'):
                    x = 1
        """,
    )
    inner = _step('given', 'inner', _line(src, "with given('inner')"))
    outer = _step('given', 'outer', _line(src, "with given('outer')"), [inner])
    assert run_ast_rules([_scenario([outer])], tmp_path) == []


@pytest.mark.parametrize(
    ('phase', 'fires'),
    [('given', False), ('when', True), ('then', True)],
)
def test_empty_step_attach_only_body_fires_for_when_and_then(
    tmp_path, phase, fires
) -> None:
    # Attaching is not acting or checking, but a `given` that only attaches
    # its arranged artifact is legitimate. Covers both the bare-name and
    # attribute call forms of attach.
    src = _write(
        tmp_path,
        f"""\
        def test_a():
            with {phase}('the step'):
                attach('label', 'content')
                pytest_given.attach('label2', 'content2')
        """,
    )
    scenario = _scenario([_step(phase, 'the step', _line(src, 'with '))])
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'empty-step')
    assert bool(findings) is fires


def test_empty_step_fires_on_empty_helper_function(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        @when('inserting money')
        def insert():
            ...
        """,
    )
    # A decorated helper anchors at its first decorator line (co_firstlineno).
    scenario = _scenario([_step('when', 'inserting money', _line(src, '@when'))])
    [finding] = run_ast_rules([scenario], tmp_path)
    assert finding.rule == RuleId('empty-step')


def test_empty_step_when_then_pair_is_reported_once(tmp_path) -> None:
    # The pair shares one `with`; its pytest.raises with-item is not body
    # content, so a pass-only body fires — but only once, not per step.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with when_then('acting', 'outcome'), pytest.raises(ValueError):
                pass
        """,
    )
    line = _line(src, 'with when_then')
    scenario = _scenario(
        [_step('when', 'acting', line), _step('then', 'outcome', line)]
    )
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'empty-step')
    assert len(findings) == 1


def test_when_then_pair_with_acting_body_passes_both_rules(tmp_path) -> None:
    # The acting expression need not be a call; the raises with-item satisfies
    # the then side.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with when_then('acting', 'outcome'), pytest.raises(KeyError):
                mapping[key]
        """,
    )
    line = _line(src, 'with when_then')
    scenario = _scenario(
        [_step('when', 'acting', line), _step('then', 'outcome', line)]
    )
    assert run_ast_rules([scenario], tmp_path) == []


def test_then_with_bare_assert_passes(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with then('it is one'):
                assert x == 1
        """,
    )
    scenario = _scenario([_step('then', 'it is one', _line(src, 'with then'))])
    assert run_ast_rules([scenario], tmp_path) == []


@scenario(
    t'{pg["Narration lint"]} flags a then {pg["Step"].low} that checks nothing',
    story=adopt_pytest_given,
)
def test_then_without_check_fires(tmp_path) -> None:
    with given(t'a then {pg["Step"].low} whose body only calls'):
        # Neither a plain call, nor a call through a subscripted callable,
        # counts as a check.
        src = _write(
            tmp_path,
            """\
            def test_a():
                with then('it is one'):
                    x = compute()
                    handlers[0](x)
            """,
        )
        attach('step body', src)
        with_line = _line(src, 'with then')
        unchecked = _scenario([_step('then', 'it is one', with_line)])
    with when(t'the AST {pg["Lint rule"]("rules")} parse that source', activity=11):
        findings = run_ast_rules([unchecked], tmp_path)
    with then(t'a then-without-check {pg["Finding"].low} reports the unchecked then'):
        [finding] = findings
        assert finding.rule == RuleId('then-without-check')
        assert finding.message == ("then 'it is one' contains no assertion")


def test_then_with_pytest_raises_item_passes(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with then('it rejects'), pytest.raises(ValueError):
                f()
        """,
    )
    scenario = _scenario([_step('then', 'it rejects', _line(src, 'with then'))])
    assert run_ast_rules([scenario], tmp_path) == []


@pytest.mark.parametrize('check', ['assert_valid(x)', 'helpers.assert_valid(x)'])
def test_then_with_assert_helper_call_passes(tmp_path, check) -> None:
    src = _write(
        tmp_path,
        f"""\
        def test_a():
            with then('it is valid'):
                {check}
        """,
    )
    scenario = _scenario([_step('then', 'it is valid', _line(src, 'with then'))])
    assert run_ast_rules([scenario], tmp_path) == []


def test_then_with_pytest_fail_passes(tmp_path) -> None:
    # A body that conditionally fails *is* checking.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with then('it never happens'):
                if x:
                    pytest.fail('nope')
        """,
    )
    scenario = _scenario([_step('then', 'it never happens', _line(src, 'with then'))])
    assert run_ast_rules([scenario], tmp_path) == []


def test_then_parent_with_checked_nested_child_passes(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with then('outer'):
                with then('inner'):
                    assert x
        """,
    )
    inner = _step('then', 'inner', _line(src, "with then('inner')"))
    outer = _step('then', 'outer', _line(src, "with then('outer')"), [inner])
    assert run_ast_rules([_scenario([outer])], tmp_path) == []


def test_plain_siblings_on_separate_lines_are_not_a_pair(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with when('acting'):
                pass
            with then('outcome'):
                pass
        """,
    )
    scenario = _scenario(
        [
            _step('when', 'acting', _line(src, 'with when')),
            _step('then', 'outcome', _line(src, 'with then')),
        ]
    )
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'empty-step')
    assert len(findings) == 2


def test_multiline_with_header_anchors_by_context_expression_line(
    tmp_path,
) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with (
                given('a value')
            ):
                pass
        """,
    )
    # The recorded anchor is the context-expression line, not the `with (` line.
    scenario = _scenario([_step('given', 'a value', _line(src, "given('a value')"))])
    [finding] = run_ast_rules([scenario], tmp_path)
    assert finding.rule == RuleId('empty-step')


def test_steps_without_source_are_skipped(tmp_path) -> None:
    _write(
        tmp_path,
        """\
        def test_a():
            with given('a value'):
                pass
        """,
    )
    scenario = _scenario([_step('given', 'a value', None)])
    assert run_ast_rules([scenario], tmp_path) == []


def test_missing_source_file_is_silently_skipped(tmp_path) -> None:
    scenario = _scenario([_step('given', 'a value', 2)])
    assert run_ast_rules([scenario], tmp_path) == []


def test_unparseable_source_file_is_silently_skipped(tmp_path) -> None:
    (tmp_path / 'test_x.py').write_text('def broken(:\n', encoding='utf-8')
    scenario = _scenario([_step('given', 'a value', 1)])
    assert run_ast_rules([scenario], tmp_path) == []


def test_anchor_line_with_no_matching_node_is_skipped(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            x = 1
        """,
    )
    scenario = _scenario([_step('given', 'a value', _line(src, 'x = 1'))])
    assert run_ast_rules([scenario], tmp_path) == []


# --- Rule 3: check-outside-then ---


@scenario(
    t'{pg["Narration lint"]} flags an assert outside a then {pg["Step"].low}',
    story=adopt_pytest_given,
)
@pytest.mark.parametrize('phase', ['given', 'when'])
def test_check_outside_then_fires_on_assert_in_given_or_when(tmp_path, phase) -> None:
    with given(t'a {phase} {pg["Step"].low} whose body asserts'):
        src = _write(
            tmp_path,
            f"""\
            def test_a():
                with {phase}('a stocked machine'):
                    machine = stock()
                    assert machine['coffees'] > 0
            """,
        )
        attach('step body', src)
        with_line = _line(src, 'with ')
        checking = _scenario([_step(phase, 'a stocked machine', with_line)])
    with when(t'the AST {pg["Lint rule"]("rules")} parse that source', activity=11):
        findings = _rule_findings(
            run_ast_rules([checking], tmp_path), 'check-outside-then'
        )
    with then(t'a warn {pg["Finding"].low} names the {phase} step holding the assert'):
        [finding] = findings
        assert finding.message == (f"assert inside {phase} 'a stocked machine'")


def test_check_outside_then_reports_one_finding_for_many_asserts(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given('a machine'):
                machine = stock()
                assert machine['coffees'] > 0
                assert machine['price'] == 2
        """,
    )
    scenario = _scenario([_step('given', 'a machine', _line(src, 'with given'))])
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'check-outside-then')
    assert len(findings) == 1


def test_check_outside_then_ignores_assert_in_then(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with then('it is one'):
                assert x == 1
        """,
    )
    scenario = _scenario([_step('then', 'it is one', _line(src, 'with then'))])
    assert (
        _rule_findings(run_ast_rules([scenario], tmp_path), 'check-outside-then') == []
    )


def test_check_outside_then_exempts_when_then_body(tmp_path) -> None:
    # The shared body belongs to the pair's `then` half, so an assert there is
    # a check in `then` territory.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with when_then('acting', 'outcome'):
                result = act()
                assert result
        """,
    )
    line = _line(src, 'with when_then')
    scenario = _scenario(
        [_step('when', 'acting', line), _step('then', 'outcome', line)]
    )
    assert (
        _rule_findings(run_ast_rules([scenario], tmp_path), 'check-outside-then') == []
    )


def test_check_outside_then_conditional_assert_still_fires(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with when('acting'):
                result = act()
                if result:
                    assert result > 0
        """,
    )
    scenario = _scenario([_step('when', 'acting', _line(src, 'with when'))])
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'check-outside-then')
    assert len(findings) == 1


def test_check_outside_then_child_assert_reported_on_the_child_only(
    tmp_path,
) -> None:
    # The assert lives in the nested step's block; the parent must not
    # double-report it.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given('outer'):
                x = 1
                with given('inner'):
                    assert x
        """,
    )
    inner_line = _line(src, "with given('inner')")
    inner = _step('given', 'inner', inner_line)
    outer = _step('given', 'outer', _line(src, "with given('outer')"), [inner])
    findings = _rule_findings(
        run_ast_rules([_scenario([outer])], tmp_path), 'check-outside-then'
    )
    [finding] = findings
    assert finding.location == SourceLocation(relpath='test_x.py', line=inner_line)


def test_check_outside_then_fires_on_helper_body_assert(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        @given('a validated machine')
        def make_machine():
            machine = stock()
            assert machine['coffees'] > 0
            return machine
        """,
    )
    scenario = _scenario([_step('given', 'a validated machine', _line(src, '@given'))])
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'check-outside-then')
    assert len(findings) == 1


# --- Rule 4: action-in-then (per scenario) ---


@scenario(
    t'{pg["Narration lint"]} flags a then {pg["Step"].low} that folds in the action',
    story=adopt_pytest_given,
)
def test_action_in_then_fires_when_no_when_exists(tmp_path) -> None:
    with given(t'a {pg["Scenario"].low} with no when, acting inside its then'):
        src = _write(
            tmp_path,
            """\
            def test_a():
                with given('a machine'):
                    machine = stock()
                with then('it brews'):
                    assert brew(machine) == 'coffee'
            """,
        )
        attach('step body', src)
        then_line = _line(src, 'with then')
        folded = _scenario(
            [
                _step('given', 'a machine', _line(src, 'with given')),
                _step('then', 'it brews', then_line),
            ]
        )
    with when(t'the AST {pg["Lint rule"]("rules")} parse that source', activity=11):
        findings = _rule_findings(run_ast_rules([folded], tmp_path), 'action-in-then')
    with then(t'a warn {pg["Finding"].low} points at the then and says no when acts'):
        [finding] = findings
        assert finding.subject == 'test_x.py::test_a'
        assert finding.location == SourceLocation(relpath='test_x.py', line=then_line)
        assert finding.message == (
            "then 'it brews' folds the action into its assertion; no when acts"
        )


def test_action_in_then_fires_when_no_when_acts(tmp_path) -> None:
    # A `when` whose body only rebinds a value performs no call — the acting
    # call hides in the then's assert.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with when('preparing'):
                x = 1
            with then('it brews'):
                assert brew(x) == 'coffee'
        """,
    )
    scenario = _scenario(
        [
            _step('when', 'preparing', _line(src, 'with when')),
            _step('then', 'it brews', _line(src, 'with then')),
        ]
    )
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'action-in-then')
    assert len(findings) == 1


def test_action_in_then_passes_when_a_when_acts(tmp_path) -> None:
    # Comparison-helper calls in the then never trigger the rule once a when
    # acts.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with when('brewing'):
                result = brew()
            with then('it is close enough'):
                assert math.isclose(result, 1.0)
        """,
    )
    scenario = _scenario(
        [
            _step('when', 'brewing', _line(src, 'with when')),
            _step('then', 'it is close enough', _line(src, 'with then')),
        ]
    )
    assert _rule_findings(run_ast_rules([scenario], tmp_path), 'action-in-then') == []


def test_action_in_then_passes_without_a_call_in_the_assert(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given('a value'):
                x = 1
            with then('it stays one'):
                assert x == 1
        """,
    )
    scenario = _scenario(
        [
            _step('given', 'a value', _line(src, 'with given')),
            _step('then', 'it stays one', _line(src, 'with then')),
        ]
    )
    assert _rule_findings(run_ast_rules([scenario], tmp_path), 'action-in-then') == []


def test_action_in_then_when_then_pair_acts_without_a_call(tmp_path) -> None:
    # The pair wraps the act by definition; a subscript raise is still acting,
    # and the pair's then never contributes to the then-side scan.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with when_then('looking up', 'it is missing'), pytest.raises(KeyError):
                mapping[key]
            with then('the log calls it out'):
                assert log.count('missing') == 1
        """,
    )
    pair_line = _line(src, 'with when_then')
    scenario = _scenario(
        [
            _step('when', 'looking up', pair_line),
            _step('then', 'it is missing', pair_line),
            _step('then', 'the log calls it out', _line(src, "with then('the log")),
        ]
    )
    assert _rule_findings(run_ast_rules([scenario], tmp_path), 'action-in-then') == []


def test_action_in_then_skips_scenario_with_anchorless_when(tmp_path) -> None:
    # Unknowable beats wrong: a `when` without an anchor may well act.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with then('it brews'):
                assert brew() == 'coffee'
        """,
    )
    scenario = _scenario(
        [
            _step('when', 'acting somewhere unseen', None),
            _step('then', 'it brews', _line(src, 'with then')),
        ]
    )
    assert _rule_findings(run_ast_rules([scenario], tmp_path), 'action-in-then') == []


def test_action_in_then_reports_once_per_scenario(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with then('it brews'):
                assert brew() == 'coffee'
            with then('it grinds'):
                assert grind() == 'powder'
        """,
    )
    scenario = _scenario(
        [
            _step('then', 'it brews', _line(src, "with then('it brews')")),
            _step('then', 'it grinds', _line(src, "with then('it grinds')")),
        ]
    )
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'action-in-then')
    assert len(findings) == 1


# --- Rule 5: unused-interpolation ---


def _value_step(phase, text, line, expressions, children=()):
    parts = [
        NarrationValue(rendered='<v>', expression=expression)
        for expression in expressions
    ]
    step = _step(phase, text, line, children)
    return dataclasses.replace(step, narration=Narration(text=text, parts=parts))


@scenario(
    t'{pg["Narration lint"]} flags a {pg["Narration"].low} interpolating a name the '
    t'body never uses',
    story=adopt_pytest_given,
)
def test_unused_interpolation_fires_on_unused_bare_identifier(tmp_path) -> None:
    with given(t'a given {pg["Step"].low} whose body never loads the name'):
        # The `{size}` inside the step's own t-string narration must not count
        # as a use — only code uses count.
        src = _write(
            tmp_path,
            """\
            def test_a():
                with given(t'a {size} ml cup'):
                    cup = make_cup()
            """,
        )
        attach('step body', src)
        with_line = _line(src, 'with given')
        unused = _scenario([_value_step('given', 'a 200 ml cup', with_line, ['size'])])
    with when(t'the AST {pg["Lint rule"]("rules")} parse that source', activity=11):
        findings = _rule_findings(
            run_ast_rules([unused], tmp_path), 'unused-interpolation'
        )
    with then(t'a warn {pg["Finding"].low} names the interpolation the body ignores'):
        [finding] = findings
        assert finding.message == (
            "given 'a 200 ml cup' interpolates {size} but never uses it"
        )
        assert finding.location == SourceLocation(relpath='test_x.py', line=with_line)


def test_unused_interpolation_fires_on_a_grouped_placeholder(tmp_path) -> None:
    """The lint runs on *grouped* scenarios, where a varying interpolation is
    already a placeholder rather than a value. Scanning only values leaves the
    rule blind to every parametrized scenario — the ones with the most
    narration to drift."""
    src = _write(
        tmp_path,
        """\
        def test_a(size):
            with given(t'a {size} ml cup'):
                cup = make_cup()
        """,
    )
    with_line = _line(src, 'with given')
    step = _step('given', 'a {size} ml cup', with_line)
    step = dataclasses.replace(
        step,
        narration=Narration(
            text='a {size} ml cup',
            parts=[NarrationPlaceholder(name='size', column_id='size')],
        ),
    )
    findings = _rule_findings(
        run_ast_rules([_scenario([step])], tmp_path), 'unused-interpolation'
    )
    [finding] = findings
    assert 'interpolates {size} but never uses it' in finding.message


def test_unused_interpolation_skips_a_disambiguated_column_name(tmp_path) -> None:
    """A column whose name was disambiguated (`size #2`) is not a bare
    identifier and drops out with the complex expressions. `ast.parse` alone
    would read `#2` as a comment and report the step under `{size}`, a token
    the report never shows — the reader would go looking for it in vain."""
    src = _write(
        tmp_path,
        """\
        def test_a(size):
            with given(t'a {size} ml cup'):
                cup = make_cup()
        """,
    )
    with_line = _line(src, 'with given')
    step = _step('given', 'a {size #2} ml cup', with_line)
    step = dataclasses.replace(
        step,
        narration=Narration(
            text='a {size #2} ml cup',
            parts=[NarrationPlaceholder(name='size #2', column_id='derived:0')],
        ),
    )
    assert (
        _rule_findings(
            run_ast_rules([_scenario([step])], tmp_path), 'unused-interpolation'
        )
        == []
    )


def test_unused_interpolation_passes_when_the_name_is_loaded(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given(t'a {size} ml cup'):
                cup = make_cup(size)
        """,
    )
    scenario = _scenario(
        [_value_step('given', 'a 200 ml cup', _line(src, 'with given'), ['size'])]
    )
    assert (
        _rule_findings(run_ast_rules([scenario], tmp_path), 'unused-interpolation')
        == []
    )


def test_unused_interpolation_store_counts_for_given(tmp_path) -> None:
    # The step *binding* the name is an honest given.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given(t'a {size} ml cup'):
                size = compute()
        """,
    )
    scenario = _scenario(
        [_value_step('given', 'a 200 ml cup', _line(src, 'with given'), ['size'])]
    )
    assert (
        _rule_findings(run_ast_rules([scenario], tmp_path), 'unused-interpolation')
        == []
    )


def test_unused_interpolation_store_does_not_count_for_when(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with when(t'inserting {amount}'):
                amount = compute()
        """,
    )
    scenario = _scenario(
        [_value_step('when', 'inserting 2', _line(src, 'with when'), ['amount'])]
    )
    findings = _rule_findings(
        run_ast_rules([scenario], tmp_path), 'unused-interpolation'
    )
    assert len(findings) == 1


@pytest.mark.parametrize('expression', ['machine["coffees"]', 'str(x)', '!!'])
def test_unused_interpolation_skips_complex_expressions(tmp_path, expression) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given(t'a loaded machine'):
                y = 1
        """,
    )
    scenario = _scenario(
        [
            _value_step(
                'given', 'a loaded machine', _line(src, 'with given'), [expression]
            )
        ]
    )
    assert (
        _rule_findings(run_ast_rules([scenario], tmp_path), 'unused-interpolation')
        == []
    )


def test_unused_interpolation_skips_term_refs(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given(t'a {pg["File glossary"]} on disk'):
                y = 1
        """,
    )
    step = _step('given', 'a File glossary on disk', _line(src, 'with given'))
    step = dataclasses.replace(
        step,
        narration=Narration(
            text='a File glossary on disk',
            parts=[
                NarrationTermRef(
                    term_id=TermId('file-glossary'),
                    display='File glossary',
                    expression='pg["File glossary"]',
                )
            ],
        ),
    )
    assert (
        _rule_findings(
            run_ast_rules([_scenario([step])], tmp_path), 'unused-interpolation'
        )
        == []
    )


def test_unused_interpolation_counts_use_in_nested_step_body(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given(t'a {size} ml cup'):
                with given('poured'):
                    cup = pour(size)
        """,
    )
    inner = _step('given', 'poured', _line(src, "with given('poured')"))
    outer = _value_step(
        'given', 'a 200 ml cup', _line(src, 'with given(t'), ['size'], [inner]
    )
    assert (
        _rule_findings(
            run_ast_rules([_scenario([outer])], tmp_path), 'unused-interpolation'
        )
        == []
    )


def test_unused_interpolation_nested_narration_does_not_count_as_use(
    tmp_path,
) -> None:
    # A nested step re-narrating {x} still parades a value the code ignores.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given(t'a {x} thing'):
                with given(t'still about {x}'):
                    y = 1
        """,
    )
    inner = _step('given', 'still about 1', _line(src, 'still about'))
    outer = _value_step(
        'given', 'a 1 thing', _line(src, "with given(t'a"), ['x'], [inner]
    )
    findings = _rule_findings(
        run_ast_rules([_scenario([outer])], tmp_path), 'unused-interpolation'
    )
    assert len(findings) == 1


def test_unused_interpolation_use_in_a_with_item_counts(tmp_path) -> None:
    # e.g. a pytest.raises match built from the interpolated value.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with then(t'rejects {code}'), pytest.raises(ValueError, match=str(code)):
                act()
        """,
    )
    scenario = _scenario(
        [_value_step('then', 'rejects 404', _line(src, 'with then'), ['code'])]
    )
    assert (
        _rule_findings(run_ast_rules([scenario], tmp_path), 'unused-interpolation')
        == []
    )


def test_unused_interpolation_skips_template_helper_steps(tmp_path) -> None:
    # Decorated helpers are out of scope in v1: signature validation already
    # ties each placeholder to a parameter.
    src = _write(
        tmp_path,
        """\
        @when(Template('I insert ${amount}'))
        def insert(amount):
            return 1
        """,
    )
    scenario = _scenario(
        [_value_step('when', 'I insert $2', _line(src, '@when'), ['amount'])]
    )
    assert (
        _rule_findings(run_ast_rules([scenario], tmp_path), 'unused-interpolation')
        == []
    )


def test_unused_interpolation_dedupes_repeated_names(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given(t'{size} of {size}'):
                y = 1
        """,
    )
    scenario = _scenario(
        [_value_step('given', '200 of 200', _line(src, 'with given'), ['size', 'size'])]
    )
    findings = _rule_findings(
        run_ast_rules([scenario], tmp_path), 'unused-interpolation'
    )
    assert len(findings) == 1


def test_action_in_then_plain_when_acts_via_subscript(tmp_path) -> None:
    # An indexing action (a lookup) is acting, same as the when_then
    # rationale — tuned on this repo's suite, where `glossary['Guest']`
    # in a plain `when` false-positived under a call-only test.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with when('the term is looked up in three cases'):
                handles = [glossary['Guest'], glossary['guest']]
            with then('every lookup resolves'):
                assert all(isinstance(h, Handle) for h in handles)
        """,
    )
    scenario = _scenario(
        [
            _step(
                'when', 'the term is looked up in three cases', _line(src, 'with when')
            ),
            _step('then', 'every lookup resolves', _line(src, 'with then')),
        ]
    )
    assert _rule_findings(run_ast_rules([scenario], tmp_path), 'action-in-then') == []


def test_empty_step_fires_on_empty_async_helper_function(tmp_path) -> None:
    # `async def` is an AsyncFunctionDef, not a FunctionDef subclass, so it
    # needs its own arm in the index — a decorated coroutine step is anchored
    # exactly like a sync one and must reach the same rules.
    src = _write(
        tmp_path,
        """\
        @when('inserting money')
        async def insert():
            ...
        """,
    )
    scenario = _scenario([_step('when', 'inserting money', _line(src, '@when'))])
    [finding] = run_ast_rules([scenario], tmp_path)
    assert finding.rule == RuleId('empty-step')


def test_action_in_then_sees_through_an_async_when(tmp_path) -> None:
    # An unresolved `when` returns None for the whole scenario, so an async
    # helper that failed to anchor used to disable this rule for every step
    # beside it. This `when` does not act, so the rule must fire on the then.
    src = _write(
        tmp_path,
        """\
        @when('inserting money')
        async def insert():
            pass

        def test_a():
            with then('it dispenses'):
                assert machine.dispense() == 1
        """,
    )
    scenario = _scenario(
        [
            _step('when', 'inserting money', _line(src, '@when')),
            _step('then', 'it dispenses', _line(src, 'with then(')),
        ]
    )
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'action-in-then')
    assert len(findings) == 1
