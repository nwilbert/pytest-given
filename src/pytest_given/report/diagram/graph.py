"""Story -> DiagramGraph extraction (Domain Storytelling notation rules).

Actors dedupe story-wide by (term, display); work objects get one node per
sentence (deduped within a sentence via the id scheme); a clause's edge parts,
activity terms and bare connective words alike, become labeled edges, the
first of each clause carrying the sentence number.
"""

from dataclasses import dataclass
from typing import Literal

from ...model import (
    Clause,
    ClausePart,
    Glossary,
    NarrationLiteral,
    NarrationTermRef,
    Sentence,
    SentenceId,
    Story,
    StoryId,
    TermId,
)


@dataclass(frozen=True, kw_only=True)
class DiagramNode:
    id: str
    label: str
    sublabel: str | None  # canonical term name when an instance display differs
    glyph: Literal['actor', 'work']
    term_id: TermId | None  # None for bare-word nodes
    # A work object's sentence, which draws it; None for an actor, drawn once.
    sentence_id: SentenceId | None


@dataclass(frozen=True, kw_only=True)
class DiagramEdge:
    source: str  # DiagramNode.id
    target: str
    label: str
    sentence_id: SentenceId
    number: int | None  # sequence badge: set on each clause's first edge
    term_id: TermId | None = None  # the activity term (None for connectives)


@dataclass(frozen=True, kw_only=True)
class DiagramGraph:
    story_id: StoryId
    title: str
    nodes: tuple[DiagramNode, ...]
    edges: tuple[DiagramEdge, ...]


def build_graph(story: Story, glossary: Glossary | None) -> DiagramGraph:
    nodes: dict[str, DiagramNode] = {}
    edges: list[DiagramEdge] = []
    for sentence in story.sentences:
        for clause in sentence.clauses:
            position_to_id = _register_clause_nodes(clause, sentence, glossary, nodes)
            for position in range(1, len(clause.parts), 2):
                part = clause.parts[position]
                edges.append(
                    DiagramEdge(
                        source=position_to_id[position - 1],
                        target=position_to_id[position + 1],
                        label=_display(part),
                        sentence_id=sentence.id,
                        number=int(sentence.id) if position == 1 else None,
                        term_id=(
                            part.term_id if isinstance(part, NarrationTermRef) else None
                        ),
                    )
                )
    return DiagramGraph(
        story_id=story.id,
        title=story.title,
        nodes=tuple(nodes.values()),
        edges=tuple(edges),
    )


def _register_clause_nodes(
    clause: Clause,
    sentence: Sentence,
    glossary: Glossary | None,
    nodes: dict[str, DiagramNode],
) -> dict[int, str]:
    """Register the node parts (even positions) of one clause; returns
    position -> node id. Dedupe falls out of the id scheme: actor ids are
    story-wide, work ids embed the sentence id."""
    position_to_id: dict[int, str] = {}
    for position in range(0, len(clause.parts), 2):
        node = _node_for(clause.parts[position], position, sentence, glossary)
        nodes.setdefault(node.id, node)
        position_to_id[position] = node.id
    return position_to_id


def _node_for(
    part: ClausePart,
    position: int,
    sentence: Sentence,
    glossary: Glossary | None,
) -> DiagramNode:
    is_actor = _is_actor(part, position, glossary)
    if isinstance(part, NarrationTermRef):
        term = glossary.get(part.term_id) if glossary is not None else None
        sublabel = (
            term.canonical
            if term is not None and term.canonical != part.display
            else None
        )
        term_id: TermId | None = part.term_id
        key = f'{part.term_id}:{part.display}'
    else:
        term_id = None
        sublabel = None
        key = f'word:{part.value}'
    node_id = f'actor:{key}' if is_actor else f'work:{sentence.id}:{key}'
    return DiagramNode(
        id=node_id,
        label=_display(part),
        sublabel=sublabel,
        glyph='actor' if is_actor else 'work',
        term_id=term_id,
        sentence_id=None if is_actor else sentence.id,
    )


def _is_actor(part: ClausePart, position: int, glossary: Glossary | None) -> bool:
    """Kind-known terms follow their glossary kind anywhere; kind-unknown
    parts count as actors only at position 0 (the clause's actor slot)."""
    if isinstance(part, NarrationTermRef) and glossary is not None:
        term = glossary.get(part.term_id)
        if term is not None and term.kind is not None:
            return term.kind == 'actor'
    return position == 0


def _display(part: ClausePart) -> str:
    match part:
        case NarrationTermRef(display=display):
            return display
        case NarrationLiteral(value=text):
            return text
