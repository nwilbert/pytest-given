import html

import pytest
from markdown_it import MarkdownIt

from pytest_given import attach, given, scenario, then, when
from pytest_given.model import (
    Attachment,
    AttachmentRef,
    ErrorInfo,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    ReportData,
    Scenario,
    SourceLocation,
    Status,
    Step,
    TracebackFrame,
    report_to_dict,
)
from pytest_given.report.md_renderer import render_md
from tests.ubiquitous_language import pg


def _report(
    *scenarios: Scenario, project: str = 'proj', title: str | None = None
) -> ReportData:
    return ReportData(
        metadata=Metadata(
            project=project,
            timestamp='t',
            pytest_version='9',
            plugin_version='0.1',
            title=title,
        ),
        scenarios=list(scenarios),
    )


def test_header_names_the_project() -> None:
    md = render_md(_report(project='hotel'))
    assert md.startswith('# pytest-given — hotel')


@scenario(
    t'A passed {pg["Scenario"].l} renders as a checked heading with '
    t'{pg["Step"].l} bullets',
)
def test_passed_scenario_heading_and_steps() -> None:
    with given(
        t'a {pg["Report"].l} holding a passed {pg["Scenario"].l} with three steps'
    ):
        scn = Scenario(
            id='tests/t.py::test_buy',
            narration=Narration(text='Buy coffee'),
            module='tests/t.py',
            tags=['billing', 'happy-path'],
            status='passed',
            steps=[
                Step(phase='given', narration=Narration(text='a machine')),
                Step(phase='when', narration=Narration(text='I insert $2')),
                Step(phase='then', narration=Narration(text='I get a coffee')),
            ],
        )
        rd = _report(scn)
    with when(t'the Markdown {pg["Report"].l} is rendered'):
        md = render_md(rd)
    with then(t'the heading is checked and each {pg["Step"].l} is a phase bullet'):
        attach('Rendered Markdown', md)
        assert '## ✓ Buy coffee' in md
        assert '`tests/t.py::test_buy` · billing, happy-path' in md
        assert '- **given** a machine' in md
        assert '- **when** I insert \\$2' in md
        assert '- **then** I get a coffee' in md


def test_a_newline_in_a_title_or_step_reads_as_a_space() -> None:
    scn = Scenario(
        id='tests/t.py::test_x',
        narration=Narration(text='line one\nline two'),
        module='tests/t.py',
        status='passed',
        steps=[
            Step(
                phase='when',
                narration=Narration(
                    text='act one\nact two',
                    parts=(
                        NarrationLiteral(value='act one\n'),
                        NarrationValue(rendered='act\r\ntwo', expression='x'),
                    ),
                ),
            )
        ],
    )
    md = render_md(_report(scn))
    assert '## ✓ line one line two' in md
    assert '- **when** act one act two' in md


def test_newline_in_attachment_label_stays_inline() -> None:
    scn = Scenario(
        id='tests/t.py::test_x',
        narration=Narration(text='X'),
        module='tests/t.py',
        status='passed',
        steps=[
            Step(
                phase='given',
                narration=Narration(text='a thing'),
                attachments=[Attachment(label='multi\nline', content='v')],
            )
        ],
    )
    md = render_md(_report(scn))
    assert '📎 multi<br>line — `v`' in md


def test_no_tags_omits_the_separator() -> None:
    scn = Scenario(
        id='tests/t.py::test_x',
        narration=Narration(text='X'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='act'))],
    )
    md = render_md(_report(scn))
    assert '`tests/t.py::test_x`\n' in md
    assert '·' not in md.split('## ✓ X')[1].split('\n')[1]


@pytest.mark.parametrize(
    ('with_lines', 'anchor'),
    [(True, 'tests/t.py:42::test_slug'), (False, 'tests/t.py::test_slug')],
)
def test_source_drops_parametrize_suffix_and_splices_line_on_request(
    with_lines: bool, anchor: str
) -> None:
    scn = Scenario(
        id='tests/t.py::test_slug[Guest-guest]',
        narration=Narration(text='Slug'),
        module='tests/t.py',
        source=SourceLocation(relpath='tests/t.py', line=42),
        steps=[Step(phase='when', narration=Narration(text='act'))],
    )
    md = render_md(_report(scn), with_lines=with_lines)
    assert f'`{anchor}`\n' in md
    assert 'Guest-guest' not in md


@pytest.mark.parametrize('with_lines', [True, False])
def test_source_without_location_still_drops_parametrize_suffix(
    with_lines: bool,
) -> None:
    scn = Scenario(
        id='tests/t.py::test_slug[case]',
        narration=Narration(text='Slug'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='act'))],
    )
    md = render_md(_report(scn), with_lines=with_lines)
    assert '`tests/t.py::test_slug`\n' in md


