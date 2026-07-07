import dataclasses
import textwrap

import pytest

from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    Glossary,
    GlossaryTerm,
    Narration,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    Scenario,
    SourceLocation,
    Step,
    Story,
    StoryId,
    TermId,
    id_derive,
)
from pytest_given.report.lint import (
    Finding,
    RuleId,
    apply_config,
    parse_ignore_entries,
    parse_rule_levels,
    run_ast_rules,
    run_runtime_rules,
)


def _finding(
    rule: str = 'empty-step',
    subject: str = 'tests/t.py::test_a',
    relpath: str = 'tests/t.py',
    line: int = 3,
) -> Finding:
    return Finding(
        rule=RuleId(rule),
        severity='error',
        subject=subject,
        node_id=NodeId(subject),
        location=SourceLocation(relpath=relpath, line=line),
        message='m',
    )


# --- rule-level overrides (given_lint_rules) ---


def test_parse_rule_levels_reads_overrides() -> None:
    assert parse_rule_levels(['empty-step=warn', 'then-without-check=off']) == {
        RuleId('empty-step'): 'warn',
        RuleId('then-without-check'): 'off',
    }


def test_parse_rule_levels_rejects_unknown_rule() -> None:
    with pytest.raises(ValueError, match='bogus-rule'):
        parse_rule_levels(['bogus-rule=warn'])


def test_parse_rule_levels_rejects_unknown_level() -> None:
    with pytest.raises(ValueError, match='loud'):
        parse_rule_levels(['empty-step=loud'])


def test_parse_rule_levels_rejects_entry_without_equals() -> None:
    with pytest.raises(ValueError, match='rule-id=level'):
        parse_rule_levels(['empty-step warn'])


# --- ignore entries (given_lint_ignore) ---


def test_parse_ignore_entries_bare_glob_applies_to_all_rules() -> None:
    [entry] = parse_ignore_entries(['tests/unit/*::test_*'])
    assert entry.rule is None
    assert entry.pattern == 'tests/unit/*::test_*'


def test_parse_ignore_entries_rule_scoped_entry() -> None:
    [entry] = parse_ignore_entries(['empty-step: tests/t.py::test_a'])
    assert entry.rule == RuleId('empty-step')
    assert entry.pattern == 'tests/t.py::test_a'


def test_parse_ignore_entries_node_id_colons_are_not_a_rule_prefix() -> None:
    [entry] = parse_ignore_entries(['*::test_*_raises'])
    assert entry.rule is None
    assert entry.pattern == '*::test_*_raises'


def test_parse_ignore_entries_rejects_unknown_rule_prefix() -> None:
    with pytest.raises(ValueError, match='dead-trem'):
        parse_ignore_entries(['dead-trem: legacy-*'])


# --- apply_config: severities, suppression, stale entries, report order ---


def test_apply_config_maps_catalog_default_severity() -> None:
    [out] = apply_config([_finding()], {}, [])
    assert out.severity == 'error'


def test_apply_config_override_demotes_to_warn() -> None:
    [out] = apply_config([_finding()], {RuleId('empty-step'): 'warn'}, [])
    assert out.severity == 'warn'


def test_apply_config_off_rule_drops_findings() -> None:
    assert apply_config([_finding()], {RuleId('empty-step'): 'off'}, []) == []


def test_apply_config_bare_glob_suppresses_any_rule() -> None:
    findings = [_finding(rule='empty-step'), _finding(rule='then-without-check')]
    out = apply_config(findings, {}, parse_ignore_entries(['tests/t.py::*']))
    assert out == []


def test_apply_config_rule_scoped_glob_suppresses_only_its_rule() -> None:
    findings = [_finding(rule='empty-step'), _finding(rule='then-without-check')]
    out = apply_config(findings, {}, parse_ignore_entries(['empty-step: tests/*']))
    assert [f.rule for f in out] == [RuleId('then-without-check')]


def test_apply_config_stale_entry_becomes_error_finding() -> None:
    out = apply_config([], {}, parse_ignore_entries(['empty-step: no-match-*']))
    [stale] = out
    assert stale.rule == RuleId('stale-ignore')
    assert stale.severity == 'error'
    assert stale.subject == 'empty-step: no-match-*'
    assert 'suppressed no finding' in stale.message


