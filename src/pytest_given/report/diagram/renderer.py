"""The diagrams page: one self-contained HTML file for all of a run's stories."""

from dataclasses import dataclass

from ...markdown import definition_html
from ...model import ReportData
from ..html_assets import bundled_assets, bundled_script, script_json_parse
from ..html_renderer import base_env
from ..theme import DEFAULT_THEME, Theme
from .graph import build_graph
from .layout import DiagramLayout, layout_graph


@dataclass(frozen=True, kw_only=True)
class StoryView:
    layout: DiagramLayout
    max_step: int  # highest sentence number; 0 for an empty story
    sentence_count: int  # sentence ids may have gaps, so not max_step


def render_diagrams_html(report: ReportData, theme: Theme = DEFAULT_THEME) -> str:
    env = base_env()
    env.filters['label_lines'] = label_lines
    views = [
        StoryView(
            layout=(layout := layout_graph(build_graph(story, report.glossary))),
            max_step=max(
                (placed.edge.number or 0 for placed in layout.edges), default=0
            ),
            sentence_count=len(story.sentences),
        )
        for story in report.stories
    ]
    terms = report.glossary.terms if report.glossary is not None else []
    app_data = {
        'story_ids': [view.layout.graph.story_id for view in views],
        'max_steps': {view.layout.graph.story_id: view.max_step for view in views},
        'diagram_sizes': {
            view.layout.graph.story_id: [
                round(view.layout.width),
                round(view.layout.height),
            ]
            for view in views
        },
        # `definition_html` escapes the text and re-admits only inline markup,
        # which is what lets the tooltip assign it as innerHTML.
        'term_definitions': {
            term.id: definition_html(term.definition_text)
            for term in terms
            if term.definition_text
        },
    }
    title = report.metadata.title or report.metadata.project
    return env.get_template('diagrams.html.j2').render(
        title=title,
        views=views,
        theme_default=theme,
        param_colors=[],
        app_data_js=script_json_parse(app_data),
        diagrams_js=bundled_script('diagrams.js'),
        **bundled_assets('diagrams.css'),
    )


def label_lines(label: str, max_chars: int = 16) -> list[str]:
    """Split a long node label into at most two lines at the space nearest the
    midpoint. `max_chars` is coupled to layout.NODE_HALF_W: 16 chars at ~7px
    each fit inside the 124px node clearance box."""
    if len(label) <= max_chars or ' ' not in label:
        return [label]
    midpoint = len(label) // 2
    spaces = [index for index, char in enumerate(label) if char == ' ']
    split_at = min(spaces, key=lambda index: abs(index - midpoint))
    return [label[:split_at], label[split_at + 1 :]]