@scenario(
    t'Nested {pg["Step"].l.s} indent under their parent',
)
def test_nested_steps_indent() -> None:
    with given(t'a {pg["Scenario"].l} whose when {pg["Step"].l} has a nested child'):
        scn = Scenario(
            id='tests/t.py::test_nest',
            narration=Narration(text='Nest'),
            module='tests/t.py',
            steps=[
                Step(
                    phase='when',
                    narration=Narration(text='outer'),
                    children=[Step(phase='when', narration=Narration(text='inner'))],
                )
            ],
        )
    with when(t'the Markdown {pg["Report"].l} is rendered'):
        md = render_md(_report(scn))
    with then('the child bullet indents under its parent'):
        attach('Rendered Markdown', md)
        assert '- **when** outer' in md
        assert '  - **when** inner' in md


@scenario(
    t'Structured {pg["Narration"].l} renders {pg["Term"].l.s}, values and placeholders',
)
def test_narration_parts_resolve_terms_and_values() -> None:
    with given(
        t'a {pg["Step"].l} whose {pg["Narration"].l} carries a '
        t'{pg["Term ref"].l}, '
        t'a value and a placeholder'
    ):
        scn = Scenario(
            id='tests/t.py::test_parts',
            narration=Narration(text='ignored'),
            module='tests/t.py',
            steps=[
                Step(
                    phase='when',
                    narration=Narration(
                        text='fallback',
                        parts=(
                            NarrationLiteral(value='a '),
                            NarrationTermRef(term_id='guest', display='Guest'),
                            NarrationValue(rendered='42', expression='n'),
                            NarrationPlaceholder(name='amount', column_id='amount'),
                        ),
                    ),
                )
            ],
        )
    with when(t'the Markdown {pg["Report"].l} is rendered'):
        md = render_md(_report(scn))
    with then(
        t'the {pg["Term ref"].l} renders in guillemets, the value verbatim '
        t'and the placeholder in braces'
    ):
        attach('Rendered Markdown', md)
        assert '- **when** a «Guest»42{amount}' in md


def test_attachment_renders_under_step() -> None:
    scn = Scenario(
        id='tests/t.py::test_att',
        narration=Narration(text='Att'),
        module='tests/t.py',
        steps=[
            Step(
                phase='then',
                narration=Narration(text='result'),
                attachments=[Attachment(label='State', content='{"n": 9}')],
            )
        ],
    )
    md = render_md(_report(scn))
    assert '  - 📎 State — `{"n": 9}`' in md


def test_single_case_heading_says_one_case_not_one_cases() -> None:
    """A one-value parametrize is still grouped, so the count reaches the
    heading and has to agree with its noun."""
    scn = Scenario(
        id='tests/t.py::test_price',
        narration=Narration(text='Pricing'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='insert'))],
        parameters=ParameterTable(
            columns=[ParameterColumn(id='euros', name='euros', kind='param')],
            cases=[
                ParameterCase(id=NodeId('t.py::test_x[1]'), values=[1], status='passed')
            ],
        ),
    )
    assert '## \u2713 Pricing \u00b7 1 case\n' in render_md(_report(scn))


@scenario(
    t'A {pg["Parametrized scenario"].l} renders its {pg["Parameter table"].l}',
    tags=['parametrization'],
)
def test_parametrized_scenario_renders_table() -> None:
    with given(
        t'a {pg["Parametrized scenario"].l} with a two-{pg["Case"].l} '
        t'{pg["Parameter table"].l}'
    ):
        scn = Scenario(
            id='tests/t.py::test_price',
            narration=Narration(text='Pricing'),
            module='tests/t.py',
            steps=[Step(phase='when', narration=Narration(text='insert'))],
            parameters=ParameterTable(
                columns=[
                    ParameterColumn(id='euros', name='euros', kind='param'),
                    ParameterColumn(id='expect', name='expect', kind='param'),
                ],
                cases=[
                    ParameterCase(
                        id=NodeId('t.py::test_x[2]'), values=[1, False], status='passed'
                    ),
                    ParameterCase(
                        id=NodeId('t.py::test_x[3]'), values=[2, True], status='passed'
                    ),
                ],
            ),
        )
    with when(t'the Markdown {pg["Report"].l} is rendered'):
        md = render_md(_report(scn))
    with then(
        t'the heading counts the cases and the {pg["Parameter table"].l} lists each row'
    ):
        attach('Rendered Markdown', md)
        assert '## ✓ Pricing · 2 cases' in md
        assert '| euros | expect |' in md
        assert '| 1 | False |' in md
        assert '| 2 | True |' in md