def test_apply_config_suppressing_entry_is_not_stale() -> None:
    out = apply_config([_finding()], {}, parse_ignore_entries(['tests/t.py::*']))
    assert out == []


def test_apply_config_entry_scoped_to_an_off_rule_is_stale() -> None:
    # The off rule's findings are dropped before ignore matching, so the entry
    # suppresses nothing — stale by definition, per the spec.
    out = apply_config(
        [_finding(rule='empty-step')],
        {RuleId('empty-step'): 'off'},
        parse_ignore_entries(['empty-step: tests/t.py::*']),
    )
    [stale] = out
    assert stale.rule == RuleId('stale-ignore')


def test_apply_config_orders_errors_first_then_by_location() -> None:
    demoted = _finding(rule='then-without-check', relpath='b.py', line=9)
    late = _finding(rule='empty-step', relpath='z.py', line=1)
    early = _finding(rule='empty-step', relpath='a.py', line=5)
    out = apply_config(
        [demoted, late, early], {RuleId('then-without-check'): 'warn'}, []
    )
    assert [(f.severity, f.location.relpath) for f in out] == [
        ('error', 'a.py'),
        ('error', 'z.py'),
        ('warn', 'b.py'),
    ]


def test_apply_config_stale_entries_come_last() -> None:
    out = apply_config(
        [_finding()],
        {},
        parse_ignore_entries(['then-without-check: no-match-*']),
    )
    assert [f.rule for f in out] == [
        RuleId('empty-step'),
        RuleId('stale-ignore'),
    ]


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


def test_empty_step_fires_on_pass_only_body(tmp_path) -> None:
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given('a value'):
                pass
        """,
    )
    with_line = _line(src, "with given('a value')")
    scenario = _scenario([_step('given', 'a value', with_line)])
    [finding] = run_ast_rules([scenario], tmp_path)
    assert finding.rule == RuleId('empty-step')
    assert finding.severity == 'error'
    assert finding.subject == 'test_x.py::test_a'
    assert finding.node_id == NodeId('test_x.py::test_a')
    assert finding.location == SourceLocation(relpath='test_x.py', line=with_line)
    assert finding.message == (f"given 'a value' has no code (test_x.py:{with_line})")


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


def test_then_without_check_fires(tmp_path) -> None:
    # Neither a plain call, nor a call through a subscripted callable, counts
    # as a check.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with then('it is one'):
                x = compute()
                handlers[0](x)
        """,
    )
    with_line = _line(src, 'with then')
    scenario = _scenario([_step('then', 'it is one', with_line)])
    [finding] = run_ast_rules([scenario], tmp_path)
    assert finding.rule == RuleId('then-without-check')
    assert finding.message == (
        f"then 'it is one' contains no assertion (test_x.py:{with_line})"
    )


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


@pytest.mark.parametrize('phase', ['given', 'when'])
def test_check_outside_then_fires_on_assert_in_given_or_when(tmp_path, phase) -> None:
    src = _write(
        tmp_path,
        f"""\
        def test_a():
            with {phase}('a stocked machine'):
                machine = stock()
                assert machine['coffees'] > 0
        """,
    )
    with_line = _line(src, 'with ')
    scenario = _scenario([_step(phase, 'a stocked machine', with_line)])
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'check-outside-then')
    [finding] = findings
    assert finding.severity == 'warn'
    assert finding.message == (
        f"assert inside {phase} 'a stocked machine' (test_x.py:{with_line})"
    )


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


