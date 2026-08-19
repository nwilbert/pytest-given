"""Fixtures shared by the report unit tests."""

import pytest

from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    Glossary,
    Narration,
    NarrationLiteral,
    NarrationTermRef,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    Scenario,
    Step,
    Story,
    StoryId,
    TermId,
)


@pytest.fixture
def guest_scenario() -> tuple[Glossary, Story, Scenario]:
    """A grouped two-case scenario whose Guest pill is bound to the `guest`
    parametrize column — the shape the per-case columns design fixes."""
    glossary = Glossary()
    glossary.actor('Guest')
    glossary.verb('Check in')
    story = Story(
        id=StoryId('s'),
        title='S',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(
                    ActivityPath(
                        parts=(
                            ActivityTermRef(term_id=TermId('guest'), display='Bob'),
                            ActivityTermRef(
                                term_id=TermId('check-in'), display='checks in'
                            ),
                        )
                    ),
                ),
            ),
        ),
    )
    step = Step(
        phase='when',
        narration=Narration(
            text='Alice checks in',
            parts=[
                NarrationTermRef(
                    term_id=TermId('guest'),
                    display='Alice',
                    expression='guest',
                    param_column='guest',
                ),
                NarrationLiteral(value=' '),
                NarrationTermRef(term_id=TermId('check-in'), display='checks in'),
            ],
        ),
    )
    scenario = Scenario(
        id=NodeId('t.py::test_check_in'),
        narration=Narration(text='checks in'),
        module='m',
        steps=[step],
        parameters=ParameterTable(
            columns=[ParameterColumn(id='guest', name='guest', kind='param')],
            cases=[
                ParameterCase(values=['Alice'], status='passed'),
                ParameterCase(values=['Bob'], status='passed'),
            ],
        ),
    )
    return glossary, story, scenario
