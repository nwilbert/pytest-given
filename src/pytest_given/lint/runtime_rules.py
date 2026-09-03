"""Runtime-surface rules: pure inspection of the recorded report model, no
source access needed."""

from collections.abc import Container
from dataclasses import dataclass

from ..model import (
    ActivityTermRef,
    Glossary,
    NarrationTermRef,
    NodeId,
    Phase,
    Scenario,
    Story,
    TermId,
    id_derive,
    iter_narrations,
    iter_steps,
)
from .base import DEAD_TERM, MISSING_PHASE, TAG_SHADOWS_TERM, RawFinding, RuleId


def run_runtime_rules(
    grouped: list[Scenario],
    glossary: Glossary | None,
    stories: list[Story],
    enabled: Container[RuleId],
) -> list[RawFinding]:
    """Every `enabled` rule here evaluates the grouped scenario list — one
    evaluation per logical scenario.

    A rule that is off is not evaluated at all. `dead-term` ships off and
    walks every narration part of every scenario plus every activity path of
    every story, so computing its findings only to discard them was the bulk
    of the lint's cost on a default run.
    """
    findings: list[RawFinding] = []
    if MISSING_PHASE in enabled:
        findings.extend(_missing_phase_findings(grouped))
    if glossary is not None:
        if TAG_SHADOWS_TERM in enabled:
            findings.extend(_tag_shadows_term_findings(grouped, glossary))
        if DEAD_TERM in enabled:
            findings.extend(_dead_term_findings(grouped, glossary, stories))
    return findings


# Canonical Given/When/Then order, used both to test completeness and to
# report missing phases in reading order rather than alphabetically.
_PHASE_ORDER: tuple[Phase, ...] = ('given', 'when', 'then')


def _missing_phase_findings(grouped: list[Scenario]) -> list[RawFinding]:
    """Rule `missing-phase`: a passed scenario lacks a Given, When, or Then.

    Non-passed scenarios are skipped — a skipped one records no steps and a
    failed one may be missing a phase only because it aborted mid-body.
    """
    findings: list[RawFinding] = []
    for scenario in grouped:
        if scenario.status != 'passed':
            continue
        present = {step.phase for step in iter_steps(scenario.steps)}
        missing = [phase for phase in _PHASE_ORDER if phase not in present]
        if missing:
            findings.append(
                _scenario_finding(
                    MISSING_PHASE, scenario, f'missing: {", ".join(missing)}'
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
) -> list[RawFinding]:
    """Rule `tag-shadows-term`: a scenario tag duplicates a glossary term.

    One finding per unique tag (subject = tag slug) — the fix is renaming the
    tag once, and per-scenario findings would be pure repetition.
    """
    shadowing: dict[TermId, _ShadowingTag] = {}
    for scenario in grouped:
        for tag in scenario.tags:
            # Tags are stored as written, and `id_derive` raises on a name it
            # cannot slugify — which from here would escape as a bare
            # traceback. A tag with no derivable slug also cannot collide with
            # a term id, so there is nothing to check.
            if not _slugifiable(tag):
                continue
            slug = TermId(id_derive(tag))
            if glossary.get(slug) is None:
                continue
            seen = shadowing.get(slug)
            if seen is None:
                shadowing[slug] = _ShadowingTag(tag=tag, example=scenario.id)
            else:
                seen.scenarios += 1
    findings: list[RawFinding] = []
    for slug, shadow in shadowing.items():
        term = glossary.get(slug)
        assert term is not None
        noun = 'scenario' if shadow.scenarios == 1 else 'scenarios'
        findings.append(
            RawFinding(
                rule=TAG_SHADOWS_TERM,
                subject=slug,
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
) -> list[RawFinding]:
    """Rule `dead-term`: a glossary term is referenced by no step and no
    story. Default `off`: for a file-backed glossary, unreferenced terms are
    often intentionally present (documented behavior)."""
    referenced: set[TermId] = set()
    for scenario in grouped:
        for narration in iter_narrations(scenario):
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
        RawFinding(
            rule=DEAD_TERM,
            subject=term.id,
            location=term.source,
            message=f'term {term.canonical!r} is referenced by no step and no story',
        )
        for term in glossary.terms
        if term.id not in referenced
    ]


def _scenario_finding(rule: RuleId, scenario: Scenario, text: str) -> RawFinding:
    return RawFinding(
        rule=rule,
        subject=scenario.id,
        location=scenario.source,
        message=text,
    )


def _slugifiable(name: str) -> bool:
    """Whether `id_derive` will return a slug for `name` rather than raise."""
    return any(char.isascii() and char.isalnum() for char in name)