@scenario(
    t'The {pg["Parameter table"].l} shows a status column only when its '
    t'cases differ in status',
    tags=['parametrization'],
)
@pytest.mark.parametrize(
    ('first_status', 'second_status', 'status_column'),
    [
        ('passed', 'passed', 'omitted'),
        ('skipped', 'skipped', 'omitted'),
        ('failed', 'failed', 'omitted'),
        ('passed', 'skipped', 'shown'),
        ('passed', 'failed', 'shown'),
    ],
)
def test_param_table_shows_status_column_only_when_case_statuses_differ(
    first_status: Status, second_status: Status, status_column: str
) -> None:
    with given(
        t'a {pg["Parameter table"].l} whose first {pg["Case"].l} is '
        t'{first_status} and whose second is {second_status}'
    ):
        table = ParameterTable(
            columns=[ParameterColumn(id='coin', name='coin', kind='param')],
            cases=[
                ParameterCase(
                    id=NodeId('t.py::test_x[4]'), values=['euro'], status=first_status
                ),
                ParameterCase(
                    id=NodeId('t.py::test_x[5]'), values=['token'], status=second_status
                ),
            ],
        )
    with when(t'the Markdown {pg["Report"].l} is rendered'):
        md = render_md(_report_with(table))
    with then(t'the status column is {status_column}'):
        attach('Rendered Markdown', md)
        header = next(line for line in md.splitlines() if line.startswith('| coin'))
        assert header == ('| coin | |' if status_column == 'shown' else '| coin |')


@scenario(
    t'A failed {pg["Scenario"].l} ends with a minimal error digest',
)
def test_failing_scenario_renders_a_minimal_error() -> None:
    with given(
        t'a failed {pg["Scenario"].l} carrying a two-line error and an internal frame'
    ):
        scn = Scenario(
            id='tests/t.py::test_sold_out',
            narration=Narration(text='Sold out'),
            module='tests/t.py',
            status='failed',
            steps=[
                Step(
                    phase='then',
                    narration=Narration(text='reports sold out'),
                )
            ],
            error=ErrorInfo(
                message='ValueError: not sold out\nassert 1 == 0',
                frames=[
                    TracebackFrame(
                        path='/x/_pytest/runner.py',
                        lineno=1,
                        func='run',
                        code='',
                        is_internal=True,
                    ),
                    TracebackFrame(
                        path='/x/tests/test_shop.py',
                        lineno=88,
                        func='test_sold_out',
                        code='buy(m)',
                        is_internal=False,
                    ),
                ],
            ),
        )
        rd = _report(scn)
        attach('Error record', report_to_dict(rd)['scenarios'][0]['error'])
    with when(t'the Markdown {pg["Report"].l} is rendered'):
        md = render_md(rd)
    with then('the heading is crossed and the error follows the steps'):
        attach('Rendered Markdown', md)
        assert '## ✗ Sold out' in md
        assert '- **then** reports sold out' in md
        assert md.index('reports sold out') < md.index('> ValueError')
    with then('only the first message line and the non-internal frame are quoted'):
        assert '> ValueError: not sold out' in md
        assert '> test_shop.py:88 in test_sold_out' in md
        assert 'assert 1 == 0' not in md
        assert '_pytest/runner.py' not in md


def test_single_line_attachment_renders_inline() -> None:
    scn = Scenario(
        id='tests/t.py::test_inline',
        narration=Narration(text='Inline'),
        module='tests/t.py',
        steps=[
            Step(
                phase='then',
                narration=Narration(text='result'),
                attachments=[Attachment(label='S', content='x=1')],
            )
        ],
    )
    md = render_md(_report(scn))
    assert '  - 📎 S — `x=1`' in md


@scenario(
    t'A multi-line {pg["Attachment"].l} renders as a fenced block',
)
def test_multiline_attachment_renders_fenced_block() -> None:
    with given(t'a {pg["Step"].l} carrying a multi-line {pg["Attachment"].l}'):
        scn = Scenario(
            id='tests/t.py::test_multiline',
            narration=Narration(text='Multi'),
            module='tests/t.py',
            steps=[
                Step(
                    phase='then',
                    narration=Narration(text='result'),
                    attachments=[Attachment(label='Doc', content='line1\nline2')],
                )
            ],
        )
    with when(t'the Markdown {pg["Report"].l} is rendered'):
        md = render_md(_report(scn))
    with then(
        t'the {pg["Attachment"].l} content sits in an indented fence, not inline'
    ):
        attach('Rendered Markdown', md)
        assert '  - 📎 Doc:' in md
        assert '\n    ```\n' in md
        assert '\n    line1\n' in md
        assert '\n    line2\n' in md
        assert '— `line1' not in md


