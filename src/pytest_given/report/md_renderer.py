from ..model import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    ReportData,
    Scenario,
    Step,
)

_STATUS_GLYPH = {'passed': '✓', 'failed': '✗', 'skipped': '⤼'}


def render_md(report: ReportData) -> str:
    """Render the report model to an agent-facing Markdown string."""
    blocks = [f'# pytest-given — {report.metadata.project}']
    blocks.extend(_scenario_md(scenario) for scenario in report.scenarios)
    return '\n\n'.join(blocks) + '\n'


def _scenario_md(scenario: Scenario) -> str:
    glyph = _STATUS_GLYPH.get(scenario.status, '✗')
    lines = [f'## {glyph} {_narration_md(scenario.narration)}']
    subtitle = f'`{scenario.id}`'
    if scenario.tags:
        subtitle += ' · ' + ', '.join(scenario.tags)
    lines.append(subtitle)
    lines.append('')
    for step in scenario.steps:
        lines.append(_step_md(step, depth=0))
    return '\n'.join(lines)


def _step_md(step: Step, depth: int) -> str:
    indent = '  ' * depth
    lines = [f'{indent}- **{step.phase}** {_narration_md(step.narration)}']
    for attachment in step.attachments:
        lines.append(f'{indent}  - 📎 {attachment.label} — `{attachment.content}`')
    for child in step.children:
        lines.append(_step_md(child, depth + 1))
    return '\n'.join(lines)


def _narration_md(narration: Narration) -> str:
    if not narration.parts:
        return narration.text
    return ''.join(_part_md(part) for part in narration.parts)


def _part_md(part: NarrationPart) -> str:
    match part:
        case NarrationLiteral(value=value):
            return value
        case NarrationValue(rendered=rendered):
            return rendered
        case NarrationPlaceholder(name=name):
            return '{' + name + '}'
        case NarrationTermRef(display=display):
            return f'«{display}»'
