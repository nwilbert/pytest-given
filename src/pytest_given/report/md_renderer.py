"""Rendering the Markdown report: the deterministic, diffable view of a run."""

import re
from collections import Counter
from pathlib import Path

from ..markdown import LINE_BREAK
from ..model import (
    Attachment,
    AttachmentRef,
    CellValue,
    ErrorInfo,
    Narration,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
    StepAttachment,
    case_id,
    node_base,
    plural,
)
from .markdown_writer import code_span_markdown, literal_markdown, narration_markdown
from .text import STATUS_GLYPH, STATUS_LABEL


def render_md(report: ReportData, *, with_lines: bool = True) -> str:
    """Render the report model to an agent-facing Markdown string."""
    name = report.metadata.title or report.metadata.project
    blocks = [_heading(1, f'pytest-given — {_text(name)}')]
    blocks.extend(_scenario_md(scenario, with_lines) for scenario in report.scenarios)
    return '\n\n'.join(blocks) + '\n'


def _scenario_md(scenario: Scenario, with_lines: bool) -> str:
    glyph = STATUS_GLYPH[scenario.status]
    suffix = ''
    # A grouped scenario counts its cases instead: an all-skipped group has
    # nothing else to say, but one xfailed row is what its status column shows.
    if scenario.status == 'skipped' or (
        scenario.status == 'xfailed' and scenario.parameters is None
    ):
        suffix = f' · {STATUS_LABEL[scenario.status]}'
    elif scenario.parameters is not None:
        suffix = f' · {plural(len(scenario.parameters.cases), "case")}'
    lines = [_heading(2, f'{glyph} {_narration_md(scenario.narration)}{suffix}')]
    subtitle = f'`{_source_md(scenario, with_lines)}`'
    if scenario.tags:
        subtitle += ' · ' + ', '.join(_text(tag) for tag in scenario.tags)
    if scenario.skip_reason:
        subtitle += f' — reason: {_text(scenario.skip_reason)}'
    if scenario.xfail_reason:
        subtitle += f' — expected to fail: {_text(scenario.xfail_reason)}'
    lines.append(subtitle)
    lines.append('')
    lines.extend(_step_md(step, depth=0) for step in scenario.steps)
    if scenario.parameters is not None:
        lines.append('')
        lines.append(_param_table_md(scenario.parameters))
    # After the steps and the table, where the HTML renderer puts it. A
    # grouped scenario never carries one — its cases do, and `_param_table_md`
    # renders those below the table instead.
    if scenario.error is not None:
        lines.append('')
        lines.extend(_error_lines(scenario.error))
    return '\n'.join(lines)


def _source_md(scenario: Scenario, with_lines: bool) -> str:
    """The subtitle source pointer: `relpath:line::test_name`, or the node ID
    when there is no source or no line is wanted.

    The parametrize suffix (`[case-id]`) is dropped — the grouped scenario
    narrates every case, so the representative case ID is noise.
    """
    node = node_base(scenario.id)
    if scenario.source is None or not with_lines:
        return node
    _path, path_sep, name = node.partition('::')
    located = f'{scenario.source.relpath}:{scenario.source.line}'
    return f'{located}{path_sep}{name}'


