"""Shared lint vocabulary: the Finding model and the rule catalog.

The catalog is data (`RULES`), so config validation, severity defaults, and
docs stay in sync with one table.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal, NewType

from ..model import NodeId, SourceLocation

type Level = Literal['off', 'warn', 'error']
type Surface = Literal['runtime', 'ast']

RuleId = NewType('RuleId', str)

# Pseudo-rule for ignore-list entries that suppressed nothing; always an
# error, never configurable or ignorable — the list stays honest by
# construction.
STALE_IGNORE = RuleId('stale-ignore')

LEVELS: tuple[Level, ...] = ('off', 'warn', 'error')


@dataclass(frozen=True, kw_only=True)
class Finding:
    """One lint finding, ready for the terminal summary."""

    rule: RuleId
    severity: Level
    subject: str
    node_id: NodeId | None
    location: SourceLocation | None
    message: str


@dataclass(frozen=True, kw_only=True)
class LintRule:
    id: RuleId
    surface: Surface
    default: Level


# The rule catalog as data: config validation and docs stay in sync with this
# one table.
RULES: tuple[LintRule, ...] = (
    LintRule(id=RuleId('missing-phase'), surface='runtime', default='warn'),
    LintRule(id=RuleId('empty-step'), surface='ast', default='error'),
    LintRule(id=RuleId('then-without-check'), surface='ast', default='error'),
    LintRule(id=RuleId('check-outside-then'), surface='ast', default='warn'),
    LintRule(id=RuleId('action-in-then'), surface='ast', default='warn'),
    LintRule(id=RuleId('unused-interpolation'), surface='ast', default='warn'),
    LintRule(id=RuleId('divergent-case-structure'), surface='runtime', default='warn'),
    LintRule(id=RuleId('tag-shadows-term'), surface='runtime', default='warn'),
    LintRule(id=RuleId('dead-term'), surface='runtime', default='off'),
)

RULES_BY_ID: dict[RuleId, LintRule] = {rule.id: rule for rule in RULES}


def location_suffix(location: SourceLocation | None) -> str:
    """The `` (filename:line)`` locator appended to a finding message, or ``''``
    when the finding carries no source location."""
    if location is None:
        return ''
    return f' ({PurePosixPath(location.relpath).name}:{location.line})'
