"""Lint configuration: parsing the `given_lint_rules` / `given_lint_ignore`
ini options and resolving raw rule findings against them."""

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase

from ..model import PytestGivenError
from .base import (
    DEFAULTS,
    LEVELS,
    STALE_IGNORE,
    Finding,
    Level,
    RawFinding,
    RuleId,
    Severity,
)

# Shape of a rule-scoped prefix in an ignore entry. Anything before the first
# ':' that does not match this (a node-id glob's path or '*', say) makes the
# whole entry a bare pattern.
_RULE_PREFIX_RE = re.compile(r'[a-z][a-z0-9-]*')


@dataclass(frozen=True, kw_only=True)
class IgnoreEntry:
    """One `given_lint_ignore` entry: a subject glob, optionally rule-scoped."""

    raw: str
    rule: RuleId | None
    pattern: str


@dataclass(frozen=True, kw_only=True)
class LintConfig:
    """The two ini options, parsed."""

    levels: dict[RuleId, Level]
    ignores: list[IgnoreEntry]


def parse_lint_config(rule_lines: list[str], ignore_lines: list[str]) -> LintConfig:
    return LintConfig(
        levels=parse_rule_levels(rule_lines),
        ignores=parse_ignore_entries(ignore_lines),
    )


def parse_rule_levels(lines: list[str]) -> dict[RuleId, Level]:
    """Parse `given_lint_rules` entries of the form ``rule-id=level``."""
    levels: dict[RuleId, Level] = {}
    for line in lines:
        rule_part, sep, level_part = line.partition('=')
        if not sep:
            raise PytestGivenError(
                f'invalid given_lint_rules entry {line!r}; expected rule-id=level.'
            )
        rule = RuleId(rule_part.strip())
        level = level_part.strip()
        if rule not in DEFAULTS:
            raise PytestGivenError(
                f'unknown rule {rule!r} in given_lint_rules '
                f'(known: {", ".join(sorted(DEFAULTS))}).'
            )
        if level not in LEVELS:
            raise PytestGivenError(
                f'unknown level {level!r} for rule {rule!r} in given_lint_rules; '
                f'expected one of {", ".join(LEVELS)}.'
            )
        levels[rule] = level
    return levels


def parse_ignore_entries(lines: list[str]) -> list[IgnoreEntry]:
    """Parse `given_lint_ignore` entries: subject globs with an optional
    ``rule-id:`` prefix.

    A prefix is only recognized when the text before the first ':' is shaped
    like a rule id — so node-id globs (``*::test_x``, ``tests/t.py::test_a``)
    parse as bare patterns.
    """
    entries: list[IgnoreEntry] = []
    for line in lines:
        prefix, sep, rest = line.partition(':')
        if sep and _RULE_PREFIX_RE.fullmatch(prefix.strip()):
            rule = RuleId(prefix.strip())
            if rule not in DEFAULTS:
                raise PytestGivenError(
                    f'unknown rule prefix {rule!r} in given_lint_ignore entry '
                    f'{line!r} (known: {", ".join(sorted(DEFAULTS))}).'
                )
            entries.append(IgnoreEntry(raw=line, rule=rule, pattern=rest.strip()))
        else:
            entries.append(IgnoreEntry(raw=line, rule=None, pattern=line.strip()))
    return entries


def apply_config(findings: list[RawFinding], config: LintConfig) -> list[Finding]:
    """Resolve raw rule findings against the configuration, in report order.

    Rules configured ``off`` are dropped *before* ignore matching, so an entry
    scoped to a disabled rule counts as stale. Every entry that suppressed
    nothing earns an error-level ``stale-ignore`` finding, appended after the
    errors-first, then file/line ordering.
    """
    effective = DEFAULTS | config.levels
    used: set[int] = set()
    kept: list[Finding] = []
    for raw in findings:
        level = effective[raw.rule]
        if level == 'off':
            continue
        suppressed = False
        for i, entry in enumerate(config.ignores):
            if entry.rule is not None and entry.rule != raw.rule:
                continue
            if fnmatchcase(raw.subject, entry.pattern):
                used.add(i)
                suppressed = True
        if not suppressed:
            kept.append(_resolved(raw, level))
    kept.sort(key=_report_order)
    kept.extend(
        Finding(
            rule=STALE_IGNORE,
            severity='error',
            subject=entry.raw,
            location=None,
            message='suppressed no finding',
        )
        for i, entry in enumerate(config.ignores)
        if i not in used
    )
    return kept


def _resolved(raw: RawFinding, level: Severity) -> Finding:
    return Finding(
        rule=raw.rule,
        severity=level,
        subject=raw.subject,
        location=raw.location,
        message=raw.message,
    )


def _report_order(finding: Finding) -> tuple[int, str, int, str, str]:
    relpath = finding.location.relpath if finding.location is not None else ''
    line = finding.location.line if finding.location is not None else 0
    return (
        0 if finding.severity == 'error' else 1,
        relpath,
        line,
        finding.rule,
        finding.subject,
    )
