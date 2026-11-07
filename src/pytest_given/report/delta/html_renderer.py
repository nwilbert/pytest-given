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

from ...markdown import definition_html
from ...model import (
    Change,
    DeltaData,
    DeltaSide,
    Mark,
    Narration,
    Side,
    SourceLocation,
    change_counts,
    narration_of,
    narration_text,
    texts_in_context,
)
from ..glyphs import STATUS_LABEL
from ..html_renderer import (
    base_env,
    bundled_assets,
    bundled_script,
    make_narration_filter,
    make_source_url_filter,
    script_json_parse,
    shown_text,
    term_app_data,
)
from ..theme import DEFAULT_THEME, Theme
from .glossary import (
    DeltaGlossaryView,
    TermReach,
    before_tip_terms,
    delta_glossary_view,
    shown_term_scenarios,
    term_reach,
    tip_terms,
)
from .scenarios import ListedScenario, listed_scenarios
from .steps import MarkedRun

_SHORT_SHA = 7


# How a change is marked beside its word, wherever colour is not enough.
_CHANGE_GLYPH: dict[Change, str] = {
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
    module_changes = _module_changes(delta, listed)
    reach = term_reach(delta, listed)
    glossary_view = delta_glossary_view(delta, listed, reach)
    return {
        'title': delta.metadata.title or after.title or after.project,
        'range': (range_side(delta.metadata.before), range_side(delta.metadata.after)),
        # The version that built the delta: each side's run has its own.
        'plugin_version': delta.metadata.plugin_version,
        'listed': listed,
        'change_counts': change_counts(item.change for item in listed),
        'unchanged_count': len(delta.unchanged),
        'module_changes': module_changes,
        'glossary_view': glossary_view,
        # Browse by offers Terms as the report does, whenever a side has any.
        'browse_terms': bool(tip_terms(delta)),
        'change_glyph': _CHANGE_GLYPH,
        'theme_default': theme,
        # Parameter coloring is off on this page: green, red and amber mean
        # only added, removed and changed.
        'param_colors': [],
        'app_data_js': script_json_parse(
            _app_data(delta, listed, module_changes, reach, glossary_view)
        ),
        **bundled_assets('delta.css'),
        'delta_js': bundled_script('delta.js'),
    }


class RangeSide(NamedTuple):
    name: str
    detail: str | None = None


def range_side(side: DeltaSide) -> RangeSide:
    """The side's label over its short SHA; the report's timestamp, to the
    minute, stands in for a SHA it doesn't carry."""
    sha = side.metadata.commit_sha
    when = (
        sha[:_SHORT_SHA]
        if sha
        else f'{datetime.fromisoformat(side.metadata.timestamp):%Y-%m-%d %H:%M}'
    )
    return RangeSide(side.label, when) if side.label else RangeSide(when)


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
    module_changes: dict[str, Change],
    reach: TermReach,
    glossary_view: DeltaGlossaryView,
) -> dict[str, object]:
    """What `delta.js` seeds `reportApp()` with: the report's projection, one
    entry per listed scenario keyed by its slug, since a removed and an added
    scenario can share a node ID, and one per term card, keyed likewise."""
    return {
        'status_labels': STATUS_LABEL,
        'glossary': {'terms': [term_app_data(term) for term in tip_terms(delta)]},
        'before_terms': [term_app_data(term) for term in before_tip_terms(delta)],
        'term_ids': [card.key for card in glossary_view.listed],
        'term_cards': [
            {
                'key': card.key,
                'kind': card.shown.kind or 'kindless',
                'change': card.change,
                'defined': card.shown.definition is not None,
                'search': card.search_text,
                'before': card.delta.before.id if card.delta.before else None,
                'after': card.delta.after.id if card.delta.after else None,
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
                'search_text': _search_text(item),
            }
            for item in listed
        ],
        'scenario_slugs': {item.slug: item.slug for item in listed},
        'module_changes': module_changes,
        'change_glyphs': _CHANGE_GLYPH,
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
    # Parameter colouring is off on this page. A ref links only to a term the
    # Glossary tab lists: an unchanged one has no card to open.
    terms = delta.glossary.terms
    narration_filters = {
        'before': make_narration_filter(
            None,
            delta.glossary.before,
            term_side='before',
            linked_terms={term.before.id for term in terms if term.before},
        ),
        'after': make_narration_filter(
            None,
            delta.glossary.after,
            term_side='after',
            linked_terms={term.after.id for term in terms if term.after},
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
    env.filters['source_url'] = source_url
    return env


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
