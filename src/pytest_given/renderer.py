from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jinja2


def _build_step_html(steps: list[dict[str, Any]], depth: int = 0) -> str:
    """Recursively build HTML for steps."""
    html_parts: list[str] = []
    current_phase: str | None = None

    for step in steps:
        phase = step['phase']
        if phase != current_phase:
            current_phase = phase
            html_parts.append(
                f'<div class="phase-label phase-{phase}">{phase.capitalize()}</div>'
            )

        html_parts.append(f'<div class="step-text">{_escape(step["text"])}</div>')

        if step.get('attachments'):
            for att in step['attachments']:
                att_id = id(att)
                html_parts.append(
                    f'<div class="step-text">'
                    f'<span class="attachment-badge" '
                    f'@click="expandedAttachments.has({att_id!r}) '
                    f'? expandedAttachments.delete({att_id!r}) '
                    f': expandedAttachments.add({att_id!r})">'
                    f'📎 {_escape(att["label"])}</span>'
                    f'<div class="attachment-content" '
                    f'x-show="expandedAttachments.has({att_id!r})">'
                    f'{_escape(att["content"])}</div>'
                    f'</div>'
                )

        if step.get('children'):
            html_parts.append('<div class="step-children">')
            html_parts.append(_build_step_html(step['children'], depth + 1))
            html_parts.append('</div>')

        if step.get('error'):
            err = step['error']
            html_parts.append('<div class="error-block">')
            html_parts.append(
                f'<div class="error-message">{_escape(err["message"])}</div>'
            )
            if err.get('diff'):
                html_parts.append(
                    f'<pre class="error-diff">{_escape(err["diff"])}</pre>'
                )
            html_parts.append('</div>')

    return '\n'.join(html_parts)


def _escape(text: str) -> str:
    """HTML-escape text."""
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def render_html(json_path: Path, html_path: Path) -> None:
    """Render a JSON report to a self-contained HTML file."""
    data = json.loads(json_path.read_text())

    # Pre-render steps to HTML
    for scenario in data['scenarios']:
        scenario['_steps_html'] = _build_step_html(scenario.get('steps', []))

    templates_dir = Path(__file__).parent / 'templates'
    css = (templates_dir / 'styles.css').read_text()
    alpine_js = (templates_dir / 'alpine.min.js').read_text()

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=False,
    )
    template = env.get_template('report.html.j2')
    html = template.render(
        metadata=data['metadata'],
        scenarios=data['scenarios'],
        report_json=json.dumps(data),
        css=css,
        alpine_js=alpine_js,
        render_steps=lambda steps: _build_step_html(steps),
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html)
