"""The lint as one pass: run every enabled rule, resolve what they found."""

from pathlib import Path

from ..model import Glossary, Scenario, Story
from .ast_rules import run_ast_rules
from .base import Finding
from .config import LintConfig, apply_config
from .runtime_rules import run_runtime_rules


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