def test_carriage_return_attachment_renders_fenced_block() -> None:
    scn = Scenario(
        id='tests/t.py::test_cr',
        narration=Narration(text='CR'),
        module='tests/t.py',
        steps=[
            Step(
                phase='then',
                narration=Narration(text='result'),
                attachments=[Attachment(label='Doc', content='line1\rline2')],
            )
        ],
    )
    md = render_md(_report(scn))
    assert '  - 📎 Doc:' in md
    assert '\n    ```\n' in md
    assert '\n    line1\n' in md
    assert '\n    line2\n' in md
    assert '— `line1' not in md
    assert '\r' not in md


def test_attachment_with_triple_backtick_uses_longer_fence() -> None:
    scn = Scenario(
        id='tests/t.py::test_backtick',
        narration=Narration(text='Backtick'),
        module='tests/t.py',
        steps=[
            Step(
                phase='then',
                narration=Narration(text='result'),
                attachments=[Attachment(label='Code', content='```python\nx = 1\n```')],
            )
        ],
    )
    md = render_md(_report(scn))
    assert '````' in md
    assert '\n    ````\n' in md


def test_failing_case_renders_its_error_below_the_table() -> None:
    """A grouped scenario carries no error of its own — every failure is on a
    case. Without a per-case block a failed row shows a ✗ and no reason
    anywhere in the Markdown report."""
    scn = Scenario(
        id='tests/t.py::test_price',
        narration=Narration(text='Pricing'),
        module='tests/t.py',
        status='failed',
        steps=[Step(phase='when', narration=Narration(text='insert'))],
        parameters=ParameterTable(
            columns=[ParameterColumn(id='coin', name='coin', kind='param')],
            cases=[
                ParameterCase(
                    id=NodeId('t.py::test_x[6]'), values=['euro'], status='passed'
                ),
                ParameterCase(
                    id=NodeId('t.py::test_x[7]'),
                    values=['token'],
                    status='failed',
                    error=ErrorInfo(
                        message='assert 0 == 1',
                        frames=[
                            TracebackFrame(
                                path='/x/tests/test_shop.py',
                                lineno=12,
                                func='test_price',
                                code='assert 0 == 1',
                                is_internal=False,
                            )
                        ],
                    ),
                ),
            ],
        ),
    )
    md = render_md(_report(scn))
    assert '| token | ✗ |' in md
    assert '- **token** — failed:' in md
    assert '  > assert 0 == 1' in md
    assert '  > test_shop.py:12 in test_price' in md
    # Below the table, never inside it.
    assert md.index('| token | ✗ |') < md.index('- **token** — failed:')


def test_param_table_escapes_pipe_in_value() -> None:
    scn = Scenario(
        id='tests/t.py::test_pipe',
        narration=Narration(text='Pipe'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='act'))],
        parameters=ParameterTable(
            columns=[ParameterColumn(id='label', name='label', kind='param')],
            cases=[
                ParameterCase(
                    id=NodeId('t.py::test_x[8]'), values=['a|b'], status='passed'
                )
            ],
        ),
    )
    md = render_md(_report(scn))
    row = next(line for line in md.splitlines() if line.startswith('| a'))
    assert row == '| a\\|b |'


def test_param_table_escapes_newline_in_value() -> None:
    scn = Scenario(
        id='tests/t.py::test_nl',
        narration=Narration(text='NL'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='act'))],
        parameters=ParameterTable(
            columns=[ParameterColumn(id='label', name='label', kind='param')],
            cases=[
                ParameterCase(
                    id=NodeId('t.py::test_x[9]'), values=['a\nb'], status='passed'
                )
            ],
        ),
    )
    md = render_md(_report(scn))
    assert '| a<br>b |' in md
    assert 'a\nb' not in md


def test_param_table_renders_none_value_as_text_not_blank() -> None:
    """A `None` parametrize value is a legitimate value on a `param` column
    (unlike a `derived`/`attachment` column, where `None` means "no value for
    this case"), so it must render, not blank out. Regression guard for a
    drift where the HTML renderer briefly blanked `None` cells while this
    renderer kept printing the literal text."""
    scn = Scenario(
        id='tests/t.py::test_none',
        narration=Narration(text='None param'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='act'))],
        parameters=ParameterTable(
            columns=[ParameterColumn(id='label', name='label', kind='param')],
            cases=[
                ParameterCase(
                    id=NodeId('t.py::test_x[10]'), values=[None], status='passed'
                )
            ],
        ),
    )
    md = render_md(_report(scn))
    assert '| None |' in md


