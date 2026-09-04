"""Runtime-surface rules: pure inspection of the recorded report model, no
source access needed."""

from collections.abc import Callable, Container
from dataclasses import dataclass

from ..model import (
    PHASES,
    ActivityTermRef,
    Glossary,
    NarrationTermRef,
    NodeId,
    Scenario,
    Story,
    TermId,
    derived_id,
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
    context = _Context(grouped=grouped, glossary=glossary, stories=stories)
    return [
        finding
        for rule, run in _RUNTIME_RULES.items()
        if rule in enabled
        for finding in run(context)
    ]


@dataclass(frozen=True)
class _Context:
    """What every runtime rule reads. `glossary` is None when the run has no
    glossary at all, which the two term rules treat as nothing to say."""

    grouped: list[Scenario]
    glossary: Glossary | None
    stories: list[Story]


def _missing_phase_findings(context: _Context) -> list[RawFinding]:
    """Rule `missing-phase`: a passed scenario lacks a Given, When, or Then.

    Non-passed scenarios are skipped — a skipped one records no steps and a
    failed one may be missing a phase only because it aborted mid-body.
    """
    findings: list[RawFinding] = []
    for scenario in context.grouped:
        if scenario.status != 'passed':
            continue
        present = {step.phase for step in iter_steps(scenario.steps)}
        missing = [phase for phase in PHASES if phase not in present]
        if missing:
            findings.append(
                RawFinding(
                    rule=MISSING_PHASE,
                    subject=scenario.id,
                    location=scenario.source,
                    message=f'missing: {", ".join(missing)}',
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


def _tag_shadows_term_findings(context: _Context) -> list[RawFinding]:
    """Rule `tag-shadows-term`: a scenario tag duplicates a glossary term.

    One finding per unique tag (subject = tag slug) — the fix is renaming the
    tag once, and per-scenario findings would be pure repetition.
    """
    if context.glossary is None:
        return []
    grouped, glossary = context.grouped, context.glossary
    shadowing: dict[TermId, _ShadowingTag] = {}
    for scenario in grouped:
        for tag in scenario.tags:
            # A tag with no derivable slug cannot collide with a term id.
            derived = derived_id(tag)
            if derived is None:
                continue
            slug = TermId(derived)
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


def _dead_term_findings(context: _Context) -> list[RawFinding]:
    """Rule `dead-term`: a glossary term is referenced by no step and no
    story. Default `off`: for a file-backed glossary, unreferenced terms are
    often intentionally present (documented behavior)."""
    if context.glossary is None:
        return []
    grouped, glossary, stories = context.grouped, context.glossary, context.stories
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


# Keyed by rule id so `run_runtime_rules` can skip a disabled rule without
# evaluating it — `dead-term` walks every narration part and every activity
# path, which was the bulk of the lint's cost on a default run.
_RUNTIME_RULES: dict[RuleId, Callable[[_Context], list[RawFinding]]] = {
    MISSING_PHASE: _missing_phase_findings,
    TAG_SHADOWS_TERM: _tag_shadows_term_findings,
    DEAD_TERM: _dead_term_findings,
}

RUNTIME_RULE_IDS = frozenset(_RUNTIME_RULES)
