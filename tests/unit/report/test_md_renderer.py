from pytest_given.model import (
    Attachment,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationTermRef,
    NarrationValue,
    ReportData,
    Scenario,
    Step,
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
                    ],
                ),
            )
        ],
    )
    md = render_md(_report(scn))
    assert '- **when** a «Guest»42' in md


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
