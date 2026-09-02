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
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    ReportData,
    Scenario,
    SourceLocation,
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
    t'A passed {pg["Scenario"].low} renders as a checked heading with '
    t'{pg["Step"].low} bullets',
)
def test_passed_scenario_heading_and_steps() -> None:
    with given(t'a {pg["Report"]} holding a passed {pg["Scenario"]} with three steps'):
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
    with when(t'the Markdown {pg["Report"]} is rendered'):
        md = render_md(rd)
    with then(t'the heading is checked and each {pg["Step"]} is a phase bullet'):
        attach('Rendered Markdown', md)
        assert '## ✓ Buy coffee' in md
        assert '`tests/t.py::test_buy` · billing, happy-path' in md
        assert '- **given** a machine' in md
        assert '- **when** I insert $2' in md
        assert '- **then** I get a coffee' in md


def test_newlines_in_narration_do_not_break_heading_or_bullet() -> None:
    scn = Scenario(
        id='tests/t.py::test_x',
        narration=Narration(text='line one\nline two'),
        module='tests/t.py',
        status='passed',
        steps=[Step(phase='when', narration=Narration(text='act one\nact two'))],
    )
    md = render_md(_report(scn))
    # Every heading and bullet line stays a single physical line.
    assert '## ✓ line one<br>line two' in md
    assert '- **when** act one<br>act two' in md
    assert 'line two' not in md.replace('line one<br>line two', '')


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


def test_source_splices_line_and_drops_parametrize_suffix() -> None:
    scn = Scenario(
        id='tests/t.py::test_slug[Guest-guest]',
        narration=Narration(text='Slug'),
        module='tests/t.py',
        source=SourceLocation(relpath='tests/t.py', line=42),
        steps=[Step(phase='when', narration=Narration(text='act'))],
    )
    md = render_md(_report(scn))
    assert '`tests/t.py:42::test_slug`\n' in md
    assert 'Guest-guest' not in md


def test_source_without_location_still_drops_parametrize_suffix() -> None:
    scn = Scenario(
        id='tests/t.py::test_slug[case]',
        narration=Narration(text='Slug'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='act'))],
    )
    md = render_md(_report(scn))
    assert '`tests/t.py::test_slug`\n' in md


@scenario(
    t'Nested {pg["Step"]("steps")} indent under their parent',
)
def test_nested_steps_indent() -> None:
    with given(t'a {pg["Scenario"]} whose when {pg["Step"]} has a nested child'):
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
    with when(t'the Markdown {pg["Report"]} is rendered'):
        md = render_md(_report(scn))
    with then('the child bullet indents under its parent'):
        attach('Rendered Markdown', md)
        assert '- **when** outer' in md
        assert '  - **when** inner' in md


@scenario(
    t'Structured {pg["Narration"].low} renders {pg["Term"]("terms")}, '
    t'values and placeholders',
)
def test_narration_parts_resolve_terms_and_values() -> None:
    with given(
        t'a {pg["Step"]} whose {pg["Narration"]} carries a {pg["Term ref"]}, '
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
    with when(t'the Markdown {pg["Report"]} is rendered'):
        md = render_md(_report(scn))
    with then(
        t'the {pg["Term ref"]} renders in guillemets, the value verbatim '
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


@scenario(
    t'A {pg["Parametrized scenario"].low} renders its {pg["Parameter table"].low}',
    tags=['parametrization'],
)
def test_parametrized_scenario_renders_table() -> None:
    with given(
        t'a {pg["Parametrized scenario"]} with a two-{pg["Case"]} '
        t'{pg["Parameter table"]}'
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
                    ParameterCase(values=[1, False], status='passed'),
                    ParameterCase(values=[2, True], status='passed'),
                ],
            ),
        )
    with when(t'the Markdown {pg["Report"]} is rendered'):
        md = render_md(_report(scn))
    with then(
        t'the heading counts the cases and the {pg["Parameter table"]} lists each row'
    ):
        attach('Rendered Markdown', md)
        assert '## ✓ Pricing · 2 cases' in md
        assert '| euros | expect | |' in md
        assert '| 1 | False | ✓ |' in md
        assert '| 2 | True | ✓ |' in md


@scenario(
    t'A failing {pg["Step"].low} is marked with a minimal error digest',
)
def test_failing_scenario_renders_a_minimal_error() -> None:
    with given(
        t'a failed {pg["Scenario"]} carrying a two-line error and an internal frame'
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
    with when(t'the Markdown {pg["Report"]} is rendered'):
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
    t'A multi-line {pg["Attachment"].low} renders as a fenced block',
)
def test_multiline_attachment_renders_fenced_block() -> None:
    with given(t'a {pg["Step"]} carrying a multi-line {pg["Attachment"]}'):
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
    with when(t'the Markdown {pg["Report"]} is rendered'):
        md = render_md(_report(scn))
    with then(t'the {pg["Attachment"]} content sits in an indented fence, not inline'):
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
                ParameterCase(values=['euro'], status='passed'),
                ParameterCase(
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
            cases=[ParameterCase(values=['a|b'], status='passed')],
        ),
    )
    md = render_md(_report(scn))
    row = next(line for line in md.splitlines() if line.startswith('| a'))
    assert row == '| a\\|b | ✓ |'
    assert row.count(' | ') == 1


