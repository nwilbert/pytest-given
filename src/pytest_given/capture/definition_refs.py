"""Session-finish resolution of the definition refs in a glossary's definitions.

Late because a glossary declared in code is complete only then: a definition
may reference a term declared after it, in the same module or in another."""

from dataclasses import replace

from ..markdown import InlineSpan, located_spans
from ..model import (
    Definition,
    DefinitionPart,
    Glossary,
    GlossaryTerm,
    NarrationLiteral,
    NarrationTermRef,
    definition_ref_text,
)


def resolve_definition_refs(glossary: Glossary) -> Glossary:
    return Glossary(terms=[_resolved(term, glossary) for term in glossary.terms])


def _resolved(term: GlossaryTerm, glossary: Glossary) -> GlossaryTerm:
    if term.definition is None:
        return term
    return replace(
        term, definition=_resolved_definition(term.definition.text, glossary)
    )


def _resolved_definition(text: str, glossary: Glossary) -> Definition:
    parts: list[DefinitionPart] = []
    end = 0
    for span, covered in located_spans(text):
        ref = _definition_ref(span, glossary)
        if ref is None:
            continue
        if end < covered.start:
            parts.append(NarrationLiteral(value=text[end : covered.start]))
        parts.append(ref)
        end = covered.stop
    if end < len(text):
        parts.append(NarrationLiteral(value=text[end:]))
    return Definition(text, tuple(parts))


def _definition_ref(span: InlineSpan, glossary: Glossary) -> NarrationTermRef | None:
    ref_text = definition_ref_text(span)
    if ref_text is None:
        return None
    target = glossary.resolve_ref(ref_text)
    if target is None:
        return None
    return NarrationTermRef(term_id=target.id, display=ref_text)
