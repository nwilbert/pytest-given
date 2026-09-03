"""Narration lint: rules that catch steps whose narration lies about their body.

Pure inspection of the built report model plus the AST of the step bodies the
run itself identified — no pytest imports — so every rule is unit-testable in
isolation. Rules emit `RawFinding`s; `apply_config` resolves them against the
configured severities and ignore globs into the `Finding`s the plugin prints
(docs/specs/2026-07-05-narration-lint-design.md).
"""

from .ast_rules import run_ast_rules
from .base import DEFAULTS, Finding, Level, RawFinding, RuleId, Severity
from .config import (
    IgnoreEntry,
    LintConfig,
    apply_config,
    enabled_rules,
    parse_lint_config,
)
from .runtime_rules import run_runtime_rules
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
    'enabled_rules',
    'error_count',
    'parse_lint_config',
    'run_ast_rules',
    'run_runtime_rules',
    'summary_rows',
    'summary_title',
]
