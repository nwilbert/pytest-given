from __future__ import annotations

import json
import re
from pathlib import Path

import jinja2
from markupsafe import Markup, escape

_NUM_PARAM_COLORS = 6
# Set by render_html for the current rendering context
_param_color_map: dict[str, int] = {}


def _highlight_params(text: str) -> Markup:
    """Replace {param_name} with color-coded <span> tags."""

    def _replace(m: re.Match[str]) -> str:
        name = m.group(1)
        color_idx = _param_color_map.get(name, 0) % _NUM_PARAM_COLORS
        return f'<span class="param-color-{color_idx}">{escape(m.group(0))}</span>'

    result = re.sub(r'\{([a-zA-Z_]\w*)\}', _replace, str(escape(text)))
    return Markup(result)


def render_html(json_path: Path, html_path: Path) -> None:
    """Render a JSON report to a self-contained HTML file."""
    data = json.loads(json_path.read_text())

    templates_dir = Path(__file__).parent / 'templates'
    css = (templates_dir / 'styles.css').read_text()
    alpine_js = (templates_dir / 'alpine.min.js').read_text()

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )
    # Build param color map from all parameterized scenarios
    _param_color_map.clear()
    color_idx = 0
    for scenario in data['scenarios']:
        params = scenario.get('parameters')
        if params:
            for name in params['names']:
                if name not in _param_color_map:
                    _param_color_map[name] = color_idx
                    color_idx += 1

    env.filters['highlight_params'] = _highlight_params
    template = env.get_template('report.html.j2')
    html = template.render(
        metadata=data['metadata'],
        scenarios=data['scenarios'],
        report_json=Markup(json.dumps(data)),
        css=Markup(css),
        alpine_js=Markup(alpine_js),
        param_color_map=_param_color_map,
        num_param_colors=_NUM_PARAM_COLORS,
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html)
