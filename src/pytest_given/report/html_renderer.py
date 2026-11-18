"""Rendering the HTML report page: the Jinja environment, and the context its
templates read.

Everything the page displays is rendered into the markup; the one JSON blob
beside it is what `app.js` seeds its state from.
"""

# A pytest session or CLI command that renders no HTML never loads Jinja.
__lazy_modules__ = ['jinja2']

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import jinja2

from ..model import AttachmentRef, Glossary, ReportData, case_id, plural
from .app_data import app_data, citation_data
from .citation_index import CitationIndex
from .coverage import build_coverage_map
from .glossary_view import build_glossary_view
from .glyphs import STATUS_GLYPH, STATUS_LABEL
from .html_assets import TEMPLATES_DIR, bundled_assets, data_url, script_json_parse
from .html_narration import (
    avoid_html,
    inline_md,
    make_clause_part_filter,
    make_definition_filter,
    make_narration_filter,
    make_source_url_filter,
)
from .palette import param_column_colors
from .slugs import build_scenario_slug_index
from .step_layout import (
    ParamColorMap,
    build_param_color_map,
    column_phase_blocks,
    make_param_color_class,
    phase_blocks,
    repr_columns,
    value_cell,
)
from .story_view import (
    build_scenario_sentence_index,
    build_sentence_labels,
    build_story_rollups,
    sentence_key,
)
from .theme import DEFAULT_THEME, Theme

type ReportView = Literal['scenarios', 'stories', 'glossary']


@dataclass(frozen=True)
class TabVisibility:
    """Which browse tabs a report has anything to show in."""

    scenarios: bool
    stories: bool
    glossary: bool

    @property
    def views(self) -> tuple[ReportView, ...]:
        """The shown views in tab order. The first is the one the page opens on."""
        shown: tuple[tuple[ReportView, bool], ...] = (
            ('scenarios', self.scenarios),
            ('stories', self.stories),
            ('glossary', self.glossary),
        )
        return tuple(view for view, visible in shown if visible)

    @property
    def visible_count(self) -> int:
        return len(self.views)


def tab_visibility(report: ReportData) -> TabVisibility:
    stories = bool(report.stories)
    glossary = bool(report.glossary is not None and report.glossary.terms)
    # A report with nothing at all keeps its empty Scenarios view, so the page
    # is never blank.
    return TabVisibility(
        scenarios=bool(report.scenarios) or not (stories or glossary),
        stories=stories,
        glossary=glossary,
    )


def render_html_string(
    report: ReportData,
    source_link_template: str | None,
    theme: Theme = DEFAULT_THEME,
    source_root: Path | None = None,
) -> str:
    """Render a report model to a self-contained HTML document.

    `source_link_template` is the already-resolved template string (preset
    expansion happens before this point). None disables source linking.
    `source_root` is what `{path}` resolves against (see
    `compile_source_link`). `theme` is the default the page opens in until the
    viewer picks one.

    Returns the document rather than writing it — `sinks` owns the writing.
    """
    # Built once and handed to both: the narration filter colors placeholders
    # with it, and the template emits the matching `.param-color-N` rules.
    param_color_map = build_param_color_map(report.scenarios)
    env = _build_env(report, source_link_template, source_root, param_color_map)
    return env.get_template('report.html.j2').render(
        **_render_context(report, param_color_map, theme)
    )


def _build_env(
    report: ReportData,
    source_link_template: str | None,
    source_root: Path | None,
    param_color_map: ParamColorMap,
) -> jinja2.Environment:
    """The Jinja environment: the shared one plus every filter the report's
    own data feeds."""
    env = base_env()
    # The sentence key's format lives in `story_view`; the template emits it
    # for the jump button and `app.js` looks the label up by it, so both sides
    # go through the one constructor.
    env.globals['sentence_key'] = sentence_key
    env.filters['source_url'] = make_source_url_filter(
        template=source_link_template,
        project=report.metadata.project,
        commit_sha=report.metadata.commit_sha,
        root=source_root,
    )
    env.filters['narration'] = make_narration_filter(
        param_color_map, glossary=report.glossary
    )
    env.filters['clause_part'] = make_clause_part_filter(report.glossary)
    env.filters['definition_md'] = make_definition_filter(report.glossary or Glossary())
    env.filters['param_color_class'] = make_param_color_class(param_color_map)
    return env


