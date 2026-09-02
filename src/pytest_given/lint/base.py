"""Shared lint vocabulary: the finding models and the rule catalog.

Rules emit `RawFinding`s; `config.apply_config` is the only thing that turns
one into a `Finding`, which is why severity narrows to what can actually be
printed. Rule ids are constants so a typo is an import-time NameError.
"""

from dataclasses import dataclass
from typing import Literal, NewType

from ..model import SourceLocation

type Level = Literal['off', 'warn', 'error']
type Severity = Literal['warn', 'error']

RuleId = NewType('RuleId', str)

MISSING_PHASE = RuleId('missing-phase')
EMPTY_STEP = RuleId('empty-step')
THEN_WITHOUT_CHECK = RuleId('then-without-check')
CHECK_OUTSIDE_THEN = RuleId('check-outside-then')
ACTION_IN_THEN = RuleId('action-in-then')
UNUSED_INTERPOLATION = RuleId('unused-interpolation')
TAG_SHADOWS_TERM = RuleId('tag-shadows-term')
DEAD_TERM = RuleId('dead-term')

# Pseudo-rule for ignore-list entries that suppressed nothing; always an
# error, never configurable or ignorable — so it is absent from DEFAULTS.
STALE_IGNORE = RuleId('stale-ignore')

LEVELS: tuple[Level, ...] = ('off', 'warn', 'error')

DEFAULTS: dict[RuleId, Level] = {
    MISSING_PHASE: 'warn',
    EMPTY_STEP: 'error',
    THEN_WITHOUT_CHECK: 'error',
    CHECK_OUTSIDE_THEN: 'warn',
    ACTION_IN_THEN: 'warn',
    UNUSED_INTERPOLATION: 'warn',
    TAG_SHADOWS_TERM: 'warn',
    DEAD_TERM: 'off',
}


@dataclass(frozen=True, kw_only=True)
class RawFinding:
    """What a rule emits, before configured severities and ignores apply."""

    rule: RuleId
    subject: str
    location: SourceLocation | None
    message: str


@dataclass(frozen=True, kw_only=True)
class Finding:
    """A raw finding resolved against the configuration, ready to print."""

    rule: RuleId
    severity: Severity
    subject: str
    location: SourceLocation | None
    message: str
