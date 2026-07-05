from pytest_given.model import (
    Attachment,
    ErrorInfo,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    ParameterCase,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
    TracebackFrame,
)
from pytest_given.report.md_renderer import render_md


def _report(*scenarios: Scenario, project: str = 'proj') -> ReportData:
    return ReportData(
        metadata=Metadata(
            project=project,
            timestamp='t',
            pytest_version='9',
            plugin_version='0.1',
        ),
        scenarios=list(scenarios),
    )


def test_header_names_the_project() -> None:
    md = render_md(_report(project='hotel'))
    assert md.startswith('# pytest-given — hotel')


def test_passed_scenario_heading_and_steps() -> None:
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
    md = render_md(_report(scn))
    assert '## ✓ Buy coffee' in md
    assert '`tests/t.py::test_buy` · billing, happy-path' in md
    assert '- **given** a machine' in md
    assert '- **when** I insert $2' in md
    assert '- **then** I get a coffee' in md


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


def test_nested_steps_indent() -> None:
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
    md = render_md(_report(scn))
    assert '- **when** outer' in md
    assert '  - **when** inner' in md


def test_narration_parts_resolve_terms_and_values() -> None:
    scn = Scenario(
        id='tests/t.py::test_parts',
        narration=Narration(text='ignored'),
        module='tests/t.py',
        steps=[
            Step(
                phase='when',
                narration=Narration(
                    text='fallback',
                    parts=[
                        NarrationLiteral(value='a '),
                        NarrationTermRef(term_id='guest', display='Guest'),
                        NarrationValue(rendered='42', expression='n'),
                        NarrationPlaceholder(name='amount'),
                    ],
                ),
            )
        ],
    )
    md = render_md(_report(scn))
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


def test_parametrized_scenario_renders_table() -> None:
    scn = Scenario(
        id='tests/t.py::test_price',
        narration=Narration(text='Pricing'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='insert'))],
        parameters=ParameterTable(
            names=['euros', 'expect'],
            cases=[
                ParameterCase(values=[1, False], status='passed'),
                ParameterCase(values=[2, True], status='passed'),
            ],
        ),
    )
    md = render_md(_report(scn))
    assert '## ✓ Pricing · 2 cases' in md
    assert '| euros | expect | |' in md
    assert '| 1 | False | ✓ |' in md
    assert '| 2 | True | ✓ |' in md


def test_failing_step_is_marked_with_minimal_error() -> None:
    scn = Scenario(
        id='tests/t.py::test_sold_out',
        narration=Narration(text='Sold out'),
        module='tests/t.py',
        status='failed',
        steps=[
            Step(
                phase='then',
                narration=Narration(text='reports sold out'),
                status='failed',
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
        ],
    )
    md = render_md(_report(scn))
    assert '## ✗ Sold out' in md
    assert '- **then** reports sold out  **← FAILED**' in md
    assert '> ValueError: not sold out' in md
    assert '> test_shop.py:88 in test_sold_out' in md
    assert 'assert 1 == 0' not in md  # only the first message line


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


def test_multiline_attachment_renders_fenced_block() -> None:
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
    md = render_md(_report(scn))
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


def test_param_table_escapes_pipe_in_value() -> None:
    scn = Scenario(
        id='tests/t.py::test_pipe',
        narration=Narration(text='Pipe'),
        module='tests/t.py',
        steps=[Step(phase='when', narration=Narration(text='act'))],
        parameters=ParameterTable(
            names=['label'],
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
            names=['label'],
            cases=[ParameterCase(values=['a\nb'], status='passed')],
        ),
    )
    md = render_md(_report(scn))
    assert '| a<br>b |' in md
    assert 'a\nb' not in md


def test_skipped_scenario_shows_reason() -> None:
    scn = Scenario(
        id='tests/t.py::test_skip',
        narration=Narration(text='Later'),
        module='tests/t.py',
        status='skipped',
        skip_reason='needs fixture data',
        steps=[Step(phase='when', narration=Narration(text='act'))],
    )
    md = render_md(_report(scn))
    assert '## ⤼ Later · skipped' in md
    assert '`tests/t.py::test_skip` — reason: needs fixture data' in md
