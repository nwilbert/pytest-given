import json
from collections.abc import Callable
from pathlib import Path

import jinja2
from markupsafe import Markup, escape

from pytest_given.model import Scenario
from pytest_given.serde import report_from_dict
from pytest_given.source_link import format_source_link
from pytest_given.template import (
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationValue,
)

_NUM_PARAM_COLORS = 6

# Maps parameter name to its color index (0-based, wraps at _NUM_PARAM_COLORS)
type ParamColorMap = dict[str, int]


def render_html(
    json_path: Path,
    html_path: Path,
    source_link_template: str | None = None,
) -> None:
    """Render a JSON report to a self-contained HTML file.

    `source_link_template` is the already-resolved template string (preset
    expansion happens before this point). None disables source linking;
    each scenario then renders a plain `<span>` for its source location.
    """
    raw_json = json_path.read_text(encoding='utf-8')
    report = report_from_dict(json.loads(raw_json))

    templates_dir = Path(__file__).parent / 'templates'
    css = (templates_dir / 'styles.css').read_text(encoding='utf-8')
    app_js = (templates_dir / 'app.js').read_text(encoding='utf-8')
    alpine_js = (templates_dir / 'alpine.min.js').read_text(encoding='utf-8')

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )

    param_color_map = _build_param_color_map(report.scenarios)
    source_urls = _compute_source_urls(
        report.scenarios,
        project=report.metadata.project,
        commit_sha=report.metadata.commit_sha,
        source_link_template=source_link_template,
    )

    env.filters['narration'] = _make_narration_filter(param_color_map)
    template = env.get_template('report.html.j2')
    html = template.render(
        metadata=report.metadata,
        scenarios=report.scenarios,
        report_json=Markup(raw_json),
        css=Markup(css),
        app_js=Markup(app_js),
        alpine_js=Markup(alpine_js),
        param_color_map=param_color_map,
        num_param_colors=_NUM_PARAM_COLORS,
        source_urls=source_urls,
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding='utf-8')


def _build_param_color_map(scenarios: list[Scenario]) -> ParamColorMap:
    color_map: ParamColorMap = {}
    color_idx = 0
    for scenario in scenarios:
        if scenario.parameters is None:
            continue
        for name in scenario.parameters.names:
            if name not in color_map:
                color_map[name] = color_idx
                color_idx += 1
    return color_map


def _compute_source_urls(
    scenarios: list[Scenario],
    *,
    project: str,
    commit_sha: str | None,
    source_link_template: str | None,
) -> dict[int, str | None]:
    """Resolve per-scenario URLs once, keyed by scenario index.

    Returns None for scenarios with no `source` data and for all scenarios
    when `source_link_template` is None.
    """
    urls: dict[int, str | None] = {}
    for idx, scenario in enumerate(scenarios):
        if scenario.source is None or source_link_template is None:
            urls[idx] = None
            continue
        urls[idx] = format_source_link(
            source_link_template,
            source=scenario.source,
            project=project,
            commit_sha=commit_sha,
        )
    return urls


def _make_narration_filter(
    color_map: ParamColorMap,
) -> Callable[[Narration], Markup]:
    """Filter usage: `{{ step.narration | narration }}` or
    `{{ scenario.narration | narration }}`.

    The narration is a `Narration` dataclass with a flat `text` and a list
    of typed `NarrationPart` variants:
      - `NarrationLiteral` → escape `value`
      - `NarrationValue`   → `.param-value` highlight around `rendered`
      - `NarrationPlaceholder` → color-coded `{name!conv:spec}` token
    Empty parts → escape `text` and emit verbatim.
    """

    def _render(narration: Narration) -> Markup:
        if not narration.parts:
            return Markup(str(escape(narration.text)))
        out: list[str] = []
        for part in narration.parts:
            match part:
                case NarrationLiteral(value=value):
                    out.append(str(escape(value)))
                case NarrationValue(rendered=rendered):
                    out.append(f'<span class="param-value">{escape(rendered)}</span>')
                case NarrationPlaceholder(name=name):
                    color_idx = color_map.get(name, 0) % _NUM_PARAM_COLORS
                    label = _placeholder_token(part)
                    out.append(
                        f'<span class="param-color-{color_idx}">{escape(label)}</span>'
                    )
        return Markup(''.join(out))

    return _render


def _placeholder_token(part: NarrationPlaceholder) -> str:
    """Reconstruct the source-side `{name!conv:spec}` token, so the merged
    template view preserves the author's format intent."""
    inner = part.name
    if part.conversion:
        inner += '!' + part.conversion
    if part.format_spec:
        inner += ':' + part.format_spec
    return '{' + inner + '}'
