from pytest_given.model import (
    Clause,
    ClausePart,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationTermRef,
    NodeId,
    ReportData,
    Scenario,
    Sentence,
    SentenceId,
    Step,
    Story,
    StoryId,
    TermId,
)


def _refs(*term_ids: str) -> tuple[ClausePart, ...]:
    return tuple(NarrationTermRef(term_id=TermId(tid), display=tid) for tid in term_ids)


def story_report() -> ReportData:
    """One story of an anchored sentence (`guest search room`), an anchored one
    nothing narrates (`guest confirm booking`), and an under-anchored one
    (`guest browses listings`); a single bound scenario whose one step narrates
    the first."""
    story = Story(
        id=StoryId('book'),
        title='Book',
        sentences=(
            Sentence(
                id=SentenceId(1),
                clauses=(Clause(parts=_refs('guest', 'search', 'room')),),
            ),
            Sentence(
                id=SentenceId(2),
                clauses=(Clause(parts=_refs('guest', 'confirm', 'booking')),),
            ),
            Sentence(
                id=SentenceId(3),
                clauses=(
                    Clause(
                        parts=(
                            *_refs('guest'),
                            NarrationLiteral(value='browses'),
                            NarrationLiteral(value='listings'),
                        )
                    ),
                ),
            ),
        ),
    )
    step = Step(
        phase='when',
        narration=Narration(
            text='guest search room',
            parts=tuple(
                NarrationTermRef(term_id=TermId(tid), display=tid)
                for tid in ('guest', 'search', 'room')
            ),
        ),
    )
    return ReportData(
        metadata=Metadata(
            project='p', timestamp='t', pytest_version='8', plugin_version='0'
        ),
        scenarios=[
            Scenario(
                id=NodeId('tests/test_demo.py::test_demo'),
                narration=Narration(text='A demo scenario'),
                module='tests.test_demo',
                status='passed',
                steps=[step],
                story_ids=(StoryId('book'),),
            )
        ],
        stories=[story],
    )
