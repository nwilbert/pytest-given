import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jinja2
from markupsafe import Markup, escape

_NUM_PARAM_COLORS = 6

# Maps parameter name to its color index (0-based, wraps at _NUM_PARAM_COLORS)
type ParamColorMap = dict[str, int]


def render_html(json_path: Path, html_path: Path) -> None:
    """Render a JSON report to a self-contained HTML file."""
    raw_json = json_path.read_text(encoding='utf-8')
    data = json.loads(raw_json)

    templates_dir = Path(__file__).parent / 'templates'
    css = (templates_dir / 'styles.css').read_text(encoding='utf-8')
    app_js = (templates_dir / 'app.js').read_text(encoding='utf-8')
    alpine_js = (templates_dir / 'alpine.min.js').read_text(encoding='utf-8')

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )

    param_color_map: ParamColorMap = {}
    color_idx = 0
    for scenario in data['scenarios']:
        params = scenario.get('parameters')
        if params:
            for name in params['names']:
                if name not in param_color_map:
                    param_color_map[name] = color_idx
                    color_idx += 1

    env.filters['narration'] = _make_narration_filter(param_color_map)
    template = env.get_template('report.html.j2')
    html = template.render(
        metadata=data['metadata'],
        scenarios=data['scenarios'],
        report_json=Markup(raw_json),
        css=Markup(css),
        app_js=Markup(app_js),
        alpine_js=Markup(alpine_js),
        param_color_map=param_color_map,
        num_param_colors=_NUM_PARAM_COLORS,
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding='utf-8')


def _make_narration_filter(
    color_map: ParamColorMap,
) -> Callable[[dict[str, Any]], Markup]:
    """Filter usage: `{{ step.narration | narration }}` or
    `{{ scenario.narration | narration }}`.

    The narration dict has `text` (plain rendering) and `parts` (a list of
    serialized NarrationPart variants). Empty `parts` → escape `text` and emit.
    Otherwise each part is identified by its unique key:
      - `value` → NarrationLiteral
      - `rendered` → NarrationValue (.param-value highlight)
      - `name` → NarrationPlaceholder (color-coded `{name}` token)
    """

    def _render(narration: dict[str, Any]) -> Markup:
        parts = narration.get('parts') or []
        if not parts:
            return Markup(str(escape(narration.get('text', ''))))
        out: list[str] = []
        for part in parts:
            if 'value' in part:
                out.append(str(escape(part['value'])))
            elif 'rendered' in part:
                out.append(
                    f'<span class="param-value">{escape(part["rendered"])}</span>'
                )
            else:
                name = part['name']
                color_idx = color_map.get(name, 0) % _NUM_PARAM_COLORS
                label = _placeholder_token(part)
                out.append(
                    f'<span class="param-color-{color_idx}">{escape(label)}</span>'
                )
        return Markup(''.join(out))

    return _render


def _placeholder_token(part: dict[str, Any]) -> str:
    """Reconstruct the source-side `{name!conv:spec}` token from a placeholder
    dict, so the merged template view preserves the author's format intent."""
    inner: str = part['name']
    conversion = part.get('conversion')
    if conversion:
        inner += '!' + conversion
    spec = part.get('format_spec')
    if spec:
        inner += ':' + spec
    return '{' + inner + '}'
