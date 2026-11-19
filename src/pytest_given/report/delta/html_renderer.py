"""Rendering the delta HTML: the page's context and the filters it reads.

Each listed scenario and term renders against its own side: its term refs
resolve in that side's glossary, and its source link names that side's commit.
"""

# A CLI command that renders no HTML never loads Jinja or MarkupSafe.
__lazy_modules__ = ['jinja2', 'markupsafe']

from collections.abc import Iterator
from datetime import datetime
from typing import NamedTuple

import jinja2
from markupsafe import Markup

from ...delta import (
    CHANGED_PARTS,
    SIDE_MARK,
    Change,
    DeltaData,
    Mark,
    Side,
    TextSegment,
    change_counts,
    on_side,
)
from ...markdown import definition_html
from ...model import (
    GlossaryTerm,
    Narration,
    SourceLocation,
    narration_of,
    narration_text,
    texts_in_context,
)
from ..app_data import term_app_data
from ..glyphs import STATUS_LABEL
from ..html_assets import bundled_assets, bundled_script, script_json_parse
from ..html_narration import make_narration_filter, make_source_url_filter, shown_text
from ..html_renderer import base_env
from ..theme import DEFAULT_THEME, Theme
from .attachments import FoldRow
from .glossary import (
    DeltaGlossaryView,
    TermReach,
    delta_glossary_view,
    shown_term_scenarios,
    term_reach,
    term_ref_targets,
    tip_terms,
)
from .scenarios import ListedScenario, listed_scenarios
from .steps import MarkedRun, joined_marks

_SHORT_SHA = 7

# How a change is marked beside its word, wherever colour is not enough.
CHANGE_GLYPH: dict[Change, str] = {
    'added': '+',
    'changed': '~',
    'removed': '\N{MINUS SIGN}',
}


def render_delta_html(
    delta: DeltaData,
    source_link_template: str | None,
    theme: Theme = DEFAULT_THEME,
) -> str:
    context = delta_render_context(delta, theme)
    env = _build_env(delta, source_link_template)
    return env.get_template('delta.html.j2').render(**context)


def delta_render_context(
    delta: DeltaData, theme: Theme = DEFAULT_THEME
) -> dict[str, object]:
    after = delta.metadata.after.metadata
    listed = listed_scenarios(delta)
    reach = term_reach(delta, listed)
    glossary_view = delta_glossary_view(delta, listed, reach)
    tips = tip_terms(delta)
    return {
        'title': delta.metadata.title or after.title or after.project,
        'range': (range_side(delta, 'before'), range_side(delta, 'after')),
        # The version that built the delta: each side's run has its own.
        'plugin_version': delta.metadata.plugin_version,
        'listed': listed,
        'change_counts': change_counts(item.change for item in listed),
        # A scenario counts under each part it changed in.
        'changed_in_counts': {
            part: sum(part in item.delta.changed_in for item in listed)
            for part in CHANGED_PARTS
        },
        'unchanged_count': len(delta.unchanged),
        'glossary_view': glossary_view,
        # Browse by offers Terms as the report does, whenever a side has any.
        'browse_terms': bool(tips),
        'change_glyph': CHANGE_GLYPH,
        'theme_default': theme,
        # Parameter coloring is off on this page: green, red and amber mean
        # only added, removed and changed.
        'param_colors': [],
        'app_data_js': script_json_parse(
            _app_data(delta, listed, reach, glossary_view, tips)
        ),
        **bundled_assets('delta.css'),
        'delta_js': bundled_script('delta.js'),
    }


class RangeSide(NamedTuple):
    """A compared side: the header shows its name, its tooltip the rest."""

    side: Side
    name: str
    commit_sha: str | None
    ran_at: str
    report_file: str | None
    report_title: str
    scenario_count: int
    pytest_version: str
    plugin_version: str


def range_side(delta: DeltaData, side: Side) -> RangeSide:
    """Named by its label, else its short SHA, else its run time."""
    delta_side = on_side(side, delta.metadata.before, delta.metadata.after)
    metadata = delta_side.metadata
    sha = metadata.commit_sha
    when = datetime.fromisoformat(metadata.timestamp)
    return RangeSide(
        side=side,
        name=delta_side.label
        or (sha[:_SHORT_SHA] if sha else f'{when:%Y-%m-%d %H:%M}'),
        commit_sha=sha,
        ran_at=f'{when:%Y-%m-%d %H:%M %Z}'.rstrip(),
        report_file=delta_side.report_file,
        report_title=metadata.title or metadata.project,
        # Every scenario of the side is listed or unchanged.
        scenario_count=len(delta.unchanged)
        + sum(item.on(side) is not None for item in delta.scenarios),
        pytest_version=metadata.pytest_version,
        plugin_version=metadata.plugin_version,
    )


def text_diff(words: tuple[TextSegment, ...], side: Side) -> Markup:
    """A changed attachment line on one side, its changed words marked."""
    return Markup('').join(
        _marked(segment.mark, Markup.escape(segment.text))
        for segment in _side_segments(words, side)
    )


def _module_changes(
    delta: DeltaData, listed: list[ListedScenario]
) -> dict[str, Change]:
    """Each listed scenario's module, by which sides have it at all."""
    before = set(delta.metadata.before.modules)
    after = set(delta.metadata.after.modules)
    changes: dict[str, Change] = {}
    for item in listed:
        module = item.shown.module
        if module in before and module in after:
            changes[module] = 'changed'
        else:
            changes[module] = 'removed' if module in before else 'added'
    return changes


