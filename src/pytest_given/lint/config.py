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
    """The two ini options, parsed, and the rule severities they resolve to."""

    levels: dict[RuleId, Level]
    ignores: list[IgnoreEntry]

    @property
    def effective(self) -> dict[RuleId, Level]:
        """Every known rule's level, configured overrides over the defaults."""
        return DEFAULTS | self.levels

    @property
    def enabled(self) -> frozenset[RuleId]:
        """The rules whose effective level is not ``off``.

        Handed to the rule runners so a disabled rule does not run at all,
        which is what the spec means by ``off``. Resolving severities
        afterwards still drops an ``off`` finding — `apply_config` stays the
        authority for a caller that assembled findings itself — but nothing
        computes one in a normal run.
        """
        return frozenset(
            rule for rule, level in self.effective.items() if level != 'off'
        )


def parse_lint_config(rule_lines: list[str], ignore_lines: list[str]) -> LintConfig:
    return LintConfig(
        levels=parse_rule_levels(rule_lines),
        ignores=parse_ignore_entries(ignore_lines),
    )


def parse_rule_levels(lines: list[str]) -> dict[RuleId, Level]:
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
    parse as bare patterns. A rule-shaped prefix that names no known rule is a
    typo worth reporting, *unless* what follows is itself a node id: that is
    how a Windows drive letter arrives (``c:/repo/tests/t.py::test_x``), where
    the prefix is part of a path rather than a rule scope.
    """
    entries: list[IgnoreEntry] = []
    for line in lines:
        prefix, sep, rest = line.partition(':')
        rule = RuleId(prefix.strip())
        if sep and _RULE_PREFIX_RE.fullmatch(rule):
            if rule in DEFAULTS:
                entries.append(IgnoreEntry(raw=line, rule=rule, pattern=rest.strip()))
                continue
            if '::' not in rest:
                raise PytestGivenError(
                    f'unknown rule prefix {rule!r} in given_lint_ignore entry '
                    f'{line!r} (known: {", ".join(sorted(DEFAULTS))}).'
                )
        entries.append(IgnoreEntry(raw=line, rule=None, pattern=line.strip()))
    return entries


def apply_config(findings: list[RawFinding], config: LintConfig) -> list[Finding]:
    """Resolve raw rule findings against the configuration, in report order.

    Rules configured ``off`` are dropped *before* ignore matching, so an entry
    scoped to a disabled rule counts as stale — the same outcome as a rule the
    runners skipped for being off, which produces no finding to suppress.

    The ordering lives here, not in `summary`, because it cannot be
    reconstructed downstream: the ``stale-ignore`` findings are appended
    *after* the sort so they come last, and they carry no location, so a
    consumer re-sorting the whole list would pull them to the front.
    `summary_rows` renders the order it is given.
    """
    effective = config.effective
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
    return Finding(**vars(raw), severity=level)


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
