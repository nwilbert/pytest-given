"""Post-run check that flags scenarios missing a Given/When/Then phase.

Pure inspection of the built report model — no pytest imports — so the rule is
unit-testable in isolation. The plugin runs this over the grouped scenario list
at session finish and surfaces the result per the configured level.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch

from ..model import Phase, Scenario, Step

# Canonical Given/When/Then order, used both to test completeness and to report
# missing phases in reading order rather than alphabetically.
_PHASE_ORDER: tuple[Phase, ...] = ('given', 'when', 'then')


@dataclass(frozen=True)
class PhaseViolation:
    """A passed scenario that does not cover all three phases."""

    node_id: str
    missing: tuple[Phase, ...]


def scenario_phases(scenario: Scenario) -> set[Phase]:
    """The distinct phases present anywhere in the scenario's step tree."""
    phases: set[Phase] = set()

    def walk(steps: list[Step]) -> None:
        for step in steps:
            phases.add(step.phase)
            walk(step.children)

    walk(scenario.steps)
    return phases


def missing_phases(scenario: Scenario) -> tuple[Phase, ...]:
    """Phases absent from the scenario, in canonical Given/When/Then order."""
    present = scenario_phases(scenario)
    return tuple(phase for phase in _PHASE_ORDER if phase not in present)


def is_ignored(node_id: str, patterns: list[str]) -> bool:
    """Whether the node id matches any `fnmatch` ignore-list glob."""
    return any(fnmatch(node_id, pattern) for pattern in patterns)


def find_violations(
    scenarios: list[Scenario], ignore_patterns: list[str]
) -> list[PhaseViolation]:
    """Incomplete scenarios worth reporting: passed, not ignored, missing a phase.

    Non-passed scenarios are skipped — a skipped one records no steps and a
    failed one may be missing a phase only because it aborted mid-body.
    """
    violations: list[PhaseViolation] = []
    for scenario in scenarios:
        if scenario.status != 'passed':
            continue
        if is_ignored(scenario.id, ignore_patterns):
            continue
        missing = missing_phases(scenario)
        if missing:
            violations.append(PhaseViolation(node_id=scenario.id, missing=missing))
    return violations
