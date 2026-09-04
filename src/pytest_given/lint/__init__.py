"""Narration lint: rules that catch steps whose narration lies about their body.

Pure inspection of the built report model plus the AST of the step bodies the
run itself identified — no pytest imports — so every rule is unit-testable in
isolation. `run_lint` is the whole pass and what a caller wants; the rule
runners underneath it emit `RawFinding`s, which `apply_config` resolves against
the configured severities and ignore globs into the `Finding`s the plugin
prints (docs/specs/2026-07-05-narration-lint-design.md).
"""

from .base import DEFAULTS, Finding, Level, RawFinding, RuleId, Severity
from .config import IgnoreEntry, LintConfig, apply_config, parse_lint_config
from .runner import run_lint
from .summary import error_count, summary_rows, summary_title

__all__ = [
    'DEFAULTS',
    'Finding',
    'IgnoreEntry',
    'Level',
    'LintConfig',
    'RawFinding',
    'RuleId',
    'Severity',
    'apply_config',
    'error_count',
    'parse_lint_config',
    'run_lint',
    'summary_rows',
    'summary_title',
]