def test_param_table_escapes_newline_in_value() -> None:
    scn = Scenario(
        id='tests/t.py::test_nl',
        narration=Narration(text='NL'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='act'))],
        parameters=ParameterTable(
            columns=[ParameterColumn(id='label', name='label', kind='param')],
            cases=[ParameterCase(values=['a\nb'], status='passed')],
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
            cases=[ParameterCase(values=[None], status='passed')],
        ),
    )
    md = render_md(_report(scn))
    assert '| None | ✓ |' in md


@scenario(
    'A skipped scenario shows its skip reason',
)
def test_skipped_scenario_shows_reason() -> None:
    with given(t'a skipped {pg["Scenario"]} with a reason'):
        scn = Scenario(
            id='tests/t.py::test_skip',
            narration=Narration(text='Later'),
            module='tests/t.py',
            status='skipped',
            skip_reason='needs fixture data',
            steps=[Step(phase='when', narration=Narration(text='act'))],
        )
    with when(t'the Markdown {pg["Report"]} is rendered'):
        md = render_md(_report(scn))
    with then('the heading is marked skipped and the reason follows the node id'):
        attach('Rendered Markdown', md)
        assert '## ○ Later · skipped' in md
        assert '`tests/t.py::test_skip` — reason: needs fixture data' in md


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
    assert '| 350 | `ok\\|fine` | ✓ |' in md


def test_a_multiline_attachment_cell_shows_the_column_name_and_fences_below() -> None:
    """Cell and block both name the *column*, not the attachment label: two
    columns can share a label, and only the column name is disambiguated."""
    md = render_md(
        _report_with(_attachment_table(short=None, long='{"ml": 350,\n "full": true}'))
    )
    assert '| 350 | machine state | ✓ |' in md
    assert '{"ml": 350,' in md
    # The fenced block belongs *after* the table, separated from it by a blank
    # line: emitted before the rows it leaves a header-only table followed by
    # loose text, and without the blank line a GFM parser keeps the block
    # header inside the table.
    assert '| 350 | machine state | ✓ |\n\n- **350** — machine state:\n' in md


def test_a_backtick_bearing_attachment_cell_also_fences_below_the_table() -> None:
    """`_fits_inline` rejects backticks as well as newlines, and the cell path
    is a new caller of it — the multiline test above pins only one of its two
    conditions."""
    md = render_md(
        _report_with(_attachment_table(short=None, long='use `attach` here'))
    )
    assert '| 350 | machine state | ✓ |' in md
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
    assert '| 350 | log | log #2 | ✓ |' in md
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
        cases=[ParameterCase(values=[350, None], status='passed')],
    )
    md = render_md(_report_with(table))
    assert '| 350 |  | ✓ |' in md


def test_a_derived_column_cell_renders_through_the_ordinary_cell_path() -> None:
    """A derived cell holds a plain value rather than an attachment, so it
    renders verbatim — no backticks, no fenced block below the table."""
    table = ParameterTable(
        columns=[
            ParameterColumn(id='cup_size', name='cup_size', kind='param'),
            ParameterColumn(id='derived:0', name='price', kind='derived'),
        ],
        cases=[ParameterCase(values=[350, '3.5'], status='passed')],
    )
    md = render_md(_report_with(table))
    assert '| 350 | 3.5 | ✓ |' in md


def test_a_long_single_line_attachment_cell_fences_below_the_table() -> None:
    """A payload with no newline still wrecks the table when it is long — a
    300-character cell pushes every other column off the terminal. Length is
    the same problem as a newline, so it takes the same route: the column name
    in the cell, the payload fenced below."""
    payload = '{"id": "ch_3PmZ", "amount": 250, ' + '"x": "y", ' * 30 + '"end": true}'
    md = render_md(_report_with(_attachment_table(short=payload, long=None)))
    assert '| 350 | machine state | ✓ |' in md
    assert f'- **350** — machine state:\n  ```\n  {payload}\n  ```' in md


def test_an_attachment_cell_at_the_inline_limit_still_sits_inline() -> None:
    """The bound is on the payload itself, so a cell that fits stays inline —
    pinning the boundary keeps the check from drifting into 'fence everything'.
    """
    payload = 'x' * 72
    md = render_md(_report_with(_attachment_table(short=payload, long=None)))
    assert f'| 350 | `{payload}` | ✓ |' in md


def test_header_prefers_the_title_over_the_project() -> None:
    md = render_md(_report(project='pytest-given', title='Coffee Shop Example'))
    assert md.startswith('# pytest-given — Coffee Shop Example')
