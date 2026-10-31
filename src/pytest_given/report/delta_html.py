"""Rendering the delta HTML: the page's context and the filters it reads.

Each listed scenario renders against its own side: its term refs resolve in
that side's glossary, and its source link names that side's commit.
"""

# A CLI command that renders no HTML never loads Jinja or MarkupSafe.
__lazy_modules__ = ['jinja2', 'markupsafe']

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import jinja2
from markupsafe import Markup

from ..model import (
    Change,
    DeltaData,
    DeltaSide,
    Glossary,
    GlossaryTerm,
    Narration,
    NodeId,
    ParameterColumn,
    ReportData,
    Scenario,
    ScenarioDelta,
    SourceLocation,
)
from .html_renderer import (
    base_env,
    build_param_color_map,
    bundled_assets,
    make_narration_filter,
    make_source_url_filter,
    script_json_parse,
    shown_text,
    term_app_data,
)
from .slugs import build_scenario_slug_index
from .text import STATUS_LABEL
from .theme import DEFAULT_THEME, Theme

_SHORT_SHA = 7
# The Change filter's order: what a release brings, then what it took away.
_CHANGE_ORDER: tuple[Change, ...] = ('added', 'changed', 'removed')
# How a change is marked beside its word, wherever colour is not enough.
_CHANGE_GLYPH: dict[Change, str] = {
    'added': '+',
    'changed': '~',
    'removed': '\N{MINUS SIGN}',
}

type Side = Literal['before', 'after']


@dataclass(frozen=True)
class ReasonRow:
    """A skip or xfail reason as the row shows it, with the before side's
    reason it replaced, if any."""

    status: Literal['skipped', 'xfailed']
    label: str
    reason: str | None
    was: str | None


@dataclass(frozen=True)
class ListedScenario:
    delta: ScenarioDelta
    # Prefixed `removed-` for a removed scenario, so a removed and an added
    # scenario sharing one node ID still have a slug each.
    slug: str

    @property
    def change(self) -> Change:
        return self.delta.change

    @property
    def side(self) -> Side:
        """The side shown: after, or before for a removed scenario."""
        return 'before' if self.delta.after is None else 'after'

    @property
    def shown(self) -> Scenario:
        shown = self.delta.after or self.delta.before
        assert shown is not None
        return shown

    @property
    def fragment(self) -> str:
        return f'scenario={self.slug}'

    @property
    def reasons(self) -> list[ReasonRow]:
        replaced = self.delta.before if self.delta.reason_changed else None
        rows = [
            _reason_row(
                'skipped',
                'Skipped:',
                self.shown.skip_reason,
                replaced.skip_reason if replaced else None,
            ),
            _reason_row(
                'xfailed',
                'Expected to fail:',
                self.shown.xfail_reason,
                replaced.xfail_reason if replaced else None,
            ),
        ]
        return [row for row in rows if row.reason or row.was]


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
    listed = _listed_scenarios(delta)
    module_changes = _module_changes(delta, listed)
    return {
        'title': after.title or after.project,
        'range': (
            f'{range_label(delta.metadata.before)} to '
            f'{range_label(delta.metadata.after)}'
        ),
        'listed': listed,
        'change_counts': {
            change: sum(item.change == change for item in listed)
            for change in _CHANGE_ORDER
        },
        'unchanged_count': len(delta.unchanged),
        'module_changes': module_changes,
        'change_glyph': _CHANGE_GLYPH,
        'theme_default': theme,
        # Parameter coloring is off on this page: green, red and amber mean
        # only added, removed and changed.
        'param_colors': [],
        'app_data_js': script_json_parse(_app_data(delta, listed, module_changes)),
        **bundled_assets(),
    }


def range_label(side: DeltaSide) -> str:
    """The side's label and short SHA; the report's timestamp stands in for a
    SHA it doesn't carry."""
    sha = side.metadata.commit_sha
    when = sha[:_SHORT_SHA] if sha else side.metadata.timestamp
    return f'{side.label} {when}' if side.label else when


def _listed_scenarios(delta: DeltaData) -> list[ListedScenario]:
    # Slugged per side, each from the scenarios it shows.
    before_slugs = _slugs(
        delta.metadata.before,
        [_removed(listed) for listed in delta.scenarios if listed.after is None],
    )
    after_slugs = _slugs(
        delta.metadata.after,
        [listed.after for listed in delta.scenarios if listed.after is not None],
    )
    return [
        ListedScenario(
            listed,
            after_slugs[listed.after.id]
            if listed.after is not None
            else 'removed-' + before_slugs[_removed(listed).id],
        )
        for listed in delta.scenarios
    ]


def _slugs(side: DeltaSide, scenarios: list[Scenario]) -> dict[NodeId, str]:
    return build_scenario_slug_index(
        ReportData(metadata=side.metadata, scenarios=scenarios)
    )


def _removed(scenario_delta: ScenarioDelta) -> Scenario:
    assert scenario_delta.before is not None
    return scenario_delta.before


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


def _reason_row(
    status: Literal['skipped', 'xfailed'],
    label: str,
    reason: str | None,
    replaced: str | None,
) -> ReasonRow:
    return ReasonRow(status, label, reason, replaced if replaced != reason else None)


def _app_data(
    delta: DeltaData,
    listed: list[ListedScenario],
    module_changes: dict[str, Change],
) -> dict[str, object]:
    """What `delta.js` seeds `reportApp()` with: the report's projection, one
    entry per listed scenario keyed by its slug, since a removed and an added
    scenario can share a node ID."""
    return {
        'metadata': {'timestamp': delta.metadata.after.metadata.timestamp},
        'status_labels': STATUS_LABEL,
        'glossary': {'terms': [term_app_data(term) for term in _tip_terms(delta)]},
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


def _tip_terms(delta: DeltaData) -> list[GlossaryTerm]:
    """Every term the tooltip may be asked about: the after glossary's, and
    the before glossary's the after one dropped."""
    after = delta.glossary.after.terms if delta.glossary.after else []
    after_ids = {term.id for term in after}
    before = delta.glossary.before.terms if delta.glossary.before else []
    return [*after, *(term for term in before if term.id not in after_ids)]


def _build_env(
    delta: DeltaData, source_link_template: str | None
) -> jinja2.Environment:
    env = base_env()
    listed = _listed_scenarios(delta)
    param_color_map = build_param_color_map([item.shown for item in listed])
    glossaries: dict[Side, Glossary | None] = {
        'before': delta.glossary.before,
        'after': delta.glossary.after,
    }
    narration_filters = {
        side: make_narration_filter(param_color_map, glossary)
        for side, glossary in glossaries.items()
    }
    # Compiled only for a side some scenario is shown from, so a `{sha}`
    # template fails only when a link would need the SHA a side lacks.
    shown_sides = {item.side for item in listed}
    source_url_filters = {
        side: _source_url_filter(source_link_template, side_of)
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

    def no_param_color(column: ParameterColumn) -> str:
        return ''

    env.filters['narration'] = narration
    env.filters['source_url'] = source_url
    env.filters['param_color_class'] = no_param_color
    return env


def _source_url_filter(
    template: str | None, side: DeltaSide
) -> Callable[[SourceLocation | None], str | None]:
    return make_source_url_filter(
        template=template,
        project=side.metadata.project,
        commit_sha=side.metadata.commit_sha,
        root=None,
    )
