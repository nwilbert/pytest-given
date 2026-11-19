from pytest_given.model import (
    CapturedStep,
    Clause,
    Definition,
    Glossary,
    GlossaryTerm,
    Narration,
    NarrationLiteral,
    NarrationTermRef,
    NodeId,
    Scenario,
    Sentence,
    SentenceId,
    SourceLocation,
    Story,
    StoryId,
    TermId,
)
from pytest_given.plugin.capture_document import (
    session_capture_from_dict,
    session_capture_to_dict,
)
from pytest_given.plugin.session_capture import SessionCapture


def _capture(glossary: Glossary | None) -> SessionCapture:
    nested = CapturedStep(
        phase='given',
        narration=Narration(text='nested'),
        source=SourceLocation(relpath='t.py', line=8),
    )
    step = CapturedStep(
        phase='given',
        narration=Narration(text='outer'),
        children=[nested],
        source=SourceLocation(relpath='t.py', line=7),
    )
    scenario = Scenario(
        id=NodeId('t.py::f'),
        narration=Narration(text='n'),
        module='t',
        steps=[step],
        source=SourceLocation(relpath='t.py', line=6),
    )
    clause = Clause(parts=(NarrationTermRef(term_id=TermId('guest'), display='Guest'),))
    story = Story(
        id=StoryId('s'),
        title='S',
        sentences=(Sentence(id=SentenceId(1), clauses=(clause,)),),
    )
    return SessionCapture(
        scenarios=[scenario],
        collection_index={NodeId('t.py::f'): 3},
        stories=[story],
        glossary=glossary,
    )


def test_a_session_capture_round_trips_with_step_source() -> None:
    glossary = Glossary()
    glossary.register(
        GlossaryTerm(
            id=TermId('guest'),
            kind='actor',
            canonical='Guest',
            definition=Definition(
                'Someone staying', (NarrationLiteral(value='Someone staying'),)
            ),
            avoid=('customer',),
        )
    )
    capture = _capture(glossary)
    restored = session_capture_from_dict(session_capture_to_dict(capture))
    assert restored.scenarios == capture.scenarios
    assert restored.scenarios[0].steps[0].children[0].source == SourceLocation(
        relpath='t.py', line=8
    )
    assert restored.collection_index == capture.collection_index
    assert restored.stories == capture.stories
    assert restored.glossary is not None
    assert restored.glossary.terms == glossary.terms


def test_a_capture_without_glossary_round_trips() -> None:
    capture = _capture(None)
    restored = session_capture_from_dict(session_capture_to_dict(capture))
    assert restored.glossary is None
