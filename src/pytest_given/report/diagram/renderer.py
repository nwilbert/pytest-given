"""Diagrams HTML artifact: one self-contained page for all of a run's stories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import jinja2
from markupsafe import Markup

from ...model import ReportData
from ..embed import script_json
from .graph import build_graph
from .layout import DiagramLayout, layout_graph


@dataclass(frozen=True, kw_only=True)
class StoryView:
    """Per-story template data: the layout plus replay bounds."""

    layout: DiagramLayout
    max_step: int  # highest activity number; 0 for an empty story


def render_diagrams(report: ReportData, output_path: Path) -> None:
    templates_dir = Path(__file__).parent.parent / 'templates'
    css = (templates_dir / 'diagrams.css').read_text(encoding='utf-8')
    alpine_js = (templates_dir / 'alpine.min.js').read_text(encoding='utf-8')
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)), autoescape=True
    )
    env.filters['label_lines'] = _label_lines
    views: list[StoryView] = []
    for story in report.stories:
        layout = layout_graph(build_graph(story, report.glossary))
        max_step = max((placed.edge.number or 0 for placed in layout.edges), default=0)
        views.append(StoryView(layout=layout, max_step=max_step))
    term_info: dict[str, dict[str, str | None]] = {}
    if report.glossary is not None:
        term_info = {
            term.id: {'kind': term.kind, 'definition': term.definition}
            for term in report.glossary.terms
        }
    template = env.get_template('diagrams.html.j2')
    html = template.render(
        metadata=report.metadata,
        views=views,
        story_ids_json=script_json([v.layout.graph.story_id for v in views]),
        max_steps_json=script_json(
            {v.layout.graph.story_id: v.max_step for v in views}
        ),
        term_info_json=script_json(term_info),
        css=Markup(css),
        alpine_js=Markup(alpine_js),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')


def _label_lines(label: str, max_chars: int = 16) -> list[str]:
    """Split a long node label into at most two lines at the space nearest
    the midpoint (spec: long labels wrap to two lines under the icon).
    `max_chars` is coupled to layout.NODE_HALF_W — one line of 16 chars at
    ~7px/char fits inside the 124px node clearance box."""
    if len(label) <= max_chars or ' ' not in label:
        return [label]
    midpoint = len(label) // 2
    spaces = [index for index, char in enumerate(label) if char == ' ']
    split_at = min(spaces, key=lambda index: abs(index - midpoint))
    return [label[:split_at], label[split_at + 1 :]]