def base_env() -> jinja2.Environment:
    """The template loader and the filters and tests that read no report, which
    the report page and the delta page share."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    # The status filter's pills, in order; `app.js` reads the same table from
    # its data, so a new status touches neither.
    env.globals['statuses'] = tuple(STATUS_LABEL)
    # The step-tree macro branches on this: an AttachmentRef has no content to
    # expand, only a column to point at.
    env.tests['attachment_ref'] = lambda value: isinstance(value, AttachmentRef)
    env.filters['inline_md'] = inline_md
    env.filters['plural'] = plural
    env.filters['avoid_html'] = avoid_html
    env.filters['status_glyph'] = lambda status: STATUS_GLYPH.get(status, '')
    env.filters['status_label'] = lambda status: STATUS_LABEL.get(status, status)
    env.filters['phase_blocks'] = phase_blocks
    env.filters['column_phase_blocks'] = column_phase_blocks
    env.filters['repr_columns'] = repr_columns
    env.filters['case_id'] = case_id
    env.filters['value_cell'] = value_cell
    # No column coloured until a page passes its colour map.
    env.filters['param_color_class'] = make_param_color_class(None)
    env.globals['data_url'] = data_url
    return env


def _render_context(
    report: ReportData, param_color_map: ParamColorMap, theme: Theme
) -> dict[str, object]:
    """Everything `report.html.j2` reads, in three groups: the report model
    itself, the precomputed aggregations, and the JSON blobs the page's Alpine
    state is seeded from."""
    glossary_view = build_glossary_view(report)
    coverage = build_coverage_map(report)
    scn_covers = build_scenario_sentence_index(coverage)
    sentence_labels = build_sentence_labels(report)
    scenario_slugs = build_scenario_slug_index(report.scenarios)
    story_rollups = build_story_rollups(report, coverage)
    citation_index = CitationIndex(
        report,
        {story_id: rollup.scenarios for story_id, rollup in story_rollups.items()},
        glossary_view.term_scenarios,
    )
    visibility = tab_visibility(report)
    return {
        'metadata': report.metadata,
        'theme_default': theme,
        'scenarios': report.scenarios,
        'stories': report.stories,
        'glossary': report.glossary,
        'glossary_view': glossary_view,
        'tab_visibility': visibility,
        'story_rollups': story_rollups,
        'scn_covers': scn_covers,
        'scenario_index': {scn.id: index for index, scn in enumerate(report.scenarios)},
        'scenario_slugs': scenario_slugs,
        'citations': report.metadata.report_url is not None,
        # The colors themselves, one (light, dark) pair per column, emitted as
        # `--param-color-N` tokens beside the stylesheet. They are generated
        # per report rather than sitting in styles.css, because how many a
        # report needs is a property of the report.
        'param_colors': list(
            zip(
                param_column_colors(len(param_color_map), 'light'),
                param_column_colors(len(param_color_map), 'dark'),
                strict=True,
            )
        ),
        'app_data_js': script_json_parse(
            app_data(report)
            | {
                'views': list(visibility.views),
                'story_ids': [story.id for story in report.stories],
                'expandable_term_ids': glossary_view.expandable_term_ids,
                'term_scenarios': glossary_view.term_scenarios,
                'scenario_sentences': scn_covers,
                'sentence_labels': sentence_labels,
                'scenario_slugs': {
                    slug: node_id for node_id, slug in scenario_slugs.items()
                },
                'citations': citation_data(report, citation_index),
                'cited_scenario_ids': {
                    cited: scenario.id
                    for cited, scenario in citation_index.scenarios.items()
                    if cited != scenario.id
                },
            }
        ),
        **bundled_assets(),
    }
