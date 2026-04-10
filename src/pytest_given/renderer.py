from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import jinja2
from markupsafe import Markup, escape

_NUM_PARAM_COLORS = 6
_PARAM_RE = re.compile(r'\{([a-zA-Z_]\w*)\}')

# Maps parameter name to its color index (0-based, wraps at _NUM_PARAM_COLORS)
type ParamColorMap = dict[str, int]


def _make_highlight_filter(
    color_map: ParamColorMap,
) -> Callable[[str], Markup]:
    """Create a Jinja2 filter that highlights {param_name} with color-coded spans."""

    def _highlight_params(text: str) -> Markup:
        def _replace(m: re.Match[str]) -> str:
            name = m.group(1)
            if name not in color_map:
                return m.group(0)
            color_idx = color_map[name] % _NUM_PARAM_COLORS
            return f'<span class="param-color-{color_idx}">{escape(m.group(0))}</span>'

        result = _PARAM_RE.sub(_replace, str(escape(text)))
        return Markup(result)

    return _highlight_params


def render_html(json_path: Path, html_path: Path) -> None:
    """Render a JSON report to a self-contained HTML file."""
    raw_json = json_path.read_text()
    data = json.loads(raw_json)

    templates_dir = Path(__file__).parent / 'templates'
    css = (templates_dir / 'styles.css').read_text()
    alpine_js = (templates_dir / 'alpine.min.js').read_text()

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )

    # Build param color map from all parameterized scenarios
    param_color_map: ParamColorMap = {}
    color_idx = 0
    for scenario in data['scenarios']:
        params = scenario.get('parameters')
        if params:
            for name in params['names']:
                if name not in param_color_map:
                    param_color_map[name] = color_idx
                    color_idx += 1

    env.filters['highlight_params'] = _make_highlight_filter(param_color_map)
    template = env.get_template('report.html.j2')
    html = template.render(
        metadata=data['metadata'],
        scenarios=data['scenarios'],
        report_json=Markup(raw_json),
        css=Markup(css),
        alpine_js=Markup(alpine_js),
        param_color_map=param_color_map,
        num_param_colors=_NUM_PARAM_COLORS,
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html)