def _param_table_md(table: ParameterTable) -> str:
    """The parameter table, plus a fenced block per attachment cell too big to inline.

    Long cells follow the split `_attachment_lines` uses: short single-line
    content sits inline in backticks; multiline or backtick-bearing content
    shows the label in the cell and renders fenced below the table, keyed by
    the row (see `_case_key`).

    The leading case ID column only appears when some case ID is custom,
    and the trailing status column only when the cases differ in status: a
    column of one glyph says nothing the heading's glyph hasn't.
    """
    show_status = table.has_mixed_statuses
    names = [_cell(column.name) for column in table.columns]
    if table.has_custom_ids:
        names.insert(0, 'case ID')
    header = '| ' + ' | '.join(names) + ' |' + ' |' * show_status
    separator = '|' + '---|' * (len(names) + show_status)
    rows: list[str] = []
    keys: list[str] = []
    for row, case in enumerate(table.cases, start=1):
        # A generated id too long to inline only repeats a value the row shows.
        pytest_id = case_id(case.id)
        if case.custom_id or len(pytest_id) <= _MAX_INLINE:
            pytest_id = _cell(pytest_id)
        else:
            pytest_id = ''
        cells = [pytest_id] if table.has_custom_ids else []
        cells.extend(_case_cell(column, value) for column, value in table.cells(case))
        if show_status:
            cells.append(STATUS_GLYPH[case.status])
        rows.append('| ' + ' | '.join(cells) + ' |')
        # The id the row leads with names it best, when it has one.
        keys.append((table.has_custom_ids and pytest_id) or _case_key(table, case, row))
    # A key two notes share points at neither row, so each adds its own.
    counts = Counter(keys)
    blocks: list[str] = []
    for row, (case, key) in enumerate(zip(table.cases, keys, strict=True), start=1):
        if counts[key] > 1:
            key = f'{key} (row {row})'
        blocks.extend(_case_error_block(key, case))
        blocks.extend(_case_attachment_blocks(table, case, key))
    return '\n'.join([header, separator, *rows, *blocks])


def _case_error_block(key: str, case: ParameterCase) -> list[str]:
    """A failing or xfailed case's error, keyed by its row.

    Below the table rather than in the row: Markdown cannot nest a block inside
    a table cell. A grouped scenario carries no error of its own, so without
    this a failed case shows a ✗ and no reason anywhere.
    """
    if case.error is None:
        return []
    return [
        '',
        f'- **{key}** — {STATUS_LABEL[case.status]}:',
        *_error_lines(case.error, '  '),
    ]


def _case_cell(column: ParameterColumn, value: CellValue) -> str:
    """One table cell.

    A `param` cell renders its value verbatim — `None` there is a real
    parametrize value, and the HTML renderer prints it the same way. For a
    generated column `None` means the case has no value for it (skipped,
    failed, or structurally incomparable) and renders blank. The blank keys on
    the column kind, never on the value.

    A short single-line attachment sits inline in backticks; a longer one names
    its column here and is fenced below the table.
    """
    if column.kind == 'param':
        return _cell(value)
    if value is None:
        return ''
    if not isinstance(value, Attachment):
        return _cell(value)
    if _fits_inline(value.content):
        return code_span_markdown(value.content, in_table_row=True)
    return _cell(column.name)


def _case_attachment_blocks(
    table: ParameterTable, case: ParameterCase, key: str
) -> list[str]:
    """Fenced blocks for this case's attachment cells that did not fit inline,
    keyed by the case's row and headed by the column name.

    The column name, not the attachment label: two columns can share a label,
    which would head both blocks identically.
    """
    lines: list[str] = []
    for column, value in table.cells(case):
        if not isinstance(value, Attachment) or _fits_inline(value.content):
            continue
        lines.append('')
        lines.append(f'- **{key}** — {_text(column.name)}:')
        lines.extend(f'  {line}' for line in _fenced(value.content))
    return lines


def _case_key(table: ParameterTable, case: ParameterCase, row: int) -> str:
    """A case's parametrize values, joined — how a note below the table names
    the row it belongs to when no id does.

    A value too long to inline is left out: the key points into the table, and
    a document in it would repeat the table instead. With none left, the row
    number names the row.
    """
    key = ', '.join(
        _cell(value)
        for column, value in table.cells(case)
        if column.kind == 'param' and _fits_inline(str(value))
    )
    return key or f'row {row}'


_MAX_INLINE = 72


def _fits_inline(content: str) -> bool:
    """Whether `content` can sit inside a table cell or an attachment bullet.

    A newline or a backtick would break the surrounding structure outright.
    Length breaks it just as effectively without being malformed: a
    300-character cell pushes every other column of the parameter table off the
    terminal.
    """
    return (
        not any(nl in content for nl in ('\r\n', '\n', '\r'))
        and '`' not in content
        and len(content) <= _MAX_INLINE
    )


