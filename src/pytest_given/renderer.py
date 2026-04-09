from __future__ import annotations

import json
from pathlib import Path

import jinja2
from markupsafe import Markup


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
    template = env.get_template('report.html.j2')
    html = template.render(
        metadata=data['metadata'],
        scenarios=data['scenarios'],
        report_json=Markup(json.dumps(data)),
        css=Markup(css),
        alpine_js=Markup(alpine_js),
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html)
