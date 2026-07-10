"""Unit tests for lint config parsing and application (`lint/config.py`)."""

import pytest

from pytest_given.lint import (
    Finding,
    RuleId,
    apply_config,
    parse_ignore_entries,
    parse_rule_levels,
)
from pytest_given.model import NodeId, SourceLocation


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
