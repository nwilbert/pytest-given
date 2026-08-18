import re
from pathlib import Path

from ..model import (
    Attachment,
    AttachmentRef,
    CellValue,
    ErrorInfo,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
    StepAttachment,
    node_base,
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
    subtitle = f'`{_source_md(scenario)}`'
    if scenario.tags:
        subtitle += ' · ' + ', '.join(scenario.tags)
    if scenario.skip_reason:
        subtitle += f' — reason: {scenario.skip_reason}'
    lines.append(subtitle)
    lines.append('')
    lines.extend(_step_md(step, depth=0) for step in scenario.steps)
    if scenario.parameters is not None:
        lines.append('')
        lines.append(_param_table_md(scenario.parameters))
    return '\n'.join(lines)


def _source_md(scenario: Scenario) -> str:
    """The subtitle source pointer: `relpath:line::test_name`.

    The parametrize suffix (`[case-id]`) is dropped — the grouped scenario
    narrates every case, so the representative case id is noise. When a
    SourceLocation is present its `line` is spliced in after the file path
    (a terminal-clickable `file:line`); the test-name segment comes from the
    node id.
    """
    node = node_base(scenario.id)
    if scenario.source is None:
        return node
    _path, path_sep, name = node.partition('::')
    located = f'{scenario.source.relpath}:{scenario.source.line}'
    return f'{located}{path_sep}{name}'


def _param_table_md(table: ParameterTable) -> str:
    """The case table, plus a fenced block per attachment cell too big to inline.

    Long cells follow the split `_attachment_lines` uses: short single-line
    content sits inline in backticks; multiline or backtick-bearing content
    shows the label in the cell and renders fenced below the table, keyed by
    the case's parametrize values.
    """
    header = '| ' + ' | '.join([*(_cell(c.name) for c in table.columns), '']) + '|'
    separator = '|' + '---|' * (len(table.columns) + 1)
    rows: list[str] = []
    blocks: list[str] = []
    for case in table.cases:
        cells = [
            _case_cell(column, value)
            for column, value in zip(table.columns, case.values, strict=True)
        ]
        rows.append(
            '| ' + ' | '.join([*cells, _STATUS_GLYPH.get(case.status, '✗')]) + ' |'
        )
        blocks.extend(_case_attachment_blocks(table, case))
        blocks.extend(_case_divergence_note(table, case))
    return '\n'.join([header, separator, *rows, *blocks])


def _case_divergence_note(table: ParameterTable, case: ParameterCase) -> list[str]:
    """A line saying why a divergent case's generated cells are blank.

    Without it the blanks sit next to a ✓ and read as a recording failure; the
    case simply took a different path, so the grouped step tree — another
    case's — has no slot to fill them from.
    """
    if not case.divergent:
        return []
    return [
        '',
        f'- **{_case_key(table, case)}** — steps differ from the other cases, so '
        f'the grouped tree is not this one and its columns stay blank.',
    ]


def _case_cell(column: ParameterColumn, value: CellValue | None) -> str:
    """One table cell.

    A `param` cell renders its value verbatim — `None` there is a real
    parametrize value, and the HTML renderer prints it the same way. For a
    generated column `None` means the case has no value for it (skipped,
    failed, or structurally incomparable) and renders blank. The blank keys on
    the column kind, never on the value.

    A short single-line attachment sits inline in backticks; a longer one names
    its column here and is fenced below the table. The *column* name rather
    than the attachment label: two columns can share a label, and only the
    column name is disambiguated.
    """
    if column.kind == 'param':
        return _cell(value)
    if value is None:
        return ''
    if not isinstance(value, Attachment):
        return _cell(value)
    if _fits_inline(value.content):
        return f'`{_cell(value.content)}`'
    return _cell(column.name)


def _case_attachment_blocks(table: ParameterTable, case: ParameterCase) -> list[str]:
    """Fenced blocks for this case's attachment cells that did not fit inline,
    keyed by the case's parametrize values and headed by the column name.

    The column name, not the attachment label: two columns can share a label,
    which would head both blocks identically.
    """
    key = _case_key(table, case)
    lines: list[str] = []
    for column, value in zip(table.columns, case.values, strict=True):
        if not isinstance(value, Attachment) or _fits_inline(value.content):
            continue
        lines.append('')
        lines.append(f'- **{key}** — {_inline(column.name)}:')
        lines.extend(f'  {line}' for line in _fenced(value.content))
    return lines


def _case_key(table: ParameterTable, case: ParameterCase) -> str:
    """A case's parametrize values, joined — how a note below the table names
    the row it belongs to."""
    return ', '.join(
        _cell(value)
        for column, value in zip(table.columns, case.values, strict=True)
        if column.kind == 'param'
    )


def _fits_inline(content: str) -> bool:
    return not any(nl in content for nl in ('\r\n', '\n', '\r')) and '`' not in content


def _fenced(content: str) -> list[str]:
    """`content` wrapped in a fence long enough to survive its own backticks."""
    longest_run = max((len(run) for run in re.findall(r'`+', content)), default=0)
    fence = '`' * max(3, longest_run + 1)
    return [fence, *content.splitlines(), fence]


def _inline(text: str) -> str:
    """Keep *text* on a single Markdown line by folding newlines to ``<br>``.

    A raw newline in a heading, list bullet, or attachment label would break
    out of the block (the tail dedents into a stray paragraph); ``<br>`` renders
    the break in place without corrupting the surrounding structure.
    """
    for nl in ('\r\n', '\n', '\r'):
        text = text.replace(nl, '<br>')
    return text


def _cell(value: object) -> str:
    return _inline(str(value).replace('|', '\\|'))


def _step_md(step: Step, depth: int) -> str:
    indent = '  ' * depth
    bullet = f'{indent}- **{step.phase}** {_narration_md(step.narration)}'
    if step.status == 'failed':
        bullet += '  **← FAILED**'
    lines = [bullet]
    if step.error is not None:
        lines.extend(_error_lines(step.error, indent))
    for attachment in step.attachments:
        lines.extend(_attachment_lines(attachment, indent))
    lines.extend(_step_md(child, depth + 1) for child in step.children)
    return '\n'.join(lines)


def _attachment_lines(attachment: StepAttachment, indent: str) -> list[str]:
    label = _inline(attachment.label)
    if isinstance(attachment, AttachmentRef):
        # A promoted attachment carries no content — the payload is in the
        # column its badge points at.
        return [f'{indent}  - 📎 {label} — *see case table*']
    if _fits_inline(attachment.content):
        return [f'{indent}  - 📎 {label} — `{attachment.content}`']
    body_indent = f'{indent}    '
    return [
        f'{indent}  - 📎 {label}:',
        *(f'{body_indent}{line}' for line in _fenced(attachment.content)),
    ]


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
        return _inline(narration.text)
    return _inline(''.join(_part_md(part) for part in narration.parts))


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
