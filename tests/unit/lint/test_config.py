"""Unit tests for lint config parsing and application (`lint/config.py`)."""

import re
from pathlib import Path

import pytest

from pytest_given.lint import (
    DEFAULTS,
    LintConfig,
    RawFinding,
    RuleId,
    apply_config,
)
from pytest_given.lint.config import parse_ignore_entries, parse_rule_levels
from pytest_given.model import PytestGivenError, SourceLocation


def _finding(
    rule: str = 'empty-step',
    subject: str = 'tests/t.py::test_a',
    relpath: str = 'tests/t.py',
    line: int = 3,
) -> RawFinding:
    return RawFinding(
        rule=RuleId(rule),
        subject=subject,
        location=SourceLocation(relpath=relpath, line=line),
        message='m',
    )


def _config(
    levels: dict[RuleId, str] | None = None, ignores: list[str] | None = None
) -> LintConfig:
    return LintConfig(
        levels=parse_rule_levels(
            [f'{rule}={level}' for rule, level in (levels or {}).items()]
        ),
        ignores=parse_ignore_entries(ignores or []),
    )


# --- rule-level overrides (given_lint_rules) ---


def test_parse_rule_levels_reads_overrides() -> None:
    assert parse_rule_levels(['empty-step=warn', 'then-without-check=off']) == {
        RuleId('empty-step'): 'warn',
        RuleId('then-without-check'): 'off',
    }


def test_parse_rule_levels_rejects_unknown_rule() -> None:
    with pytest.raises(PytestGivenError, match='bogus-rule'):
        parse_rule_levels(['bogus-rule=warn'])


def test_parse_rule_levels_rejects_unknown_level() -> None:
    with pytest.raises(PytestGivenError, match='loud'):
        parse_rule_levels(['empty-step=loud'])


def test_parse_rule_levels_rejects_entry_without_equals() -> None:
    with pytest.raises(PytestGivenError, match='rule-id=level'):
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
    with pytest.raises(PytestGivenError, match='dead-trem'):
        parse_ignore_entries(['dead-trem: legacy-*'])


# --- apply_config: severities, suppression, stale entries, report order ---


def test_apply_config_maps_catalog_default_severity() -> None:
    [out] = apply_config([_finding()], _config())
    assert out.severity == 'error'


def test_apply_config_override_demotes_to_warn() -> None:
    [out] = apply_config([_finding()], _config({RuleId('empty-step'): 'warn'}))
    assert out.severity == 'warn'


def test_apply_config_off_rule_drops_findings() -> None:
    assert apply_config([_finding()], _config({RuleId('empty-step'): 'off'})) == []


def test_apply_config_bare_glob_suppresses_any_rule() -> None:
    findings = [_finding(rule='empty-step'), _finding(rule='then-without-check')]
    out = apply_config(findings, _config(ignores=['tests/t.py::*']))
    assert out == []


def test_apply_config_rule_scoped_glob_suppresses_only_its_rule() -> None:
    findings = [_finding(rule='empty-step'), _finding(rule='then-without-check')]
    out = apply_config(findings, _config(ignores=['empty-step: tests/*']))
    assert [f.rule for f in out] == [RuleId('then-without-check')]


def test_apply_config_stale_entry_becomes_error_finding() -> None:
    out = apply_config([], _config(ignores=['empty-step: no-match-*']))
    [stale] = out
    assert stale.rule == RuleId('stale-ignore')
    assert stale.severity == 'error'
    assert stale.subject == 'empty-step: no-match-*'
    assert 'suppressed no finding' in stale.message


def test_apply_config_suppressing_entry_is_not_stale() -> None:
    out = apply_config([_finding()], _config(ignores=['tests/t.py::*']))
    assert out == []


def test_apply_config_ignore_matching_is_case_sensitive_cross_platform() -> None:
    # fnmatchcase (not fnmatch, which normcases on Windows): a case-mismatched
    # glob suppresses nothing on every platform, so the finding survives and
    # the entry is flagged stale.
    findings = [_finding(subject='tests/Foo.py::test_A')]
    out = apply_config(findings, _config(ignores=['tests/foo.py::test_a']))
    assert [f.rule for f in out] == [RuleId('empty-step'), RuleId('stale-ignore')]


def test_apply_config_entry_scoped_to_an_off_rule_is_stale() -> None:
    # The off rule's findings are dropped before ignore matching, so the entry
    # suppresses nothing — stale by definition, per the spec.
    out = apply_config(
        [_finding(rule='empty-step')],
        _config({RuleId('empty-step'): 'off'}, ignores=['empty-step: tests/t.py::*']),
    )
    [stale] = out
    assert stale.rule == RuleId('stale-ignore')


def test_apply_config_orders_errors_first_then_by_location() -> None:
    demoted = _finding(rule='then-without-check', relpath='b.py', line=9)
    late = _finding(rule='empty-step', relpath='z.py', line=1)
    early = _finding(rule='empty-step', relpath='a.py', line=5)
    out = apply_config(
        [demoted, late, early], _config({RuleId('then-without-check'): 'warn'})
    )
    assert [(f.severity, f.location.relpath) for f in out] == [
        ('error', 'a.py'),
        ('error', 'z.py'),
        ('warn', 'b.py'),
    ]


def test_apply_config_stale_entries_come_last() -> None:
    out = apply_config(
        [_finding()], _config(ignores=['then-without-check: no-match-*'])
    )
    assert [f.rule for f in out] == [
        RuleId('empty-step'),
        RuleId('stale-ignore'),
    ]


def test_the_documented_rule_tables_match_the_catalog() -> None:
    """README and the bundled authoring skill each hand-maintain a rule table.

    Nothing else notices when a rule is added, renamed, or has its default
    changed, and a downstream agent reads the skill's copy instead of the
    README — so both are checked against `DEFAULTS` here.
    """
    root = Path(__file__).resolve().parents[3]
    skill = (
        root
        / 'src/pytest_given/skills_data/pytest-given-authoring'
        / 'references/scenarios.md'
    )
    for doc in (root / 'README.md', skill):
        rows = dict(
            re.findall(
                r'^\| `([a-z][a-z0-9-]*)` \| `?(off|warn|error)`? \|',
                doc.read_text(encoding='utf-8'),
                re.MULTILINE,
            )
        )
        assert rows, f'no rule table found in {doc.name}'
        assert rows == {str(rule): level for rule, level in DEFAULTS.items()}, (
            f'{doc.name} rule table is out of sync with lint.DEFAULTS'
        )
