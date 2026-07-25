"""Story -> DiagramGraph extraction (Domain Storytelling notation rules).

Actors dedupe story-wide by (term, display); work objects get one node per
activity (deduped within an activity via the id scheme); verbs become labeled
edges carrying the activity number on each path's first edge; bare-string
connectives become unnumbered muted edges.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...model import (
    Activity,
    ActivityId,
    ActivityPart,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Glossary,
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


@dataclass(frozen=True, kw_only=True)
class DiagramEdge:
    source: str  # DiagramNode.id
    target: str
    label: str
    activity_id: ActivityId
    number: int | None  # sequence badge: set on each path's first edge
    connective: bool  # True when the part was a bare-string ActivityWord
    term_id: TermId | None = None  # the verb's glossary term (None for connectives)


@dataclass(frozen=True, kw_only=True)
class DiagramGraph:
    story_id: StoryId
    title: str
    nodes: tuple[DiagramNode, ...]
    edges: tuple[DiagramEdge, ...]


def build_graph(story: Story, glossary: Glossary | None) -> DiagramGraph:
    nodes: dict[str, DiagramNode] = {}
    edges: list[DiagramEdge] = []
    for activity in story.activities:
        for activity_path in activity.paths:
            position_to_id = _register_path_nodes(
                activity_path, activity, glossary, nodes
            )
            for position in range(1, len(activity_path.parts), 2):
                part = activity_path.parts[position]
                edges.append(
                    DiagramEdge(
                        source=position_to_id[position - 1],
                        target=position_to_id[position + 1],
                        label=_display(part),
                        activity_id=activity.id,
                        number=int(activity.id) if position == 1 else None,
                        connective=isinstance(part, ActivityWord),
                        term_id=(
                            part.term_id
                            if isinstance(part, ActivityTermRef)
                            else None
                        ),
                    )
                )
    return DiagramGraph(
        story_id=story.id,
        title=story.title,
        nodes=tuple(nodes.values()),
        edges=tuple(edges),
    )


def _register_path_nodes(
    activity_path: ActivityPath,
    activity: Activity,
    glossary: Glossary | None,
    nodes: dict[str, DiagramNode],
) -> dict[int, str]:
    """Register the node parts (even positions) of one path; returns
    position -> node id. Dedupe falls out of the id scheme: actor ids are
    story-wide, work ids embed the activity id."""
    position_to_id: dict[int, str] = {}
    for position in range(0, len(activity_path.parts), 2):
        node = _node_for(activity_path.parts[position], position, activity, glossary)
        nodes.setdefault(node.id, node)
        position_to_id[position] = node.id
    return position_to_id


def _node_for(
    part: ActivityPart,
    position: int,
    activity: Activity,
    glossary: Glossary | None,
) -> DiagramNode:
    is_actor = _is_actor(part, position, glossary)
    if isinstance(part, ActivityTermRef):
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
        key = f'word:{part.text}'
    node_id = f'actor:{key}' if is_actor else f'work:{activity.id}:{key}'
    return DiagramNode(
        id=node_id,
        label=_display(part),
        sublabel=sublabel,
        glyph='actor' if is_actor else 'work',
        term_id=term_id,
    )


def _is_actor(part: ActivityPart, position: int, glossary: Glossary | None) -> bool:
    """Kind-known terms follow their glossary kind anywhere; kind-unknown
    parts count as actors only at position 0 (the path's actor slot)."""
    if isinstance(part, ActivityTermRef) and glossary is not None:
        term = glossary.get(part.term_id)
        if term is not None and term.kind is not None:
            return term.kind == 'actor'
    return position == 0


def _display(part: ActivityPart) -> str:
    match part:
        case ActivityTermRef(display=display):
            return display
        case ActivityWord(text=text):
            return text
