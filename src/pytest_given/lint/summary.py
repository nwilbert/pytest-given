"""The terminal presentation of a run's lint findings.

Formatting only — the title, the aligned finding rows, the error tally. The
plugin owns the writing (and the exit code); this owns what the reader sees,
so the wording and the column alignment live beside the findings they
describe rather than in the pytest hook that happens to print them.
"""

from .base import Finding


def error_count(findings: list[Finding]) -> int:
    """How many findings are error-level — what fails the run."""
    return sum(1 for finding in findings if finding.severity == 'error')


def summary_title(findings: list[Finding]) -> str:
    """The separator headline: how much was found, and how much of it fails."""
    errors = error_count(findings)
    return (
        f'pytest-given: narration lint '
        f'({_count(len(findings), "finding")}, {_count(errors, "error")})'
    )


def summary_rows(findings: list[Finding]) -> list[str]:
    """One aligned row per finding: severity, rule, subject, message.

    Rule and subject are padded to the widest in *this* run rather than to a
    fixed width, so the messages line up without a short run carrying columns
    of blanks for a rule id it never hit.
    """
    if not findings:
        return []
    rule_width = max(len(finding.rule) for finding in findings)
    subject_width = max(len(finding.subject) for finding in findings)
    return [
        f'{finding.severity.upper():<5} {finding.rule:<{rule_width}}  '
        f'{finding.subject:<{subject_width}}  {finding.message}'
        for finding in findings
    ]


def _count(n: int, noun: str) -> str:
    return f'{n} {noun}' if n == 1 else f'{n} {noun}s'