def test_action_in_then_fires_when_no_when_exists(tmp_path) -> None:
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
    then_line = _line(src, 'with then')
    scenario = _scenario(
        [
            _step('given', 'a machine', _line(src, 'with given')),
            _step('then', 'it brews', then_line),
        ]
    )
    findings = _rule_findings(run_ast_rules([scenario], tmp_path), 'action-in-then')
    [finding] = findings
    assert finding.severity == 'warn'
    assert finding.subject == 'test_x.py::test_a'
    assert finding.location == SourceLocation(relpath='test_x.py', line=then_line)
    assert finding.message == (
        f"then 'it brews' folds the action into its assertion; "
        f'no when acts (test_x.py:{then_line})'
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


def test_unused_interpolation_fires_on_unused_bare_identifier(tmp_path) -> None:
    # The `{size}` inside the step's own t-string narration must not count as
    # a use — only code uses count.
    src = _write(
        tmp_path,
        """\
        def test_a():
            with given(t'a {size} ml cup'):
                cup = make_cup()
        """,
    )
    with_line = _line(src, 'with given')
    scenario = _scenario([_value_step('given', 'a 200 ml cup', with_line, ['size'])])
    findings = _rule_findings(
        run_ast_rules([scenario], tmp_path), 'unused-interpolation'
    )
    [finding] = findings
    assert finding.severity == 'warn'
    assert finding.message == (
        f"given 'a 200 ml cup' interpolates {{size}} but never uses it "
        f'(test_x.py:{with_line})'
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


# --- Runtime rules: missing-phase, divergent-case-structure,
# --- tag-shadows-term, dead-term ---


def _phases_scenario(node_id, phases, *, status='passed', steps=None, tags=None):
    return Scenario(
        id=NodeId(node_id),
        narration=Narration(text='S'),
        module='m',
        status=status,
        tags=tags or [],
        steps=steps if steps is not None else [_step(p, p, None) for p in phases],
        source=SourceLocation(relpath='test_x.py', line=7),
    )


def _runtime(grouped=(), per_case=(), glossary=None, stories=()):
    return run_runtime_rules(list(grouped), list(per_case), glossary, list(stories))


def test_missing_phase_fires_on_passed_two_phase_scenario() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given', 'then'])
    [finding] = _runtime(grouped=[scenario])
    assert finding.rule == RuleId('missing-phase')
    assert finding.severity == 'warn'
    assert finding.subject == 'test_x.py::test_a'
    assert finding.location == SourceLocation(relpath='test_x.py', line=7)
    assert finding.message == 'missing: when (test_x.py:7)'


def test_missing_phase_passes_a_complete_scenario() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given', 'when', 'then'])
    assert _runtime(grouped=[scenario]) == []


def test_missing_phase_skips_non_passed_scenarios() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given'], status='failed')
    assert _runtime(grouped=[scenario]) == []


def test_missing_phase_reports_in_canonical_gwt_order() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given'])
    [finding] = _runtime(grouped=[scenario])
    assert 'missing: when, then' in finding.message


def test_missing_phase_counts_phases_of_nested_steps() -> None:
    steps = [
        _step('given', 'g', None),
        _step('when', 'w', None, [_step('then', 't', None)]),
    ]
    scenario = _phases_scenario('test_x.py::test_a', [], steps=steps)
    assert _runtime(grouped=[scenario]) == []


def test_missing_phase_without_scenario_source_omits_location() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given', 'then'])
    scenario = dataclasses.replace(scenario, source=None)
    [finding] = _runtime(grouped=[scenario])
    assert finding.location is None
    assert finding.message == 'missing: when'


def _case(node_id, phases, *, status='passed'):
    return _phases_scenario(node_id, phases, status=status)


def test_divergent_case_structure_passes_matching_cases() -> None:
    cases = [
        _case('test_x.py::test_a[1]', ['given', 'when', 'then']),
        _case('test_x.py::test_a[2]', ['given', 'when', 'then']),
    ]
    assert _runtime(per_case=cases) == []


def test_divergent_case_structure_fires_once_naming_the_case() -> None:
    cases = [
        _case('test_x.py::test_a[1]', ['given', 'when', 'then']),
        _case('test_x.py::test_a[2]', ['given', 'then']),
        _case('test_x.py::test_a[3]', ['given', 'then']),
    ]
    [finding] = _runtime(per_case=cases)
    assert finding.rule == RuleId('divergent-case-structure')
    assert finding.severity == 'warn'
    assert finding.subject == 'test_x.py::test_a'
    assert '[2]' in finding.message
    assert '[3]' in finding.message


def test_divergent_case_structure_detects_nested_differences() -> None:
    nested = [
        _step('given', 'g', None),
        _step('when', 'w', None, [_step('when', 'sub', None)]),
        _step('then', 't', None),
    ]
    flat = [
        _step('given', 'g', None),
        _step('when', 'w', None),
        _step('then', 't', None),
    ]
    cases = [
        _phases_scenario('test_x.py::test_a[1]', [], steps=nested),
        _phases_scenario('test_x.py::test_a[2]', [], steps=flat),
    ]
    [finding] = _runtime(per_case=cases)
    assert finding.rule == RuleId('divergent-case-structure')


def test_divergent_case_structure_exempts_non_passed_cases() -> None:
    cases = [
        _case('test_x.py::test_a[1]', ['given', 'when', 'then']),
        _case('test_x.py::test_a[2]', ['given'], status='failed'),
        _case('test_x.py::test_a[3]', [], status='skipped'),
    ]
    assert _runtime(per_case=cases) == []


def test_divergent_case_structure_ignores_unparametrized_scenarios() -> None:
    cases = [
        _case('test_x.py::test_a', ['given', 'when', 'then']),
        _case('test_x.py::test_b', ['given', 'then']),
    ]
    assert _runtime(per_case=cases) == []


def _glossary(*names):
    return Glossary(
        terms=[
            GlossaryTerm(id=id_derive(name), kind=None, canonical=name)
            for name in names
        ]
    )


def test_tag_shadows_term_fires_once_per_unique_tag() -> None:
    glossary = _glossary('File glossary')
    scenarios = [
        _phases_scenario(
            'test_x.py::test_a', ['given', 'when', 'then'], tags=['File Glossary']
        ),
        _phases_scenario(
            'test_x.py::test_b', ['given', 'when', 'then'], tags=['File Glossary']
        ),
    ]
    [finding] = _rule_findings(
        _runtime(grouped=scenarios, glossary=glossary), 'tag-shadows-term'
    )
    assert finding.severity == 'warn'
    assert finding.subject == 'file-glossary'
    assert finding.message == (
        "tag 'File Glossary' duplicates glossary term 'File glossary' "
        '(2 scenarios, e.g. test_x.py::test_a)'
    )


def test_tag_shadows_term_passes_orthogonal_tags() -> None:
    glossary = _glossary('File glossary')
    scenarios = [
        _phases_scenario(
            'test_x.py::test_a', ['given', 'when', 'then'], tags=['happy-path']
        ),
    ]
    findings = _runtime(grouped=scenarios, glossary=glossary)
    assert _rule_findings(findings, 'tag-shadows-term') == []


def test_tag_shadows_term_needs_a_glossary() -> None:
    scenarios = [
        _phases_scenario(
            'test_x.py::test_a', ['given', 'when', 'then'], tags=['file-glossary']
        ),
    ]
    assert _runtime(grouped=scenarios, glossary=None) == []


def _term_ref_step(term):
    step = _step('given', f'a {term}', None)
    return dataclasses.replace(
        step,
        narration=Narration(
            text=f'a {term}',
            parts=[NarrationTermRef(term_id=id_derive(term), display=term)],
        ),
    )


def _dead_term_findings(glossary, grouped=(), stories=()):
    findings = _runtime(grouped=grouped, glossary=glossary, stories=stories)
    return _rule_findings(findings, 'dead-term')


def test_dead_term_flags_unreferenced_term() -> None:
    [finding] = _dead_term_findings(_glossary('Ghost term'))
    assert finding.subject == 'ghost-term'
    assert finding.severity == 'off'  # catalog default; apply_config drops it
    assert finding.message == "term 'Ghost term' is referenced by no step and no story"


def test_dead_term_passes_term_referenced_by_a_step() -> None:
    steps = [
        _term_ref_step('Ghost term'),
        _step('when', 'w', None),
        _step('then', 't', None),
    ]
    scenario = _phases_scenario('test_x.py::test_a', [], steps=steps)
    assert _dead_term_findings(_glossary('Ghost term'), grouped=[scenario]) == []


def test_dead_term_passes_term_referenced_by_a_scenario_name() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given', 'when', 'then'])
    scenario = dataclasses.replace(
        scenario,
        narration=Narration(
            text='about Ghost term',
            parts=[
                NarrationTermRef(term_id=id_derive('Ghost term'), display='Ghost term')
            ],
        ),
    )
    assert _dead_term_findings(_glossary('Ghost term'), grouped=[scenario]) == []


def test_dead_term_passes_term_referenced_by_a_story() -> None:
    story = Story(
        id=StoryId('s'),
        title='S',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(
                    ActivityPath(
                        parts=(
                            ActivityTermRef(
                                term_id=id_derive('Ghost term'), display='Ghost term'
                            ),
                        )
                    ),
                ),
            ),
        ),
    )
    assert _dead_term_findings(_glossary('Ghost term'), stories=[story]) == []


def test_dead_term_needs_a_glossary() -> None:
    assert _dead_term_findings(None) == []
