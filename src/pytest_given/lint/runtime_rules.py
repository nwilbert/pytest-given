"""Runtime-surface rules: pure inspection of the recorded report model, no
source access needed."""

import re
from collections.abc import Callable, Container, Iterator
from dataclasses import dataclass, field

from ..markdown import unwrapped_text
from ..model import (
    PHASES,
    ClauseTermRef,
    ClauseWord,
    Definition,
    Glossary,
    GlossaryTerm,
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    Scenario,
    SourceLocation,
    Story,
    TermId,
    avoided_word,
    boolean_phrases,
    definition_ref_text,
    derived_id,
    iter_narrations,
    iter_steps,
    name_key,
    name_keys,
    read_definition,
)
from .catalog import (
    AVOIDED_WORD,
    DEAD_TERM,
    MISSING_PHASE,
    TAG_SHADOWS_TERM,
    UNRESOLVED_DEFINITION_REF,
    RawLintFinding,
    RuleId,
)


def run_runtime_rules(
    grouped: list[Scenario],
    glossary: Glossary | None,
    stories: list[Story],
    enabled: Container[RuleId],
) -> list[RawLintFinding]:
    """Every `enabled` rule here, evaluated over the grouped scenario list —
    once per logical scenario."""
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
    glossary at all, which the term rules treat as nothing to say."""

    grouped: list[Scenario]
    glossary: Glossary | None
    stories: list[Story]


def _missing_phase_findings(context: _Context) -> list[RawLintFinding]:
    """Rule `missing-phase`: a passed scenario lacks a Given, When, or Then.

    Non-passed scenarios are skipped — a skipped one records no steps and a
    failed one may be missing a phase only because it aborted mid-body.
    """
    findings: list[RawLintFinding] = []
    for scenario in context.grouped:
        if scenario.status != 'passed':
            continue
        present = {step.phase for step in iter_steps(scenario.steps)}
        missing = [phase for phase in PHASES if phase not in present]
        if missing:
            findings.append(
                RawLintFinding(
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

    The example node ID is the first scenario carrying the tag, so the message
    can point at one without listing them all.
    """

    tag: str
    term: GlossaryTerm
    example: NodeId
    # A set, so a scenario carrying two spellings of the tag counts once.
    scenarios: set[NodeId] = field(default_factory=set)


def _tag_shadows_term_findings(context: _Context) -> list[RawLintFinding]:
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
            term = glossary.get(slug)
            if term is None:
                continue
            shadow = shadowing.get(slug)
            if shadow is None:
                shadow = shadowing[slug] = _ShadowingTag(
                    tag=tag, term=term, example=scenario.id
                )
            shadow.scenarios.add(scenario.id)
    findings: list[RawLintFinding] = []
    for slug, shadow in shadowing.items():
        count = len(shadow.scenarios)
        noun = 'scenario' if count == 1 else 'scenarios'
        findings.append(
            RawLintFinding(
                rule=TAG_SHADOWS_TERM,
                subject=slug,
                location=None,
                message=(
                    f'tag {shadow.tag!r} duplicates glossary term '
                    f'{shadow.term.canonical!r} ({count} {noun}, '
                    f'e.g. {shadow.example})'
                ),
            )
        )
    return findings


def _dead_term_findings(context: _Context) -> list[RawLintFinding]:
    """Rule `dead-term`: a glossary term is referenced by no scenario title, no
    step and no story. Default `off`: for a file-backed glossary, unreferenced
    terms are often intentionally present (documented behavior)."""
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
        for sentence in story.sentences:
            for clause in sentence.clauses:
                for ref in clause.parts:
                    if isinstance(ref, ClauseTermRef):
                        referenced.add(ref.term_id)
    return [
        RawLintFinding(
            rule=DEAD_TERM,
            subject=term.id,
            location=term.source,
            message=(
                f'term {term.canonical!r} is referenced by no scenario title, '
                f'no step and no story sentence'
            ),
        )
        for term in glossary.terms
        if term.id not in referenced
    ]


def _unresolved_definition_ref_findings(context: _Context) -> list[RawLintFinding]:
    """Rule `unresolved-definition-ref`: a bold span in a glossary definition
    names no term — a definition ref left stale by a rename, or bold used for
    emphasis. One finding per term and bold text."""
    if context.glossary is None:
        return []
    return [
        RawLintFinding(
            rule=UNRESOLVED_DEFINITION_REF,
            subject=term.id,
            location=term.source,
            message=(
                f'definition of {term.canonical!r} bolds {text!r}, '
                f'which names no glossary term'
            ),
        )
        for term in context.glossary.terms
        for text in dict.fromkeys(_unresolved_bold_spans(term.definition))
    ]


def _unresolved_bold_spans(definition: Definition | None) -> Iterator[str]:
    """The text of each bold span the resolution left in a literal part."""
    if definition is None:
        return
    for piece in read_definition(definition):
        if isinstance(piece, NarrationTermRef):
            continue
        text = definition_ref_text(piece)
        if text is not None:
            yield text


