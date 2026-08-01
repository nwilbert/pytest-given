"""Export a laid-out story to the egon.io (.egn) Domain Story Modeler format.

The point of this exporter is a round-trip: emit our computed layout as a valid
egon.io document, let a human open it at https://egon.io/, drag the nodes into a
tidy arrangement, and save the result back as a reference for tuning our own
layout heuristic. So the geometry we write is our layout's -- node centres and
trimmed edge endpoints -- not an egon auto-layout.

Format (egon.io v2.0.1): a top-level object with a `domain` icon dictionary and
a `dst` array of elements. Each actor/work-object is a shape
(`domainStory:actorPerson` / `domainStory:workObjectDocument`) with a top-left
`x`/`y`; each verb/connective is a `domainStory:activity` connection carrying the
sequence `number` (or null) and `waypoints`. The array ends with an `{"info":
""}` blob and a `{"version": "2.0.1"}` stamp. Our diagrams have a single actor
glyph and a single work-object glyph, so every node maps to the Person or the
Document icon; a modeller can swap icons in egon afterwards.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from ...model import ReportData
from .graph import build_graph
from .layout import DiagramLayout, PlacedEdge, PlacedNode, layout_graph

# The two built-in egon.io icons we target, copied verbatim from egon's default
# icon dictionary so the emitted file is self-contained.
PERSON_SVG = (
    '<svg viewBox="0 0 24 26" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 5.9c1.16 0 2.1.94 2.1 2.1s-.94 2.1-2.1 2.1S9.9 9.16 9.9 8s.94-2.1 '
    '2.1-2.1m0 9c2.97 0 6.1 1.46 6.1 2.1v1.1H5.9V17c0-.64 3.13-2.1 6.1-2.1M12 4C9.79 '
    '4 8 5.79 8 8s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm0 9c-2.67 0-8 1.34-8 4v3h16v-3c0'
    '-2.66-5.33-4-8-4z"/><path d="M0 0h24v24H0z" fill="none"/></svg>'
)
DOCUMENT_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
    'viewBox="0 0 24 26"><path fill="none" d="M0 0h24v24H0V0z"/><path d="M8 16h8v2H8'
    'zm0-4h8v2H8zm6-10H6c-1.1 0-2 .9-2 2v16c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6'
    '-6zm4 18H6V4h7v5h5v11z"/></svg>'
)

# egon shapes store a top-left corner and no size; it applies a default box. We
# offset our node centres by half that box so the icon sits where we placed it.
_ICON_HALF = 38


def render_egn(report: ReportData, output_dir: Path) -> list[Path]:
    """Write one `.egn` file per story into `output_dir` (named by story id, the
    same slug the report uses for anchors) and return the paths written. Stories
    with no activities still emit a valid empty document."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for story in report.stories:
        layout = layout_graph(build_graph(story, report.glossary))
        path = output_dir / f'{story.id}.egn'
        path.write_text(egn_to_json(layout_to_egn(layout)), encoding='utf-8')
        written.append(path)
    return written


def layout_to_egn(layout: DiagramLayout) -> dict[str, Any]:
    """Convert a laid-out story into an egon.io v2.0.1 document (a dict ready for
    `egn_to_json`)."""
    shape_id_by_node = {
        placed.node.id: f'shape_{index:04d}'
        for index, placed in enumerate(layout.nodes, start=1)
    }
    number_counts = Counter(
        edge.edge.number for edge in layout.edges if edge.edge.number is not None
    )

    dst: list[dict[str, Any]] = [
        _shape(placed, shape_id_by_node[placed.node.id]) for placed in layout.nodes
    ]
    dst.extend(
        _activity(
            edge,
            f'connection_{index:04d}',
            shape_id_by_node,
            shared_number=edge.edge.number is not None
            and number_counts[edge.edge.number] > 1,
        )
        for index, edge in enumerate(layout.edges, start=1)
    )
    dst.append({'info': ''})
    dst.append({'version': '2.0.1'})

    return {
        'domain': {
            'name': 'default',
            'actors': {'Person': PERSON_SVG},
            'workObjects': {'Document': DOCUMENT_SVG},
        },
        'dst': dst,
    }


def egn_to_json(egn: dict[str, Any]) -> str:
    """Serialise an egon document to the pretty-printed JSON egon.io writes."""
    return json.dumps(egn, indent=2, ensure_ascii=False)


def _shape(placed: PlacedNode, shape_id: str) -> dict[str, Any]:
    is_actor = placed.node.glyph == 'actor'
    return {
        'type': 'domainStory:actorPerson'
        if is_actor
        else 'domainStory:workObjectDocument',
        'name': placed.node.label,
        'id': shape_id,
        'pickedColor': 'black',
        'x': round(placed.x) - _ICON_HALF,
        'y': round(placed.y) - _ICON_HALF,
        '$type': 'Element',
        'di': {},
        '$descriptor': {},
    }


def _activity(
    placed: PlacedEdge,
    connection_id: str,
    shape_id_by_node: dict[str, str],
    shared_number: bool,
) -> dict[str, Any]:
    edge = placed.edge
    activity: dict[str, Any] = {
        'type': 'domainStory:activity',
        'name': edge.label,
        'id': connection_id,
        'pickedColor': 'black',
        'number': edge.number,
        'waypoints': [
            _waypoint(placed.x1, placed.y1),
            _waypoint(placed.x2, placed.y2),
        ],
        'source': shape_id_by_node[edge.source],
        'target': shape_id_by_node[edge.target],
        '$type': 'Element',
        'di': {},
        '$descriptor': {},
    }
    if edge.number is not None:
        activity['multipleNumberAllowed'] = shared_number
    return activity


def _waypoint(x: float, y: float) -> dict[str, Any]:
    point = {'x': round(x), 'y': round(y)}
    return {'original': dict(point), **point}