@scenario(
    'A skipped scenario shows its skip reason',
)
def test_skipped_scenario_shows_reason() -> None:
    with given(t'a skipped {pg["Scenario"].l} with a reason'):
        scn = Scenario(
            id='tests/t.py::test_skip',
            narration=Narration(text='Later'),
            module='tests/t.py',
            status='skipped',
            skip_reason='needs fixture data',
            steps=[Step(phase='when', narration=Narration(text='act'))],
        )
    with when(t'the Markdown {pg["Report"].l} is rendered'):
        md = render_md(_report(scn))
    with then('the heading is marked skipped and the reason follows the node ID'):
        attach('Rendered Markdown', md)
        assert '## ○ Later · skipped' in md
        assert '`tests/t.py::test_skip` — reason: needs fixture data' in md


def test_an_xfailed_scenario_heading_and_subtitle() -> None:
    scn = Scenario(
        id='tests/t.py::test_planned',
        narration=Narration(text='Planned'),
        module='tests/t.py',
        status='xfailed',
        xfail_reason='not implemented yet',
    )
    md = render_md(_report(scn))
    assert '## ⊗ Planned · expected failure' in md
    assert '`tests/t.py::test_planned` — expected to fail: not implemented yet' in md


def test_a_grouped_xfailed_scenario_keeps_its_case_count_and_labels_the_case() -> None:
    scn = Scenario(
        id='tests/t.py::test_price',
        narration=Narration(text='Pricing'),
        module='tests/t.py',
        status='xfailed',
        steps=[Step(phase='when', narration=Narration(text='insert'))],
        parameters=ParameterTable(
            columns=[ParameterColumn(id='coin', name='coin', kind='param')],
            cases=[
                ParameterCase(
                    id=NodeId('t.py::test_x[11]'), values=['euro'], status='passed'
                ),
                ParameterCase(
                    id=NodeId('t.py::test_x[12]'),
                    values=['token'],
                    status='xfailed',
                    error=ErrorInfo(message='tokens are planned'),
                ),
            ],
        ),
    )
    md = render_md(_report(scn))
    assert '## ⊗ Pricing · 2 cases' in md
    assert '| token | ⊗ |' in md
    assert '- **token** — expected failure:' in md
    assert '— failed:' not in md


def _attachment_table(*, short: str | None, long: str | None) -> ParameterTable:
    """A one-parameter table with one attachment cell.

    The column's name and the attachment's label are deliberately *different*:
    with both called `state`, a `'| state |'` needle is satisfied by the header
    row, and the cell's label fallback ships unpinned.
    """
    content = short if short is not None else long
    assert content is not None
    return ParameterTable(
        columns=[
            ParameterColumn(id='cup_size', name='cup_size', kind='param'),
            ParameterColumn(id='attachment:0', name='machine state', kind='attachment'),
        ],
        cases=[
            ParameterCase(
                id=NodeId('t.py::test_x[13]'),
                values=[350, Attachment(label='state', content=content)],
                status='passed',
            ),
        ],
    )


def _report_with(table: ParameterTable) -> ReportData:
    scn = Scenario(
        id='tests/t.py::test_att',
        narration=Narration(text='Att'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='act'))],
        parameters=table,
    )
    return _report(scn)


def _report_with_step(step: Step) -> ReportData:
    scn = Scenario(
        id='tests/t.py::test_att',
        narration=Narration(text='Att'),
        module='tests/t.py',
        steps=[step],
    )
    return _report(scn)


def test_a_short_attachment_cell_sits_inline_in_backticks() -> None:
    md = render_md(_report_with(_attachment_table(short='ok', long=None)))
    assert '| `ok` |' in md
    # …and is not *also* fenced below the table: inline and fenced are
    # alternatives, not both.
    assert '— state:' not in md


def test_a_pipe_in_an_inline_attachment_cell_is_escaped() -> None:
    """An inline attachment cell is the one cell path that interpolates raw
    payload text into a table row, so an unescaped `|` in it would split the
    row into a new column and derail every cell after it."""
    md = render_md(_report_with(_attachment_table(short='ok|fine', long=None)))
    assert '| 350 | `ok\\|fine` |' in md


def test_a_multiline_attachment_cell_shows_the_column_name_and_fences_below() -> None:
    """Cell and block both name the *column*, not the attachment label: two
    columns can share a label, and only the column name is disambiguated."""
    md = render_md(
        _report_with(_attachment_table(short=None, long='{"ml": 350,\n "full": true}'))
    )
    assert '| 350 | machine state |' in md
    assert '{"ml": 350,' in md
    # The fenced block belongs *after* the table, separated from it by a blank
    # line: emitted before the rows it leaves a header-only table followed by
    # loose text, and without the blank line a GFM parser keeps the block
    # header inside the table.
    assert '| 350 | machine state |\n\n- **350** — machine state:\n' in md


