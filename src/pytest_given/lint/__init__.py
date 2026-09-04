"""Narration lint: rules that catch steps whose narration lies about their body.

Pure inspection of the built report model plus the AST of the step bodies the
run itself identified — no pytest imports — so every rule is unit-testable in
isolation. `run_lint` is the whole pass and the only thing a caller outside
this package needs; the rule runners and severity resolution underneath it stay
in their own modules (docs/specs/2026-07-05-narration-lint-design.md).
"""

from .base import DEFAULTS, Finding
from .config import LintConfig, parse_lint_config
from .runner import run_lint
from .summary import error_count, summary_rows, summary_title

__all__ = [
    'DEFAULTS',
    'Finding',
    'LintConfig',
    'error_count',
    'parse_lint_config',
    'run_lint',
    'summary_rows',
    'summary_title',
]
