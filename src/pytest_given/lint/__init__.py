"""Narration lint: rules that catch steps whose narration lies about their body.

Pure inspection of the built report model plus the AST of the step bodies the
run itself identified — no pytest imports — so every rule is unit-testable in
isolation. `base` holds the Finding model and the rule catalog; `config`
parses the ini options and resolves raw findings against them;
`runtime_rules` and `ast_rules` hold the two rule surfaces. The plugin runs
the rule passes at session finish, applies the configured severities and
ignore globs via `apply_config`, and surfaces the findings per the design
spec (docs/specs/2026-07-05-narration-lint-design.md).
"""

from .ast_rules import run_ast_rules
from .base import (
    LEVELS,
    RULES,
    STALE_IGNORE,
    Finding,
    Level,
    LintRule,
    RuleId,
    Surface,
)
from .config import (
    IgnoreEntry,
    apply_config,
    parse_ignore_entries,
    parse_rule_levels,
)
from .runtime_rules import run_runtime_rules
from .summary import error_count, summary_rows, summary_title

__all__ = [
    'LEVELS',
    'RULES',
    'STALE_IGNORE',
    'Finding',
    'IgnoreEntry',
    'Level',
    'LintRule',
    'RuleId',
    'Surface',
    'apply_config',
    'error_count',
    'parse_ignore_entries',
    'parse_rule_levels',
    'run_ast_rules',
    'run_runtime_rules',
    'summary_rows',
    'summary_title',
]