@dataclass(frozen=True)
class _AvoidedWord:
    spelling: str
    pattern: re.Pattern[str]
    preferred: tuple[str, ...]


@dataclass(frozen=True)
class _Text:
    """Plain text one rule reads, and where a finding about it points."""

    kind: str
    location: SourceLocation | None
    text: str


def _avoided_word_findings(context: _Context) -> list[RawLintFinding]:
    """Rule `avoided-word`: narration uses a word a term lists in its `avoid`.
    One finding per scenario or story and word, for its first use."""
    if context.glossary is None:
        return []
    words = _avoided_words(context.glossary)
    if not words:
        return []
    subjects = [
        (scenario.id, list(_scenario_texts(scenario))) for scenario in context.grouped
    ] + [(story.id, list(_story_texts(story))) for story in context.stories]
    findings = (
        _avoided_word_finding(word, texts, subject)
        for subject, texts in subjects
        for word in words
    )
    return [finding for finding in findings if finding is not None]


def _avoided_word_finding(
    word: _AvoidedWord,
    texts: list[_Text],
    subject: str,
) -> RawLintFinding | None:
    for text in texts:
        if word.pattern.search(text.text):
            preferred = ' or '.join(repr(name) for name in word.preferred)
            return RawLintFinding(
                rule=AVOIDED_WORD,
                subject=subject,
                location=text.location,
                message=(
                    f'{text.kind} uses {word.spelling!r}, which the glossary '
                    f'avoids in favour of {preferred}'
                ),
            )
    return None


def _avoided_words(glossary: Glossary) -> list[_AvoidedWord]:
    """Each distinct avoided word once, with the terms that avoid it in
    glossary order."""
    spellings: dict[str, str] = {}
    preferred: dict[str, list[str]] = {}
    for term in glossary.terms:
        for entry in term.avoid:
            spelling = avoided_word(entry)
            key = name_key(spelling)
            spellings.setdefault(key, spelling)
            names = preferred.setdefault(key, [])
            if term.canonical not in names:
                names.append(term.canonical)
    return [
        _AvoidedWord(
            spelling=spelling,
            pattern=_word_pattern(spelling),
            preferred=tuple(preferred[key]),
        )
        for key, spelling in spellings.items()
    ]


def _word_pattern(spelling: str) -> re.Pattern[str]:
    """Each spelling `name_keys` counts, as a whole word in any case."""
    spellings = '|'.join(_spaced(key) for key in sorted(name_keys(spelling)))
    return re.compile(rf'(?<!\w)(?:{spellings})(?!\w)', re.IGNORECASE)


def _spaced(key: str) -> str:
    # A `name_key` joins words by one space for any run of whitespace and hyphens.
    return _SEPARATOR.join(re.escape(word) for word in key.split(' '))


_SEPARATOR = r'[\s-]+'


def _scenario_texts(scenario: Scenario) -> Iterator[_Text]:
    yield from _narration_texts('scenario title', scenario.source, scenario.narration)
    for step in iter_steps(scenario.steps):
        yield from _narration_texts('step text', step.source, step.narration)


def _narration_texts(
    kind: str, location: SourceLocation | None, narration: Narration
) -> Iterator[_Text]:
    if not narration.parts:
        yield _Text(kind, location, unwrapped_text(narration.text, code=False))
        return
    for part in narration.parts:
        if isinstance(part, NarrationLiteral):
            yield _Text(kind, location, unwrapped_text(part.value, code=False))
        elif isinstance(part, NarrationValue | NarrationPlaceholder):
            # Both phrases are the author's prose, whichever one a row shows.
            for phrase in boolean_phrases(part.format_spec) or ():
                yield _Text(kind, location, phrase)


def _story_texts(story: Story) -> Iterator[_Text]:
    for sentence in story.sentences:
        for clause in sentence.clauses:
            words: list[str] = []
            for part in (*clause.parts, None):
                if isinstance(part, ClauseWord):
                    words.append(part.text)
                elif words:
                    yield _Text('story sentence', story.source, ' '.join(words))
                    words = []


# Keyed by rule id so `run_runtime_rules` skips a disabled rule entirely —
# `dead-term`, off by default, walks every narration part and every clause.
_RUNTIME_RULES: dict[RuleId, Callable[[_Context], list[RawLintFinding]]] = {
    MISSING_PHASE: _missing_phase_findings,
    TAG_SHADOWS_TERM: _tag_shadows_term_findings,
    DEAD_TERM: _dead_term_findings,
    UNRESOLVED_DEFINITION_REF: _unresolved_definition_ref_findings,
    AVOIDED_WORD: _avoided_word_findings,
}

RUNTIME_RULE_IDS = frozenset(_RUNTIME_RULES)
