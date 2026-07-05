from pathlib import Path

from ..model import (
    ErrorInfo,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    ParameterTable,
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
    suffix = ''
    if scenario.status == 'skipped':
        suffix = ' · skipped'
    elif scenario.parameters is not None:
        suffix = f' · {len(scenario.parameters.cases)} cases'
    lines = [f'## {glyph} {_narration_md(scenario.narration)}{suffix}']
    subtitle = f'`{scenario.id}`'
    if scenario.tags:
        subtitle += ' · ' + ', '.join(scenario.tags)
    if scenario.skip_reason:
        subtitle += f' — reason: {scenario.skip_reason}'
    lines.append(subtitle)
    lines.append('')
    for step in scenario.steps:
        lines.append(_step_md(step, depth=0))
    if scenario.parameters is not None:
        lines.append('')
        lines.append(_param_table_md(scenario.parameters))
    return '\n'.join(lines)


def _param_table_md(table: ParameterTable) -> str:
    header = '| ' + ' | '.join([*table.names, '']) + '|'
    separator = '|' + '---|' * (len(table.names) + 1)
    rows = [
        '| '
        + ' | '.join(
            [*(str(v) for v in case.values), _STATUS_GLYPH.get(case.status, '✗')]
        )
        + ' |'
        for case in table.cases
    ]
    return '\n'.join([header, separator, *rows])


def _step_md(step: Step, depth: int) -> str:
    indent = '  ' * depth
    bullet = f'{indent}- **{step.phase}** {_narration_md(step.narration)}'
    if step.status == 'failed':
        bullet += '  **← FAILED**'
    lines = [bullet]
    if step.error is not None:
        lines.extend(_error_lines(step.error, indent))
    for attachment in step.attachments:
        lines.append(f'{indent}  - 📎 {attachment.label} — `{attachment.content}`')
    for child in step.children:
        lines.append(_step_md(child, depth + 1))
    return '\n'.join(lines)


def _error_lines(error: ErrorInfo, indent: str) -> list[str]:
    lines = []
    first = error.message.splitlines()[0] if error.message else ''
    if first:
        lines.append(f'{indent}  > {first}')
    for frame in reversed(error.frames):
        if not frame.is_internal:
            lines.append(
                f'{indent}  > {Path(frame.path).name}:{frame.lineno} in {frame.func}'
            )
            break
    return lines


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
