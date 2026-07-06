import textwrap

import pytest

from pytest_given.model import Narration, NodeId, Scenario, SourceLocation, Step
from pytest_given.report.lint import (
    Finding,
    RuleId,
    apply_config,
    parse_ignore_entries,
    parse_rule_levels,
    run_ast_rules,
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
