"""Unit tests for the lint findings' terminal presentation (`lint/summary.py`)."""

from pytest_given.lint import (
    Finding,
    RuleId,
    Severity,
    error_count,
    summary_rows,
    summary_title,
)
from pytest_given.model import SourceLocation


def _finding(
    rule: str = 'empty-step',
    severity: Severity = 'error',
    subject: str = 'tests/t.py::test_a',
    message: str = 'has no code',
    location: SourceLocation | None = None,
) -> Finding:
    return Finding(
        rule=RuleId(rule),
        severity=severity,
        subject=subject,
        location=location,
        message=message,
    )


def test_error_count_counts_only_error_level() -> None:
    findings = [
        _finding(severity='error'),
        _finding(severity='warn'),
        _finding(severity='error'),
    ]
    assert error_count(findings) == 2


def test_summary_title_pluralizes_each_count_independently() -> None:
    findings = [_finding(severity='error'), _finding(severity='warn')]
    assert summary_title(findings) == (
        'pytest-given: narration lint (2 findings, 1 error)'
    )


def test_summary_title_singular_finding_reads_singular() -> None:
    assert summary_title([_finding()]) == (
        'pytest-given: narration lint (1 finding, 1 error)'
    )


def test_summary_rows_pad_rule_and_subject_to_the_widest_in_the_run() -> None:
    """Alignment is per run, so a short run carries no blanks for a rule it
    never hit."""
    rows = summary_rows(
        [
            _finding(rule='empty-step', subject='t.py::a', message='first'),
            _finding(rule='then-without-check', subject='t.py::longer', message='2nd'),
        ]
    )
    assert rows == [
        'ERROR empty-step          t.py::a       first',
        'ERROR then-without-check  t.py::longer  2nd',
    ]


def test_summary_rows_append_the_location_when_a_finding_has_one() -> None:
    """The location is a column of its own, not text baked into the message —
    so a rule that forgets to mention it still shows where it fired."""
    rows = summary_rows(
        [_finding(location=SourceLocation(relpath='pkg/t.py', line=12))]
    )
    assert rows == ['ERROR empty-step  tests/t.py::test_a  has no code (t.py:12)']


def test_summary_rows_of_nothing_is_nothing() -> None:
    """The widths come from a `max` over the findings, so the empty case has to
    short-circuit rather than reach it."""
    assert summary_rows([]) == []
