"""Rendering the delta HTML: the page's context and the filters it reads.

Each listed scenario renders against its own side: its term refs resolve in
that side's glossary, and its source link names that side's commit.
"""

# A CLI command that renders no HTML never loads Jinja or MarkupSafe.
__lazy_modules__ = ['jinja2', 'markupsafe']

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import jinja2
from markupsafe import Markup

from ..model import (
    Change,
    DeltaData,
    DeltaSide,
    Glossary,
    Narration,
    Scenario,
    ScenarioDelta,
    SourceLocation,
)
from .html_renderer import (
    build_param_color_map,
    bundled_assets,
    data_url,
    make_narration_filter,
    make_source_url_filter,
)
from .palette import param_column_colors
from .theme import DEFAULT_THEME, Theme

_TEMPLATES_DIR = Path(__file__).parent / 'templates'
_SHORT_SHA = 7

type Side = Literal['before', 'after']


@dataclass(frozen=True)
class ListedScenario:
    change: Change
    side: Side  # the side shown: after, or before for a removed scenario
    scenario: Scenario


def render_delta_html(
    delta: DeltaData,
    source_link_template: str | None,
    theme: Theme = DEFAULT_THEME,
) -> str:
    env = _build_env(delta, source_link_template, _listed_scenarios(delta))
    return env.get_template('delta.html.j2').render(
        **delta_render_context(delta, theme)
    )


def delta_render_context(
    delta: DeltaData, theme: Theme = DEFAULT_THEME
) -> dict[str, object]:
    after = delta.metadata.after.metadata
    listed = _listed_scenarios(delta)
    color_count = len(build_param_color_map([item.scenario for item in listed]))
    return {
        'title': after.title or after.project,
        'range': (
            f'{range_label(delta.metadata.before)} to '
            f'{range_label(delta.metadata.after)}'
        ),
        'listed': listed,
        'theme_default': theme,
        'param_colors': list(
            zip(
                param_column_colors(color_count, 'light'),
                param_column_colors(color_count, 'dark'),
                strict=True,
            )
        ),
        'css': bundled_assets()['css'],
    }


def range_label(side: DeltaSide) -> str:
    """The side's label and short SHA; the report's timestamp stands in for a
    SHA it doesn't carry."""
    sha = side.metadata.commit_sha
    when = sha[:_SHORT_SHA] if sha else side.metadata.timestamp
    return f'{side.label} {when}' if side.label else when


def _listed_scenarios(delta: DeltaData) -> list[ListedScenario]:
    return [_listed_scenario(scenario_delta) for scenario_delta in delta.scenarios]


def _listed_scenario(scenario_delta: ScenarioDelta) -> ListedScenario:
    if scenario_delta.after is not None:
        return ListedScenario(scenario_delta.change, 'after', scenario_delta.after)
    assert scenario_delta.before is not None
    return ListedScenario(scenario_delta.change, 'before', scenario_delta.before)


def _build_env(
    delta: DeltaData, source_link_template: str | None, listed: list[ListedScenario]
) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    param_color_map = build_param_color_map([item.scenario for item in listed])
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

    env.filters['narration'] = narration
    env.filters['source_url'] = source_url
    env.globals['data_url'] = data_url
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
