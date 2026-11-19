"""Report builders more than one model test reads."""

from pytest_given.delta import (
    AttachmentDelta,
    CasePair,
    DeltaData,
    DeltaSide,
    DiffSegment,
    LineDelta,
    ParameterDelta,
    ScenarioDelta,
    StepDelta,
    TermDelta,
    TermFacts,
    TextSegment,
)
from pytest_given.delta.schema import (
    CellDelta,
    ColumnPair,
    DeltaMetadata,
    GlossaryDelta,
    IdentityPair,
    Suggestion,
)
from pytest_given.model import (
    Attachment,
    AttachmentLabel,
    AttachmentRef,
    Clause,
    ColumnId,
    Definition,
    ErrorCause,
    ErrorInfo,
    Glossary,
    GlossaryTerm,
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
    Pin,
    ReportData,
    Scenario,
    Sentence,
    SentenceId,
    SourceLocation,
    Step,
    Story,
    StoryId,
    TermId,
    TracebackFrame,
)
from tests.unit.delta.builders import (
    lit,
    meta,
    narr,
    ph,
    ref,
    scn,
    step,
    table,
    term,
)


def every_field_populated() -> ReportData:
    """A report exercising every optional field and every union variant."""
    term = GlossaryTerm(
        id=TermId('guest'),
        kind='actor',
        canonical='Guest',
        definition=Definition.literal('someone who books'),
        source=SourceLocation(relpath='g.py', line=3),
    )
    story = Story(
        id=StoryId('booking'),
        title='Booking',
        source=SourceLocation(relpath='s.py', line=1),
        sentences=(
            Sentence(
                id=SentenceId(1),
                clauses=(
                    Clause(
                        parts=(
                            NarrationTermRef(term_id=TermId('guest'), display='Guest'),
                            NarrationLiteral(value='books'),
                            NarrationTermRef(term_id=TermId('room'), display='Room'),
                        )
                    ),
                ),
            ),
        ),
    )
    step = Step(
        phase='given',
        narration=Narration(
            text='a Guest with 2 rooms',
            parts=(
                NarrationLiteral(value='a '),
                NarrationTermRef(
                    term_id=TermId('guest'), display='Guest', expression='pg'
                ),
                NarrationValue(
                    rendered='2', expression='count', conversion='r', format_spec='d'
                ),
                NarrationPlaceholder(
                    name='rooms',
                    column_id='rooms',
                    conversion='s',
                    format_spec='>4',
                ),
            ),
        ),
        attachments=[
            Attachment(label='payload', content='{"a": 1}', content_type='json'),
            AttachmentRef(
                label='varies', content_type='text', column_id='attachment:0'
            ),
        ],
        fixture_name='shop',
        pins=(Pin(story_id=StoryId('booking'), sentence_id=SentenceId(1)),),
        children=[Step(phase='then', narration=Narration(text='it holds'))],
    )
    scenario = Scenario(
        id=NodeId('t.py::test_a[1]'),
        narration=Narration(
            text='A booking', parts=(NarrationLiteral(value='A booking'),)
        ),
        module='t',
        tags=['smoke'],
        status='failed',
        duration_ms=12,
        steps=[step],
        parameters=ParameterTable(
            columns=[
                ParameterColumn(id='rooms', name='rooms', kind='param'),
                ParameterColumn(id='derived:0', name='total', kind='derived'),
                ParameterColumn(id='attachment:0', name='varies', kind='attachment'),
            ],
            cases=[
                ParameterCase(
                    id=NodeId('t.py::test_x[5]'),
                    values=[
                        2,
                        'four',
                        Attachment(label='varies', content='x', content_type='text'),
                    ],
                    status='failed',
                    error=ErrorInfo(
                        message='boom',
                        frames=[
                            TracebackFrame(
                                path='t.py',
                                lineno=9,
                                func='test_a',
                                code='assert x',
                                is_internal=False,
                            )
                        ],
                        error_tail='E   AssertionError',
                        causes=[
                            ErrorCause(
                                frames=[
                                    TracebackFrame(
                                        path='t.py',
                                        lineno=3,
                                        func='load',
                                        code='raise E',
                                        is_internal=False,
                                    )
                                ],
                                error_tail='E   ValueError',
                                connector='During handling of the above '
                                'exception, another exception occurred:',
                            )
                        ],
                    ),
                )
            ],
        ),
        error=ErrorInfo(message='boom', frames=[], error_tail=None),
        skip_reason=None,
        source=SourceLocation(relpath='t.py', line=5),
        story_ids=(StoryId('booking'),),
        pins=(Pin(story_id=StoryId('booking'), sentence_id=SentenceId(1)),),
    )
    return ReportData(
        metadata=Metadata(
            project='p',
            timestamp='2026-09-02',
            pytest_version='9',
            plugin_version='0.1',
            commit_sha='abc123',
            title='A title',
        ),
        scenarios=[scenario],
        stories=[story],
        glossary=Glossary(terms=[term]),
    )


