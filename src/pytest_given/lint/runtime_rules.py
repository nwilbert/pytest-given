"""Runtime-surface rules: pure inspection of the recorded report model, no
source access needed."""

from collections.abc import Iterator
from dataclasses import dataclass

from ..model import (
    ActivityTermRef,
    Glossary,
    Narration,
    NarrationTermRef,
    NodeId,
    Phase,
    Scenario,
    SourceLocation,
    Story,
    TermId,
    id_derive,
    iter_steps,
    location_suffix,
)
from .base import RULES_BY_ID, Finding, RuleId


def run_runtime_rules(
    grouped: list[Scenario],
    glossary: Glossary | None,
    stories: list[Story],
) -> list[Finding]:
    """Run the runtime-surface rules over the recorded report model.

    Every rule here evaluates the grouped scenario list — one evaluation per
    logical scenario.
    """
    findings: list[Finding] = []
    findings.extend(_missing_phase_findings(grouped))
    if glossary is not None:
        findings.extend(_tag_shadows_term_findings(grouped, glossary))
        findings.extend(_dead_term_findings(grouped, glossary, stories))
    return findings


# Canonical Given/When/Then order, used both to test completeness and to
# report missing phases in reading order rather than alphabetically.
_PHASE_ORDER: tuple[Phase, ...] = ('given', 'when', 'then')


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


@dataclass
class _ShadowingTag:
    """A tag that collides with a glossary term, and where it was first seen.

    The example node id is the first scenario carrying the tag, so the message
    can point at one without listing them all.
    """

    tag: str
    example: NodeId
    scenarios: int = 1


def _tag_shadows_term_findings(
    grouped: list[Scenario], glossary: Glossary
) -> list[Finding]:
    """Rule `tag-shadows-term`: a scenario tag duplicates a glossary term.

    One finding per unique tag (subject = tag slug) — the fix is renaming the
    tag once, and per-scenario findings would be pure repetition.
    """
    shadowing: dict[TermId, _ShadowingTag] = {}
    for scenario in grouped:
        for tag in scenario.tags:
            slug = id_derive(tag)
            if glossary.get(slug) is None:
                continue
            seen = shadowing.get(slug)
            if seen is None:
                shadowing[slug] = _ShadowingTag(tag=tag, example=scenario.id)
            else:
                seen.scenarios += 1
    findings: list[Finding] = []
    for slug, shadow in shadowing.items():
        term = glossary.get(slug)
        assert term is not None
        noun = 'scenario' if shadow.scenarios == 1 else 'scenarios'
        findings.append(
            _finding(
                RuleId('tag-shadows-term'),
                subject=slug,
                node_id=shadow.example,
                location=None,
                message=(
                    f'tag {shadow.tag!r} duplicates glossary term '
                    f'{term.canonical!r} ({shadow.scenarios} {noun}, '
                    f'e.g. {shadow.example})'
                ),
            )
        )
    return findings


def _dead_term_findings(
    grouped: list[Scenario], glossary: Glossary, stories: list[Story]
) -> list[Finding]:
    """Rule `dead-term`: a glossary term is referenced by no step and no
    story. Default `off`: for a file-backed glossary, unreferenced terms are
    often intentionally present (documented behavior)."""
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
        _finding(
            RuleId('dead-term'),
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
    """A finding about a whole scenario, located and suffixed like a lint
    message anywhere else."""
    return _finding(
        rule,
        subject=scenario.id,
        node_id=scenario.id,
        location=scenario.source,
        message=f'{text}{location_suffix(scenario.source)}',
    )


def _finding(
    rule: RuleId,
    *,
    subject: str,
    node_id: NodeId | None,
    location: SourceLocation | None,
    message: str,
) -> Finding:
    """A finding at its rule's configured-default severity — the one place
    that reads `RULES_BY_ID`, so a rule cannot be reported at a level its
    catalog entry does not name."""
    return Finding(
        rule=rule,
        severity=RULES_BY_ID[rule].default,
        subject=subject,
        node_id=node_id,
        location=location,
        message=message,
    )