def test_a_block_key_leaves_out_a_param_value_too_long_to_inline() -> None:
    """The key names the row in a bullet; a multiline value there turns it into
    a `<br>`-strung wall that repeats the table instead of pointing into it."""
    table = ParameterTable(
        columns=[
            ParameterColumn(id='problem', name='problem', kind='param'),
            ParameterColumn(id='doc', name='doc', kind='param'),
            ParameterColumn(id='attachment:0', name='file', kind='attachment'),
        ],
        cases=[
            ParameterCase(
                id=NodeId('t.py::test_x[14]'),
                values=['no table', '# no table\n', Attachment('file', '# no\ntable')],
            ),
        ],
    )
    md = render_md(_report_with(table))
    assert '- **no table** — file:' in md


def test_a_block_key_falls_back_to_the_row_number() -> None:
    table = ParameterTable(
        columns=[
            ParameterColumn(id='doc', name='doc', kind='param'),
            ParameterColumn(id='attachment:0', name='file', kind='attachment'),
        ],
        cases=[
            ParameterCase(
                id=NodeId('t.py::test_x[15]'),
                values=['a\nb', Attachment('file', 'one\ntwo')],
            ),
            ParameterCase(
                id=NodeId('t.py::test_x[16]'),
                values=['c\nd', Attachment('file', 'three\nfour')],
            ),
        ],
    )
    md = render_md(_report_with(table))
    assert '- **row 2** — file:' in md


def test_a_backtick_bearing_attachment_cell_also_fences_below_the_table() -> None:
    """`_fits_inline` rejects backticks as well as newlines, and the cell path
    is a new caller of it — the multiline test above pins only one of its two
    conditions."""
    md = render_md(
        _report_with(_attachment_table(short=None, long='use `attach` here'))
    )
    assert '| 350 | machine state |' in md
    assert '- **350** — machine state:' in md


def test_two_columns_sharing_a_label_get_distinct_block_headers() -> None:
    """Two occurrences of one attachment label make two columns, whose names
    grouping has already disambiguated. Keying the fenced blocks on the label
    would emit two identical `- **350** — log:` headers, leaving the reader no
    way to tell which column each payload belongs to."""
    table = ParameterTable(
        columns=[
            ParameterColumn(id='cup_size', name='cup_size', kind='param'),
            ParameterColumn(id='attachment:0', name='log', kind='attachment'),
            ParameterColumn(id='attachment:1', name='log #2', kind='attachment'),
        ],
        cases=[
            ParameterCase(
                id=NodeId('t.py::test_x[17]'),
                values=[
                    350,
                    Attachment(label='log', content='first\nline'),
                    Attachment(label='log', content='second\nline'),
                ],
                status='passed',
            ),
        ],
    )
    md = render_md(_report_with(table))
    assert '| 350 | log | log #2 |' in md
    assert '- **350** — log:' in md
    assert '- **350** — log #2:' in md


def test_an_attachment_ref_renders_as_badge_and_label_alone() -> None:
    step = Step(
        phase='when',
        narration=Narration(text='the machine brews'),
        attachments=[
            AttachmentRef(
                label='machine state', content_type='json', column_id='attachment:0'
            )
        ],
    )
    md = render_md(_report_with_step(step))
    assert '- 📎 machine state — *see parameter table*' in md


def test_a_generated_column_with_no_value_for_a_case_renders_blank() -> None:
    """`None` in a generated column means the case has no value for it and
    renders blank — unlike a `param` column, where `None` is a real
    parametrize value and renders verbatim."""
    table = ParameterTable(
        columns=[
            ParameterColumn(id='cup_size', name='cup_size', kind='param'),
            ParameterColumn(id='attachment:0', name='state', kind='attachment'),
        ],
        cases=[
            ParameterCase(
                id=NodeId('t.py::test_x[18]'), values=[350, None], status='passed'
            )
        ],
    )
    md = render_md(_report_with(table))
    assert '| 350 |  |' in md


def test_a_derived_column_cell_renders_through_the_ordinary_cell_path() -> None:
    """A derived cell holds a plain value rather than an attachment, so it
    renders verbatim — no backticks, no fenced block below the table."""
    table = ParameterTable(
        columns=[
            ParameterColumn(id='cup_size', name='cup_size', kind='param'),
            ParameterColumn(id='derived:0', name='price', kind='derived'),
        ],
        cases=[
            ParameterCase(
                id=NodeId('t.py::test_x[19]'), values=[350, '3.5'], status='passed'
            )
        ],
    )
    md = render_md(_report_with(table))
    assert '| 350 | 3.5 |' in md


