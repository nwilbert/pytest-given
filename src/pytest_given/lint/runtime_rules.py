"""Runtime-surface rules: pure inspection of the recorded report model, no
source access needed."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import PurePosixPath

from ..model import (
    ActivityTermRef,
    Glossary,
    Narration,
    NarrationTermRef,
    NodeId,
    Phase,
    Scenario,
    Step,
    Story,
    TermId,
    case_suffix,
    id_derive,
    node_base,
)
from .base import RULES_BY_ID, Finding, RuleId, iter_steps


def run_runtime_rules(
    grouped: list[Scenario],
    per_case: list[Scenario],
    glossary: Glossary | None,
    stories: list[Story],
) -> list[Finding]:
    """Run the runtime-surface rules over the recorded report model.

    `missing-phase` and the glossary rules evaluate the grouped scenario list
    (one evaluation per logical scenario); `divergent-case-structure` needs
    the pre-grouping per-case list — the only place per-case step structure
    exists, since grouping collapses every case onto case 1's tree.
    """
    findings: list[Finding] = []
    findings.extend(_missing_phase_findings(grouped))
    findings.extend(_divergent_case_findings(per_case))
    if glossary is not None:
        findings.extend(_tag_shadows_term_findings(grouped, glossary))
        findings.extend(_dead_term_findings(grouped, glossary, stories))
    return findings


# Canonical Given/When/Then order, used both to test completeness and to
# report missing phases in reading order rather than alphabetically.
_PHASE_ORDER: tuple[Phase, ...] = ('given', 'when', 'then')

# A step tree reduced to nested phase tuples — narration text and values
# ignored. Two cases with equal signatures render truthfully in the merged
# parameter-table view.
type _StepSignature = tuple[tuple[Phase, _StepSignature], ...]


def _missing_phase_findings(grouped: list[Scenario]) -> list[Finding]:
    """Rule `missing-phase`: a passed scenario lacks a Given, When, or Then.

    Non-passed scenarios are skipped — a skipped one records no steps and a
    failed one may be missing a phase only because it aborted mid-body.
    """
    findings: list[Finding] = []
    for scenario in grouped:
        if scenario.status != 'passed':
            continue
        present = {step.phase for step in iter_steps(scenario.steps)}
        missing = [phase for phase in _PHASE_ORDER if phase not in present]
        if missing:
            findings.append(
                _scenario_finding(
                    RuleId('missing-phase'),
                    scenario,
                    f'missing: {", ".join(missing)}',
                )
            )
    return findings


def _divergent_case_findings(per_case: list[Scenario]) -> list[Finding]:
    """Rule `divergent-case-structure`: a parametrize case records a
    different step structure than case 1.

    Groups the pre-grouping cases by node-id base. Non-passed cases are
    exempt (skipped cases record no steps; failed cases abort mid-tree), so
    the baseline is the first passed case. One finding per scenario, naming
    the diverging case ids.
    """
    groups: dict[str, list[Scenario]] = {}
    for scenario in per_case:
        if '[' in scenario.id:
            groups.setdefault(node_base(scenario.id), []).append(scenario)
    findings: list[Finding] = []
    for base, cases in groups.items():
        passed = [case for case in cases if case.status == 'passed']
        if len(passed) < 2:
            continue
        baseline = _structure_signature(passed[0].steps)
        diverging = [
            case_suffix(case.id)
            for case in passed[1:]
            if _structure_signature(case.steps) != baseline
        ]
        if diverging:
            findings.append(
                Finding(
                    rule=RuleId('divergent-case-structure'),
                    severity=RULES_BY_ID[RuleId('divergent-case-structure')].default,
                    subject=base,
                    node_id=NodeId(base),
                    location=passed[0].source,
                    message=(
                        f'cases {", ".join(diverging)} record a different step '
                        f'structure than case {case_suffix(passed[0].id)}'
                    ),
                )
            )
    return findings


def _structure_signature(steps: list[Step]) -> _StepSignature:
    return tuple((step.phase, _structure_signature(step.children)) for step in steps)


def _tag_shadows_term_findings(
    grouped: list[Scenario], glossary: Glossary
) -> list[Finding]:
    """Rule `tag-shadows-term`: a scenario tag duplicates a glossary term.

    One finding per unique tag (subject = tag slug) — the fix is renaming the
    tag once, and per-scenario findings would be pure repetition.
    """
    counts: dict[TermId, tuple[str, NodeId, int]] = {}
    for scenario in grouped:
        for tag in scenario.tags:
            slug = id_derive(tag)
            if glossary.get(slug) is None:
                continue
            if slug in counts:
                first_tag, first_id, count = counts[slug]
                counts[slug] = (first_tag, first_id, count + 1)
            else:
                counts[slug] = (tag, scenario.id, 1)
    findings: list[Finding] = []
    for slug, (tag, node_id, count) in counts.items():
        term = glossary.get(slug)
        assert term is not None
        noun = 'scenario' if count == 1 else 'scenarios'
        findings.append(
            Finding(
                rule=RuleId('tag-shadows-term'),
                severity=RULES_BY_ID[RuleId('tag-shadows-term')].default,
                subject=slug,
                node_id=node_id,
                location=None,
                message=(
                    f'tag {tag!r} duplicates glossary term {term.canonical!r} '
                    f'({count} {noun}, e.g. {node_id})'
                ),
            )
        )
    return findings


def _dead_term_findings(
    grouped: list[Scenario], glossary: Glossary, stories: list[Story]
) -> list[Finding]:
    """Rule `dead-term`: a glossary term is referenced by no step and no
    story. Default `off`: for a file-backed glossary, unreferenced terms are
    often intentionally present (documented behaviour)."""
    referenced: set[TermId] = set()
    for scenario in grouped:
        for narration in _iter_narrations(scenario):
            for part in narration.parts:
                if isinstance(part, NarrationTermRef):
                    referenced.add(part.term_id)
    for story in stories:
        for activity in story.activities:
            for path in activity.paths:
                for ref in path.parts:
                    if isinstance(ref, ActivityTermRef):
                        referenced.add(ref.term_id)
    return [
        Finding(
            rule=RuleId('dead-term'),
            severity=RULES_BY_ID[RuleId('dead-term')].default,
            subject=term.id,
            node_id=None,
            location=term.source,
            message=f'term {term.canonical!r} is referenced by no step and no story',
        )
        for term in glossary.terms
        if term.id not in referenced
    ]


def _iter_narrations(scenario: Scenario) -> Iterator[Narration]:
    yield scenario.narration
    for step in iter_steps(scenario.steps):
        yield step.narration


def _scenario_finding(rule: RuleId, scenario: Scenario, text: str) -> Finding:
    location = scenario.source
    if location is not None:
        filename = PurePosixPath(location.relpath).name
        text = f'{text} ({filename}:{location.line})'
    return Finding(
        rule=rule,
        severity=RULES_BY_ID[rule].default,
        subject=scenario.id,
        node_id=scenario.id,
        location=location,
        message=text,
    )
