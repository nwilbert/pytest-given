from pytest_given import attach, given, scenario, then, when
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
    SourceLocation,
    Step,
    TracebackFrame,
    report_to_dict,
)
from pytest_given.report.md_renderer import render_md
from tests.ubiquitous_language import pg


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


@scenario(
    'A passed scenario renders as a checked heading with step bullets',
    tags=['happy-path'],
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
        attach('Scenario record', report_to_dict(rd)['scenarios'][0])
    with when(t'the Markdown {pg["Report"]} is rendered'):
        md = render_md(rd)
    with then(t'the heading is checked and each {pg["Step"]} is a phase bullet'):
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


@scenario('Nested steps indent under their parent', tags=['happy-path'])
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
        assert '- **when** outer' in md
        assert '  - **when** inner' in md


@scenario(
    'Structured narration renders terms, values and placeholders',
    tags=['step-text'],
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
    with when(t'the Markdown {pg["Report"]} is rendered'):
        md = render_md(_report(scn))
    with then(
        t'the {pg["Term ref"]} renders in guillemets, the value verbatim '
        t'and the placeholder in braces'
    ):
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
    'A parametrized scenario renders its parameter table',
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
                names=['euros', 'expect'],
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
        assert '## ✓ Pricing · 2 cases' in md
        assert '| euros | expect | |' in md
        assert '| 1 | False | ✓ |' in md
        assert '| 2 | True | ✓ |' in md


@scenario(
    'A failing step is marked with a minimal error digest',
    tags=['happy-path'],
)
def test_failing_step_is_marked_with_minimal_error() -> None:
    with given(
        t'a failed {pg["Scenario"]} whose then {pg["Step"]} carries a two-line '
        t'error and an internal frame'
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
        rd = _report(scn)
        attach('Error record', report_to_dict(rd)['scenarios'][0]['steps'][0]['error'])
    with when(t'the Markdown {pg["Report"]} is rendered'):
        md = render_md(rd)
    with then('the heading is crossed and the failed step is marked'):
        assert '## ✗ Sold out' in md
        assert '- **then** reports sold out  **← FAILED**' in md
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


@scenario('A multi-line attachment renders as a fenced block', tags=['happy-path'])
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


@scenario('A skipped scenario shows its skip reason', tags=['happy-path'])
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
        assert '## ⤼ Later · skipped' in md
        assert '`tests/t.py::test_skip` — reason: needs fixture data' in md