def test_a_long_single_line_attachment_cell_fences_below_the_table() -> None:
    """A payload with no newline still wrecks the table when it is long — a
    300-character cell pushes every other column off the terminal. Length is
    the same problem as a newline, so it takes the same route: the column name
    in the cell, the payload fenced below."""
    payload = '{"id": "ch_3PmZ", "amount": 250, ' + '"x": "y", ' * 30 + '"end": true}'
    md = render_md(_report_with(_attachment_table(short=payload, long=None)))
    assert '| 350 | machine state |' in md
    assert f'- **350** — machine state:\n  ```\n  {payload}\n  ```' in md


def test_an_attachment_cell_at_the_inline_limit_still_sits_inline() -> None:
    """The bound is on the payload itself, so a cell that fits stays inline —
    pinning the boundary keeps the check from drifting into 'fence everything'.
    """
    payload = 'x' * 72
    md = render_md(_report_with(_attachment_table(short=payload, long=None)))
    assert f'| 350 | `{payload}` |' in md


def test_header_prefers_the_title_over_the_project() -> None:
    md = render_md(_report(project='pytest-given', title='Coffee Shop Example'))
    assert md.startswith('# pytest-given — Coffee Shop Example')


def test_a_heading_ending_in_a_hash_keeps_it() -> None:
    scn = Scenario(
        id='tests/t.py::test_x',
        narration=Narration(text='fix issue ##'),
        module='tests/t.py',
    )
    rendered = MarkdownIt('commonmark').render(render_md(_report(scn, title='C #')))
    assert '<h1>pytest-given — C #</h1>' in rendered
    assert '<h2>✓ fix issue ##</h2>' in rendered


def test_a_title_and_a_step_keep_their_spans() -> None:
    scn = Scenario(
        id='tests/t.py::test_x',
        narration=Narration(text='Books a **suite** for 2 * 3'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='the `book` call'))],
    )
    md = render_md(_report(scn))
    assert '## ✓ Books a **suite** for 2 \\* 3' in md
    assert '- **when** the `book` call' in md


def test_a_value_holding_a_marker_is_literal() -> None:
    step = Step(
        phase='when',
        narration=Narration(
            text='split *',
            parts=(
                NarrationLiteral(value='split '),
                NarrationValue(rendered='*', expression='sep'),
            ),
        ),
    )
    md = render_md(_report_with_step(step))
    assert '- **when** split \\*' in md


def test_every_other_text_is_literal() -> None:
    scn = Scenario(
        id='tests/t.py::test_x',
        narration=Narration(text='X'),
        module='tests/t.py',
        tags=['a*b*', 'snake_case'],
        status='skipped',
        skip_reason='needs <b>data</b>',
        steps=[
            Step(
                phase='given',
                narration=Narration(text='a thing'),
                attachments=[Attachment(label='**raw**', content='*v*')],
            )
        ],
        error=ErrorInfo(
            message='AssertionError: assert *x* == [1]\nsecond line',
            frames=[
                TracebackFrame(
                    path='/x/tests/t.py',
                    lineno=3,
                    func='<module>',
                    code='',
                    is_internal=False,
                )
            ],
        ),
    )
    md = render_md(_report(scn, project='**proj**'))
    assert md.startswith('# pytest-given — \\*\\*proj\\*\\*')
    assert '· a\\*b\\*, snake_case — reason: needs \\<b>data\\</b>' in md
    assert '📎 \\*\\*raw\\*\\* — `*v*`' in md
    assert '> AssertionError: assert \\*x\\* == \\[1\\]' in md
    assert '> t.py:3 in \\<module>' in md


def test_a_parameter_table_writes_its_names_and_values_literally() -> None:
    scn = Scenario(
        id='tests/t.py::test_x',
        narration=Narration(text='X'),
        module='tests/t.py',
        status='failed',
        steps=[Step(phase='when', narration=Narration(text='act'))],
        parameters=ParameterTable(
            columns=[ParameterColumn(id='a_b', name='*a*', kind='param')],
            cases=[
                ParameterCase(
                    id=NodeId('t.py::test_x[1]'),
                    values=['**v**'],
                    status='failed',
                    error=ErrorInfo(message='boom', frames=[]),
                )
            ],
        ),
    )
    md = render_md(_report(scn))
    assert '| \\*a\\* |' in md
    assert '| \\*\\*v\\*\\* |' in md
    assert '- **\\*\\*v\\*\\*** — failed:' in md


