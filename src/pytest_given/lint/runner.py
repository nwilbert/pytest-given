"""The lint as one pass: run every enabled rule, resolve what they found."""

from pathlib import Path

from ..model import Glossary, Scenario, Story
from .ast_rules import AST_RULE_IDS, run_ast_rules
from .base import DEFAULTS, Finding, RuleId
from .config import LintConfig, apply_config
from .runtime_rules import RUNTIME_RULE_IDS, run_runtime_rules

# Every rule the two runners actually implement. `DEFAULTS` is what
# `given_lint_rules` validates against and what the documented rule tables are
# checked against, so the two sets have to be the same one: a catalogued rule
# with no runner would configure and document cleanly while never firing.
RULE_SURFACE: frozenset[RuleId] = AST_RULE_IDS | RUNTIME_RULE_IDS

assert set(DEFAULTS) == RULE_SURFACE, (
    f'lint rule catalog and runners disagree: {RULE_SURFACE ^ set(DEFAULTS)}'
)


def run_lint(
    scenarios: list[Scenario],
    glossary: Glossary | None,
    stories: list[Story],
    rootdir: Path,
    config: LintConfig,
) -> list[Finding]:
    """Every enabled rule, resolved against the configuration, in report order.

    The two runners and `apply_config` compose in exactly one way: severities
    and ignores apply to the *concatenation*, and `apply_config` reports an
    ignore entry that suppressed nothing — so a caller that resolved one
    runner's findings alone would call the other's entries stale. Composing it
    here makes that a property of this package rather than of whoever calls it.
    """
    return apply_config(
        run_runtime_rules(scenarios, glossary, stories, config.enabled)
        + run_ast_rules(scenarios, rootdir, config.enabled),
        config,
    )