def _fenced(content: str) -> list[str]:
    """`content` wrapped in a fence long enough to survive its own backticks."""
    longest_run = max((len(run) for run in re.findall(r'`+', content)), default=0)
    fence = '`' * max(3, longest_run + 1)
    return [fence, *content.splitlines(), fence]


def _text(text: str) -> str:
    """*text* shown literally, on a single Markdown line: newlines fold to
    ``<br>`` after the escaping, which would otherwise show it as text.

    A raw newline in a bullet, table cell or attachment label would break out
    of the block (the tail dedents into a stray paragraph); ``<br>`` renders
    the break in place without corrupting the surrounding structure.
    """
    return LINE_BREAK.sub('<br>', literal_markdown(text))


def _cell(value: object) -> str:
    return _text(str(value))


def _step_md(step: Step, depth: int) -> str:
    indent = '  ' * depth
    lines = [f'{indent}- **{step.phase}** {_narration_md(step.narration)}']
    for attachment in step.attachments:
        lines.extend(_attachment_lines(attachment, indent))
    lines.extend(_step_md(child, depth + 1) for child in step.children)
    return '\n'.join(lines)


def _attachment_lines(attachment: StepAttachment, indent: str) -> list[str]:
    label = _text(attachment.label)
    if isinstance(attachment, AttachmentRef):
        # A promoted attachment carries no content — the payload is in the
        # column its badge points at.
        return [f'{indent}  - 📎 {label} — *see parameter table*']
    if _fits_inline(attachment.content):
        return [f'{indent}  - 📎 {label} — {code_span_markdown(attachment.content)}']
    body_indent = f'{indent}    '
    return [
        f'{indent}  - 📎 {label}:',
        *(f'{body_indent}{line}' for line in _fenced(attachment.content)),
    ]


def _error_lines(error: ErrorInfo, prefix: str = '') -> list[str]:
    """A failure as blockquote lines: its first message line, then the
    innermost non-internal frame. `prefix` is the full leading indent, so a
    case's block can sit under a table bullet and a scenario's at the margin.
    """
    lines = []
    first = error.message.splitlines()[0] if error.message else ''
    if first:
        lines.append(f'{prefix}> {_quoted(first)}')
    for frame in reversed(error.frames):
        if not frame.is_internal:
            where = f'{Path(frame.path).name}:{frame.lineno} in {frame.func}'
            lines.append(f'{prefix}> {_quoted(where)}')
            break
    return lines


# What opens a block at the start of a line: a heading, a list item — the
# group holding an ordered one's delimiter — a `-` thematic break or a nested
# quote. `literal_markdown` already escapes a `*` or `_` one.
_BLOCK_MARKER = re.compile(
    r'(?:#{1,6}|[-+])(?=\s|$)|-(?=[ \t-]*$)|>|[0-9]{1,9}(?=([.)])(?:\s|$))'
)


def _quoted(text: str) -> str:
    """A line of a quote, shown literally: a block marker at its start is
    escaped too, and its indent, which would open a code block, dropped."""
    line = literal_markdown(text.lstrip())
    marker = _BLOCK_MARKER.match(line)
    if marker is None:
        return line
    if marker.group(1) is not None:
        return f'{line[: marker.end()]}\\{line[marker.end() :]}'
    return f'\\{line}'


def _narration_md(narration: Narration) -> str:
    return narration_markdown(narration, term_ref=lambda display: f'«{display}»')


# A heading's trailing run of `#` after a space, which would close it unseen.
_CLOSING_SEQUENCE = re.compile(r'(?<=[ \t])#+[ \t]*$')


def _heading(level: int, text: str) -> str:
    return f'{"#" * level} {_CLOSING_SEQUENCE.sub(r"\\\g<0>", text)}'