@pytest.mark.parametrize(
    'message',
    [
        '# 1 failed',
        '###### deep',
        '- item',
        '+ item',
        '1. first',
        '2) second',
        '> nested',
        '---',
        '-- - -',
        '    indented',
        '#hashtag and -1 and 3.14',
    ],
)
def test_an_error_line_never_opens_a_block_inside_its_quote(message: str) -> None:
    scn = Scenario(
        id='tests/t.py::test_x',
        narration=Narration(text='X'),
        module='tests/t.py',
        status='failed',
        error=ErrorInfo(
            message=message,
            frames=[
                TracebackFrame(
                    path='/x/1. a.py',
                    lineno=3,
                    func='f',
                    code='',
                    is_internal=False,
                )
            ],
        ),
    )
    md = render_md(_report(scn))
    quote = '\n'.join(line for line in md.splitlines() if line.startswith('>'))
    rendered = MarkdownIt('commonmark').render(quote)
    text = html.escape(message.strip(), quote=False)
    assert rendered == f'<blockquote>\n<p>{text}\n1. a.py:3 in f</p>\n</blockquote>\n'


def _table_with_custom_ids(*cases: ParameterCase) -> ParameterTable:
    return ParameterTable(
        columns=[ParameterColumn(id='hours', name='hours', kind='param')],
        cases=list(cases),
    )


def _custom(
    node_id: str,
    value: int,
    *,
    status: Status = 'passed',
    error: ErrorInfo | None = None,
) -> ParameterCase:
    return ParameterCase(
        id=NodeId(node_id), values=[value], status=status, error=error, custom_id=True
    )


def test_a_table_with_custom_ids_leads_with_every_cases_id() -> None:
    """A generated id shows beside a custom one, as the terminal printed it."""
    table = _table_with_custom_ids(
        _custom('t.py::test_x[touching-edges]', 10),
        ParameterCase(id=NodeId('t.py::test_x[11]'), values=[11], status='failed'),
    )
    md = render_md(_report_with(table))
    assert '| case ID | hours | |\n|---|---|---|' in md
    assert '| touching-edges | 10 | ✓ |' in md
    assert '| 11 | 11 | ✗ |' in md


def test_a_hidden_id_leaves_its_cell_empty() -> None:
    table = _table_with_custom_ids(
        _custom('t.py::test_x[one]', 1),
        ParameterCase(id=NodeId('t.py::test_x'), values=[2]),
    )
    assert '|  | 2 |' in render_md(_report_with(table))


def test_notes_below_a_table_with_custom_ids_are_keyed_by_the_id() -> None:
    """An empty id falls back to the values."""
    table = _table_with_custom_ids(
        _custom(
            't.py::test_x[touching-edges]',
            10,
            status='failed',
            error=ErrorInfo(message='clash'),
        ),
        ParameterCase(
            id=NodeId('t.py::test_x'),
            values=[11],
            status='failed',
            error=ErrorInfo(message='clash'),
        ),
    )
    md = render_md(_report_with(table))
    assert '- **touching-edges** — failed:' in md
    assert '- **11** — failed:' in md


def test_an_id_is_written_literally() -> None:
    table = _table_with_custom_ids(_custom('t.py::test_x[a*b*c|d`e]', 1))
    assert r'| a\*b\*c\|d\`e | 1 |' in render_md(_report_with(table))


def test_a_long_generated_id_leaves_its_cell_and_notes_to_the_values() -> None:
    """An id that long repeats a value the row already shows."""
    long_id = 'x' * 73
    table = _table_with_custom_ids(
        _custom('t.py::test_x[edge]', 1),
        ParameterCase(
            id=NodeId(f't.py::test_x[{long_id}]'),
            values=[10],
            status='failed',
            error=ErrorInfo(message='clash'),
        ),
    )
    md = render_md(_report_with(table))
    assert long_id not in md
    assert '|  | 10 |' in md
    assert '- **10** — failed:' in md


def test_a_custom_id_shows_whole_however_long() -> None:
    long_id = 'touching-' * 10
    table = _table_with_custom_ids(
        _custom(
            f't.py::test_x[{long_id}]',
            10,
            status='failed',
            error=ErrorInfo(message='clash'),
        ),
    )
    md = render_md(_report_with(table))
    assert f'| {long_id} | 10 |' in md
    assert f'- **{long_id}** — failed:' in md


def test_notes_sharing_a_key_add_their_row() -> None:
    """A hidden id falls back to its values, which a custom ID may match."""
    error = ErrorInfo(message='clash')
    table = _table_with_custom_ids(
        _custom('t.py::test_x[11]', 5, status='failed', error=error),
        ParameterCase(
            id=NodeId('t.py::test_x'), values=[11], status='failed', error=error
        ),
        ParameterCase(
            id=NodeId('t.py::test_x[3]'), values=[3], status='failed', error=error
        ),
    )
    md = render_md(_report_with(table))
    assert '- **11 (row 1)** — failed:' in md
    assert '- **11 (row 2)** — failed:' in md
    assert '- **3** — failed:' in md
