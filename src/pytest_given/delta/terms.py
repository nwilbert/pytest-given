"""Pairing two glossaries' terms, and the facts each side lists them with."""

from collections.abc import Callable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from ..model import (
    DiffSegment,
    Glossary,
    GlossaryDelta,
    GlossaryTerm,
    IdentityPair,
    Narration,
    ReportData,
    TermDelta,
    TermFacts,
    TermId,
    build_term_crossrefs,
)
from .chains import rewrite_identities
from .narration import Reading, word_diff
from .order import interleaved
from .renames import RenameLog


@dataclass(frozen=True)
class TermAlignment:
    delta: GlossaryDelta
    term_id: Callable[[TermId], TermId]  # before → after, for every ref, any kind
    warnings: tuple[str, ...]


def align_terms(
    before: ReportData,
    after: ReportData,
    log: RenameLog,
    skipped_revs: AbstractSet[str],
) -> TermAlignment:
    before_terms = before.glossary.terms if before.glossary else []
    after_terms = after.glossary.terms if after.glossary else []
    rewrites = rewrite_identities(
        [term.id for term in before_terms],
        {term.id for term in after_terms},
        log.of('term'),
        skipped_revs,
    )

    def rewritten(term_id: TermId) -> TermId:
        rewrite = rewrites.by_identity.get(term_id)
        return TermId(rewrite.identity) if rewrite else term_id

    paired: dict[TermId, TermId] = {}
    for term in before_terms:
        partner = after.glossary.get(rewritten(term.id)) if after.glossary else None
        if partner is not None and partner.kind == term.kind:
            paired[term.id] = partner.id

    before_facts = term_facts(before)
    after_facts = term_facts(after)
    # A definition has no placeholders, so the column key is never asked for.
    before_reading = Reading(
        before.glossary, rewritten, lambda placeholder: placeholder.name
    )
    after_reading = Reading(
        after.glossary, lambda term_id: term_id, lambda placeholder: placeholder.name
    )
    before_by_id = {term.id: term for term in before_terms}
    after_by_id = {term.id: term for term in after_terms}

    deltas: list[TermDelta] = []
    unchanged: list[IdentityPair] = []
    rows = interleaved(
        [term.id for term in after_terms], [term.id for term in before_terms], paired
    )
    for before_id, after_id in rows:
        before_term = before_by_id[before_id] if before_id is not None else None
        after_term = after_by_id[after_id] if after_id is not None else None
        if before_term is None and after_term is not None:
            deltas.append(
                TermDelta(
                    change='added',
                    after=after_term,
                    after_facts=after_facts[after_term.id],
                )
            )
        elif after_term is None and before_term is not None:
            deltas.append(
                TermDelta(
                    change='removed',
                    before=before_term,
                    before_facts=before_facts[before_term.id],
                )
            )
        elif before_term is not None and after_term is not None:
            if _same_term(before_term, after_term):
                unchanged.append(
                    IdentityPair(before=before_term.id, after=after_term.id)
                )
                continue
            deltas.append(
                TermDelta(
                    change='changed',
                    before=before_term,
                    after=after_term,
                    paired_by='rename-log'
                    if before_term.id in rewrites.by_identity
                    else 'term-id',
                    before_facts=before_facts[before_term.id],
                    after_facts=after_facts[after_term.id],
                    definition=_definition_diff(
                        before_term, after_term, before_reading, after_reading
                    ),
                )
            )
    return TermAlignment(
        delta=GlossaryDelta(
            before=before.glossary,
            after=after.glossary,
            terms=tuple(deltas),
            unchanged=tuple(unchanged),
        ),
        term_id=rewritten,
        warnings=rewrites.warnings,
    )


def term_facts(report: ReportData) -> dict[TermId, TermFacts]:
    """Computed from the whole report, whichever scenarios the delta lists."""
    glossary: Glossary | None = report.glossary
    if glossary is None:
        return {}
    crossrefs = build_term_crossrefs(report)
    facts: dict[TermId, TermFacts] = {}
    for term in glossary.terms:
        aggregation = crossrefs.aggregations.get(term.id)
        forms = (
            [instance.display for instance in aggregation.instances]
            + [str(form) for form in aggregation.forms]
            if aggregation
            else []
        )
        facts[term.id] = TermFacts(
            other_forms=tuple(dict.fromkeys(forms)),
            scenario_count=len(crossrefs.term_scenarios.get(term.id, [])),
        )
    return facts


def _same_term(before: GlossaryTerm, after: GlossaryTerm) -> bool:
    return (before.canonical, before.definition) == (after.canonical, after.definition)


def _definition_diff(
    before: GlossaryTerm,
    after: GlossaryTerm,
    before_reading: Reading,
    after_reading: Reading,
) -> tuple[DiffSegment, ...]:
    if before.definition == after.definition:
        return ()
    return word_diff(
        Narration(text=before.definition or ''),
        before_reading,
        Narration(text=after.definition or ''),
        after_reading,
    )