def full_delta() -> DeltaData:
    value = NarrationValue(
        rendered='3', expression='n', format_spec='02', conversion='r'
    )
    words = (
        DiffSegment(
            mark='equal',
            before=(lit('a  '), ref('coffee', 'coffee')),
            after=(lit('a '), ref('coffee', 'Coffee')),
        ),
        DiffSegment(mark='removed', before=(lit('old'), value)),
        DiffSegment(mark='added', after=(ph('size', 'size'), lit('new'))),
    )
    before_scenario = scn(
        'tests/test_a.py::test_a[1]',
        'A brew',
        step(
            'given', narr(lit('a '), ref('coffee', 'coffee')), step('when', 'it pours')
        ),
        step('when', 'it cools'),
        step('then', 'it is gone'),
        parameters=table(
            [('size', 'param'), ('log', 'attachment')],
            ('1', [1, None]),
            ('gone', [2, None]),
            custom=True,
        ),
    )
    after_scenario = scn(
        'tests/test_a.py::test_a[2]',
        'A brew',
        step('given', 'a cup', step('when', 'it fills'), step('when', 'it brews')),
        step('then', 'it is served'),
        tags=['fast'],
        status='failed',
        parameters=table(
            [('size', 'param'), ('shown', 'derived'), ('log', 'attachment')],
            ('2', [1, 'x', Attachment(AttachmentLabel('log'), 'a')], 'failed'),
        ),
    )
    changed = ScenarioDelta(
        change='changed',
        before=before_scenario,
        after=after_scenario,
        paired_by='rename-log',
        changed_in=('title', 'steps', 'attachments'),
        steps=(
            StepDelta(
                change='modified',
                before=(0,),
                after=(0, 1),
                words=words,
                children=(StepDelta(change='equal', before=(0, 0), after=(0, 0)),),
                attachments=(
                    AttachmentDelta(
                        change='changed',
                        before=0,
                        after=0,
                        lines=(
                            LineDelta(change='equal', before=0, after=0, count=2),
                            LineDelta(
                                change='modified',
                                before=2,
                                after=2,
                                words=(
                                    TextSegment(mark='equal', text='a '),
                                    TextSegment(mark='removed', text='b'),
                                    TextSegment(mark='added', text='c'),
                                ),
                            ),
                            LineDelta(change='removed', before=3),
                            LineDelta(change='added', after=3),
                        ),
                    ),
                    AttachmentDelta(change='equal', before=1, after=1),
                    AttachmentDelta(change='added', after=2),
                    AttachmentDelta(change='removed', before=2),
                ),
            ),
            StepDelta(change='added', after=(1,)),
            StepDelta(change='removed', before=(2,)),
        ),
        parameters=ParameterDelta(
            columns=(
                ColumnPair(
                    kind='param',
                    before=ColumnId('size'),
                    after=ColumnId('size'),
                    paired_by='name',
                ),
                ColumnPair(kind='derived', after=ColumnId('derived:0')),
                ColumnPair(
                    kind='attachment',
                    before=ColumnId('attachment:0'),
                    after=ColumnId('attachment:0'),
                    paired_by='name',
                ),
            ),
            cases=(
                CasePair(
                    before=NodeId('1'),
                    after=NodeId('2'),
                    paired_by='values',
                    changed_cells=(ColumnId('size'),),
                    changed_attachments=(
                        CellDelta(
                            column=ColumnId('attachment:0'),
                            lines=(LineDelta(change='added', after=0),),
                        ),
                    ),
                    id_changed=True,
                    status_changed=True,
                ),
                CasePair(before=NodeId('gone')),
            ),
        ),
    )
    return DeltaData(
        metadata=DeltaMetadata(
            before=DeltaSide(metadata=meta('aaa'), label='v1', modules=('m.a',)),
            after=DeltaSide(metadata=meta('bbb'), modules=('m.a', 'm.b')),
            plugin_version='0.2.0',
            timestamp='2026-02-02T00:00:00+00:00',
            title='Coffee changes for v2',
        ),
        scenarios=(
            changed,
            ScenarioDelta(change='added', after=after_scenario),
            ScenarioDelta(change='removed', before=before_scenario),
        ),
        unchanged=(IdentityPair(before='t::a', after='t::a'),),
        suggestions=(
            Suggestion(of='scenario', before='t::old', after='t::new'),
            Suggestion(
                of='case',
                before='1',
                after='2',
                scenario=IdentityPair(before='t::a', after='t::a'),
            ),
        ),
        glossary=GlossaryDelta(
            before=Glossary(terms=[term('coffee', 'coffee', definition='A drink.')]),
            after=Glossary(terms=[term('coffee', 'coffee', definition='A hot drink.')]),
            terms=(
                TermDelta(
                    change='changed',
                    before=term('coffee', 'coffee', definition='A drink.'),
                    after=term('coffee', 'coffee', definition='A hot drink.'),
                    paired_by='term-id',
                    before_facts=TermFacts(other_forms=('coffees',), scenario_count=2),
                    after_facts=TermFacts(scenario_count=3),
                    definition=(DiffSegment(mark='added', after=(lit('hot'),)),),
                ),
                TermDelta(change='added', after=term('tea', 'tea')),
            ),
            unchanged=(IdentityPair(before='tea', after='tea'),),
        ),
    )