def _app_data(
    delta: DeltaData,
    listed: list[ListedScenario],
    reach: TermReach,
    glossary_view: DeltaGlossaryView,
    tips: dict[str, GlossaryTerm],
) -> dict[str, object]:
    """What `delta.js` seeds `reportApp()` with: the report's projection, one
    entry per listed scenario keyed by its slug, since a removed and an added
    scenario can share a node ID, and one row per term card, keyed likewise.
    The glossary holds every term a tooltip shows, by the key a ref names it
    by."""
    return {
        'status_labels': STATUS_LABEL,
        'views': ['scenarios', 'glossary'] if glossary_view.listed else ['scenarios'],
        'glossary': {
            'terms': [{**term_app_data(term), 'id': key} for key, term in tips.items()]
        },
        'expandable_term_ids': [card.key for card in glossary_view.listed],
        'term_rows': [
            {
                'key': card.key,
                'kind': card.shown.kind or 'kindless',
                'change': card.change,
                'defined': card.shown.definition is not None,
                'search': card.search_text,
            }
            for card in glossary_view.listed
        ],
        'term_scenarios': shown_term_scenarios(reach),
        'scenarios': [
            {
                'id': item.slug,
                'module': item.shown.module,
                'tags': item.shown.tags,
                'status': item.shown.status,
                'change': item.change,
                'changed_in': list(item.delta.changed_in),
                'search_text': _search_text(item),
            }
            for item in listed
        ],
        'changed_parts': list(CHANGED_PARTS),
        'module_changes': _module_changes(delta, listed),
        'change_glyphs': CHANGE_GLYPH,
    }


def _search_text(item: ListedScenario) -> str:
    """Both sides' titles, and the tags only the before side had."""
    sides = (item.delta.before, item.delta.after)
    titles = [shown_text(side.narration) for side in sides if side is not None]
    return ' '.join([*titles, *item.delta.tags_removed])


def _build_env(
    delta: DeltaData, source_link_template: str | None
) -> jinja2.Environment:
    env = base_env()
    # Parameter colouring is off on this page.
    ref_targets = term_ref_targets(delta)
    narration_filters = {
        'before': make_narration_filter(
            None, delta.glossary.before, ref_targets=ref_targets['before']
        ),
        'after': make_narration_filter(
            None, delta.glossary.after, ref_targets=ref_targets['after']
        ),
    }
    # Compiled only for a side some scenario or term is shown from, so a
    # `{sha}` template fails only when a link would need the SHA a side lacks.
    shown_sides = {item.shown_side for item in delta.scenarios} | {
        term_delta.shown_side for term_delta in delta.glossary.terms
    }
    source_url_filters = {
        side: make_source_url_filter(
            template=source_link_template,
            project=side_of.metadata.project,
            commit_sha=side_of.metadata.commit_sha,
            root=None,
        )
        for side, side_of in (
            ('before', delta.metadata.before),
            ('after', delta.metadata.after),
        )
        if side in shown_sides
    }

    def narration(value: Narration, side: Side) -> Markup:
        return narration_filters[side](value)

    def source_url(value: SourceLocation | None, side: Side) -> str | None:
        return source_url_filters[side](value)

    def narration_diff(words: tuple[MarkedRun, ...], side: Side) -> Markup:
        """A modified step's text on one side, its changed words marked. A run
        holds whole spans, so each renders on its own, flanked by its
        neighbours as the whole line would flank it."""
        return Markup('').join(
            _marked(
                run.mark,
                narration_filters[side](
                    narration_of(run.parts), before=before, after=after
                ),
            )
            for run, (before, after) in zip(words, _contexts(words), strict=True)
        )

    def definition_diff(words: tuple[MarkedRun, ...]) -> Markup:
        """A changed definition on one side, its changed words marked."""
        return Markup('').join(
            _marked(
                run.mark,
                Markup(
                    definition_html(
                        narration_text(run.parts), before=before, after=after
                    )
                ),
            )
            for run, (before, after) in zip(words, _contexts(words), strict=True)
        )

    env.filters['narration'] = narration
    env.filters['narration_diff'] = narration_diff
    env.filters['definition_diff'] = definition_diff
    env.filters['text_diff'] = text_diff
    env.tests['fold_row'] = lambda value: isinstance(value, FoldRow)
    env.filters['source_url'] = source_url
    return env


def _side_segments(words: tuple[TextSegment, ...], side: Side) -> list[TextSegment]:
    """The side's own segments, joined as `steps.side_runs` joins a narration's."""
    own = [segment for segment in words if segment.mark in ('equal', SIDE_MARK[side])]
    return [
        TextSegment(mark=mark, text=''.join(segment.text for segment in group))
        for mark, group in joined_marks(
            own, [segment.text.isspace() for segment in own]
        )
    ]


def _contexts(words: tuple[MarkedRun, ...]) -> Iterator[tuple[str, str]]:
    return texts_in_context([narration_text(run.parts) for run in words])


def _marked(mark: Mark, text: Markup) -> Markup:
    match mark:
        case 'equal':
            return text
        case 'removed':
            return Markup('<del class="delta-words">{}</del>').format(text)
        case 'added':
            return Markup('<ins class="delta-words">{}</ins>').format(text)
