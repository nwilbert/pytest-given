import dataclasses

import pytest

from pytest_given.capture import FixtureRecording
from pytest_given.capture.collector import RecordingState
from pytest_given.model import (
    Attachment,
    AttachmentRef,
    Clause,
    ClausePart,
    ClauseTermRef,
    ClauseWord,
    ErrorInfo,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
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
    case_id,
    case_suffix,
    definition_bold_spans,
    derived_id,
    node_base,
)


def _n(text: str) -> Narration:
    return Narration(text=text)


def test_step_defaults() -> None:
    step = Step(phase='given', narration=_n('a coffee machine'))
    assert step.phase == 'given'
    assert step.narration.text == 'a coffee machine'
    assert step.narration.parts == ()
    assert step.children == []
    assert step.attachments == []
    assert step.fixture_name is None


def test_step_fixture_name_is_set_when_provided() -> None:
    step = Step(phase='given', narration=_n('our guest'), fixture_name='alice')
    assert step.fixture_name == 'alice'


def test_step_with_children() -> None:
    child = Step(phase='when', narration=_n('validating coin'))
    parent = Step(phase='when', narration=_n('insert money'), children=[child])
    assert len(parent.children) == 1
    assert parent.children[0].narration.text == 'validating coin'


def test_attachment() -> None:
    att = Attachment(label='Machine log', content='log line 1\nlog line 2')
    assert att.label == 'Machine log'
    assert att.content == 'log line 1\nlog line 2'


def test_error_info_with_frames_and_tail() -> None:
    err = ErrorInfo(
        message='assert 1 == 2',
        frames=[
            TracebackFrame(
                path='tests/test_x.py',
                lineno=10,
                func='test_x',
                code='    assert 1 == 2',
                is_internal=False,
            ),
        ],
        error_tail='E   assert 1 == 2',
    )
    assert err.message == 'assert 1 == 2'
    assert len(err.frames) == 1
    assert err.frames[0].is_internal is False
    assert err.error_tail == 'E   assert 1 == 2'


def test_error_info_defaults() -> None:
    err = ErrorInfo(message='assert False')
    assert err.frames == []
    assert err.error_tail is None


def test_scenario_defaults() -> None:
    s = Scenario(
        id='test_file.py::test_foo',
        narration=_n('Foo scenario'),
        module='test_file',
    )
    assert s.tags == []
    assert s.status == 'passed'
    assert s.duration_ms == 0
    assert s.steps == []
    assert s.parameters is None
    assert s.error is None


def test_parameter_table() -> None:
    case1 = ParameterCase(id=NodeId('t.py::test_x[1]'), values=[1, 0], status='passed')
    case2 = ParameterCase(
        id=NodeId('t.py::test_x[2]'),
        values=[2, 1],
        status='failed',
        error=ErrorInfo(message='fail'),
    )
    table = ParameterTable(
        columns=[
            ParameterColumn(id='euros', name='euros', kind='param'),
            ParameterColumn(id='coffees', name='coffees', kind='param'),
        ],
        cases=[case1, case2],
    )
    assert [c.name for c in table.columns] == ['euros', 'coffees']
    assert len(table.cases) == 2
    assert table.cases[1].error is not None


@pytest.mark.parametrize(
    ('node_id', 'expected'),
    [
        pytest.param('t.py::test_x[touching-edges]', 'touching-edges', id='plain'),
        pytest.param('t.py::C::test_x[edge-1]', 'edge-1', id='stacked'),
        pytest.param('t.py::test_x[a[0]]', 'a[0]', id='bracketed'),
        pytest.param('t.py::test_x', '', id='hidden'),
        pytest.param('tests/[legacy]/t.py::test_x[1]', '1', id='bracketed-path'),
    ],
)
def test_case_id_is_the_node_ids_suffix_unbracketed(
    node_id: str, expected: str
) -> None:
    assert case_id(node_id) == expected


def test_metadata() -> None:
    m = Metadata(
        project='coffee-shop',
        timestamp='2026-04-09T14:30:00Z',
        pytest_version='9.0',
        plugin_version='0.1.0',
    )
    assert m.project == 'coffee-shop'


def test_report_data() -> None:
    report = ReportData(
        metadata=Metadata(
            project='test',
            timestamp='now',
            pytest_version='9',
            plugin_version='0.1',
        ),
        scenarios=[],
    )
    assert report.scenarios == []


def test_recording_state_literals() -> None:
    # Type-check sanity: these are the four legal states
    states: list[RecordingState] = ['idle', 'test', 'fixture_setup', 'fixture_teardown']
    assert len(states) == 4


def test_fixture_recording_holds_root_step_and_stack() -> None:
    root = Step(phase='given', narration=_n('a shop'))
    recording = FixtureRecording(root=root)
    assert recording.root is root
    assert recording.stack == [root]


def test_step_narration_defaults_to_plain_text() -> None:
    step = Step(phase='given', narration=_n('hello'))
    assert step.narration.parts == ()


def test_step_narration_accepts_parts() -> None:
    parts: list[NarrationPart] = [
        NarrationLiteral(value='Brew '),
        NarrationPlaceholder(name='cup_size', column_id='cup_size'),
        NarrationLiteral(value=' ml'),
    ]
    step = Step(phase='given', narration=Narration(text='Brew 200 ml', parts=parts))
    assert step.narration.parts == parts


def test_scenario_narration_defaults_to_plain_text() -> None:
    s = Scenario(id='id', narration=_n('hello'), module='m')
    assert s.narration.parts == ()


def test_scenario_skip_reason_defaults_to_none() -> None:
    s = Scenario(id=NodeId('t::x'), narration=Narration(text='x'), module='m')
    assert s.skip_reason is None


def test_source_location_is_frozen() -> None:
    src = SourceLocation(relpath='tests/test_x.py', line=42)
    assert src.relpath == 'tests/test_x.py'
    assert src.line == 42
    with pytest.raises(dataclasses.FrozenInstanceError):
        src.line = 99  # type: ignore[misc]


def test_scenario_source_defaults_to_none() -> None:
    s = Scenario(
        id=NodeId('test.py::t'),
        narration=_n('n'),
        module='mod',
    )
    assert s.source is None


def test_story_source_defaults_to_none() -> None:
    s = Story(id=StoryId('checkout'), title='Checkout', sentences=())
    assert s.source is None


def test_story_carries_source_location() -> None:
    src = SourceLocation(relpath='tests/conftest.py', line=12)
    s = Story(id=StoryId('checkout'), title='Checkout', sentences=(), source=src)
    assert s.source == src


def test_glossary_term_source_defaults_to_none() -> None:
    t = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest')
    assert t.source is None


def test_glossary_term_carries_source_location() -> None:
    src = SourceLocation(relpath='tests/conftest.py', line=4)
    t = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest', source=src)
    assert t.source == src


def test_metadata_commit_sha_defaults_to_none() -> None:
    m = Metadata(project='p', timestamp='t', pytest_version='9', plugin_version='0.1')
    assert m.commit_sha is None


# --- Task 1.1: Id aliases + GlossaryTerm ---


def test_glossary_term_is_frozen_and_kw_only() -> None:
    term = GlossaryTerm(
        id=TermId('guest'),
        kind='actor',
        canonical='Guest',
        definition='Person booking accommodation.',
    )
    assert term.id == 'guest'
    assert term.kind == 'actor'
    assert term.canonical == 'Guest'
    assert term.definition == 'Person booking accommodation.'
    with pytest.raises(dataclasses.FrozenInstanceError):
        term.kind = 'activity'  # type: ignore[misc]


def test_glossary_term_definition_defaults_none() -> None:
    term = GlossaryTerm(id=TermId('x'), kind='activity', canonical='x')
    assert term.definition is None


# --- Task 1.2: Sentence-part variants + ClausePart union ---


def test_clause_term_ref_carries_term_id_and_display() -> None:
    part = ClauseTermRef(term_id=TermId('guest'), display='Alice')
    assert part.term_id == 'guest'
    assert part.display == 'Alice'


def test_clause_word_carries_text() -> None:
    part = ClauseWord(text='for')
    assert part.text == 'for'


def test_clause_parts_are_frozen() -> None:
    part = ClauseWord(text='for')
    with pytest.raises(dataclasses.FrozenInstanceError):
        part.text = 'and'  # type: ignore[misc]


def test_clause_part_union_accepts_all_variants() -> None:
    parts: list[ClausePart] = [
        ClauseTermRef(term_id=TermId('g'), display='Guest'),
        ClauseTermRef(term_id=TermId('s'), display='searches'),
        ClauseWord(text='for'),
    ]
    assert [type(p).__name__ for p in parts] == [
        'ClauseTermRef',
        'ClauseTermRef',
        'ClauseWord',
    ]


# --- Task 1.3: Clause, Sentence, Story with _by_id index ---


def test_clause_is_frozen_with_parts_tuple() -> None:
    path = Clause(
        parts=(
            ClauseTermRef(term_id=TermId('guest'), display='Guest'),
            ClauseTermRef(term_id=TermId('search'), display='searches for'),
            ClauseTermRef(term_id=TermId('room'), display='Room'),
        )
    )
    assert len(path.parts) == 3


def test_sentence_holds_id_and_clauses() -> None:
    p = Clause(
        parts=(
            ClauseTermRef(term_id=TermId('g'), display='G'),
            ClauseTermRef(term_id=TermId('s'), display='s'),
            ClauseTermRef(term_id=TermId('o'), display='O'),
        )
    )
    act = Sentence(id=SentenceId(1), clauses=(p,))
    assert act.id == 1
    assert act.clauses == (p,)


def test_story_glossary_pin_excluded_from_repr_and_equality() -> None:
    p = Clause(
        parts=(
            ClauseTermRef(term_id=TermId('g'), display='G'),
            ClauseTermRef(term_id=TermId('s'), display='s'),
            ClauseTermRef(term_id=TermId('o'), display='O'),
        )
    )
    a = Sentence(id=SentenceId(1), clauses=(p,))
    s1 = Story(id=StoryId('x'), title='X', sentences=(a,))
    s2 = Story(id=StoryId('x'), title='X', sentences=(a,))
    assert s1 == s2
    assert '_glossaries' not in repr(s1)


def test_a_glossary_is_identified_by_object_not_by_value() -> None:
    """Nothing compares two glossaries by value, and several places collect the
    distinct ones a story tree reaches — which needs them hashable."""
    one = Glossary(terms=[GlossaryTerm(id=TermId('a'), kind='actor', canonical='A')])
    same_terms = Glossary(
        terms=[GlossaryTerm(id=TermId('a'), kind='actor', canonical='A')]
    )
    assert one != same_terms
    assert one == one
    assert frozenset({one, same_terms, one}) == frozenset({one, same_terms})


# --- Task 1.4: Glossary container with atomic write-through ---


def test_glossary_register_appends_and_indexes() -> None:
    g = Glossary()
    t = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest')
    g.register(t)
    assert g.terms == [t]
    assert g.get(TermId('guest')) is t
    assert g.get(TermId('missing')) is None


def test_glossary_register_rejects_id_collision() -> None:
    g = Glossary()
    g.register(GlossaryTerm(id=TermId('x'), kind='actor', canonical='X'))
    with pytest.raises(AssertionError, match='already registered'):
        g.register(GlossaryTerm(id=TermId('x'), kind='activity', canonical='X'))


def test_glossary_index_excluded_from_repr() -> None:
    """The index is derived from `terms`; showing it would double every term."""
    g = Glossary()
    g.register(GlossaryTerm(id=TermId('x'), kind='actor', canonical='X'))
    assert '_by_id' not in repr(g)


def test_glossary_post_init_indexes_terms_passed_at_construction() -> None:
    t1 = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest')
    t2 = GlossaryTerm(id=TermId('room'), kind='object', canonical='Room')
    g = Glossary(terms=[t1, t2])
    assert g.get(TermId('guest')) is t1
    assert g.get(TermId('room')) is t2


# --- Task 1.5: NarrationTermRef + extended NarrationPart union ---


def test_narration_term_ref_carries_term_id_display_and_expression() -> None:
    part = NarrationTermRef(term_id=TermId('guest'), display='Alice')
    assert part.term_id == 'guest'
    assert part.display == 'Alice'
    assert part.expression == ''

    part2 = NarrationTermRef(
        term_id=TermId('guest'), display='Alice', expression='guest_name'
    )
    assert part2.expression == 'guest_name'


def test_narration_term_ref_is_assignable_to_narration_part() -> None:
    part: NarrationPart = NarrationTermRef(term_id=TermId('guest'), display='Alice')
    assert isinstance(part, NarrationTermRef)


# --- Task 1.6: Extend ReportData, Scenario, Step with new fields ---


def _meta() -> Metadata:
    return Metadata(
        project='proj',
        timestamp='now',
        pytest_version='8',
        plugin_version='0.1.0',
    )


def test_report_data_defaults_glossary_none_and_stories_empty() -> None:
    rd = ReportData(metadata=_meta())
    assert rd.glossary is None
    assert rd.stories == []


def test_report_data_accepts_glossary_and_stories() -> None:
    g = Glossary()
    g.register(GlossaryTerm(id=TermId('x'), kind='actor', canonical='X'))
    rd = ReportData(metadata=_meta(), glossary=g, stories=[])
    assert rd.glossary is g


def test_scenario_defaults_to_no_stories_and_not_pinned() -> None:
    scenario_ = Scenario(id=NodeId('n'), narration=Narration(text='t'), module='m')
    assert scenario_.story_ids == ()
    assert scenario_.pins is None


def test_scenario_accepts_story_ids_and_pins() -> None:
    pins = (
        Pin(story_id=StoryId('book'), sentence_id=SentenceId(1)),
        Pin(story_id=StoryId('book'), sentence_id=SentenceId(2)),
    )
    scenario_ = Scenario(
        id=NodeId('n'),
        narration=Narration(text='t'),
        module='m',
        story_ids=(StoryId('book'),),
        pins=pins,
    )
    assert scenario_.story_ids == ('book',)
    assert scenario_.pins == pins


def test_step_defaults_to_not_pinned() -> None:
    step = Step(phase='given', narration=Narration(text='t'))
    assert step.pins is None


def test_step_accepts_pins() -> None:
    pins = (Pin(story_id=StoryId('book'), sentence_id=SentenceId(3)),)
    step = Step(phase='given', narration=Narration(text='t'), pins=pins)
    assert step.pins == pins


def test_parameter_table_carries_typed_columns() -> None:
    table = ParameterTable(
        columns=[
            ParameterColumn(id='cup_size', name='cup_size', kind='param'),
            ParameterColumn(id='derived:0', name='price', kind='derived'),
            ParameterColumn(id='attachment:0', name='machine state', kind='attachment'),
        ],
        cases=[
            ParameterCase(
                id=NodeId('t.py::test_x[3]'),
                values=[
                    200,
                    '2.0',
                    Attachment(
                        label='machine state', content='{}', content_type='json'
                    ),
                ],
                status='passed',
            )
        ],
    )
    assert [c.kind for c in table.columns] == ['param', 'derived', 'attachment']
    assert len(table.cases[0].values) == len(table.columns)


def test_attachment_ref_has_no_content_field() -> None:
    ref = AttachmentRef(
        label='machine state', content_type='json', column_id='attachment:0'
    )
    assert not hasattr(ref, 'content')
    assert ref.column_id == 'attachment:0'


def test_node_base_drops_parametrize_tail() -> None:
    assert node_base('tests/t.py::test_x[1-2]') == 'tests/t.py::test_x'


def test_node_base_leaves_unparametrized_id_unchanged() -> None:
    assert node_base('tests/t.py::test_x') == 'tests/t.py::test_x'


def test_node_base_keeps_a_bracket_in_the_path() -> None:
    assert node_base('tests/[legacy]/t.py::test_x[1]') == 'tests/[legacy]/t.py::test_x'


def test_case_suffix_returns_the_bracketed_tail() -> None:
    assert case_suffix('tests/t.py::test_x[1-2]') == '[1-2]'


def test_case_suffix_is_empty_without_a_tail() -> None:
    assert case_suffix('tests/t.py::test_x') == ''


def test_case_suffix_is_empty_for_a_bracket_in_the_path_only() -> None:
    assert case_suffix('tests/[legacy]/t.py::test_x') == ''


@pytest.mark.parametrize(
    ('custom', 'expected'), [([False, False], False), ([False, True], True)]
)
def test_a_table_has_custom_ids_when_any_case_has_one(
    custom: list[bool], expected: bool
) -> None:
    table = ParameterTable(
        columns=[],
        cases=[
            ParameterCase(
                id=NodeId(f't.py::test_x[{index}]'), values=[], custom_id=flag
            )
            for index, flag in enumerate(custom)
        ],
    )
    assert table.has_custom_ids is expected


# --- Definition refs ---


def _term(canonical: str) -> GlossaryTerm:
    return GlossaryTerm(
        id=TermId(derived_id(canonical) or ''), kind='object', canonical=canonical
    )


@pytest.mark.parametrize('text', ['Phase', 'phase', 'PHASE', 'Phases', 'phases'])
def test_resolve_ref_matches_the_canonical_name_or_s_form_in_any_case(
    text: str,
) -> None:
    phase = _term('Phase')
    assert Glossary(terms=[phase]).resolve_ref(text) is phase


@pytest.mark.parametrize('text', ['term ref', 'Term refs', 'term-ref'])
def test_resolve_ref_matches_a_multi_word_term_by_derived_id(text: str) -> None:
    term_ref = _term('Term ref')
    assert Glossary(terms=[term_ref]).resolve_ref(text) is term_ref


@pytest.mark.parametrize('text', ['sentence handle', 'Phased', '', '***'])
def test_resolve_ref_returns_none_for_text_naming_no_term(text: str) -> None:
    glossary = Glossary(terms=[_term('Handle'), _term('Phase')])
    assert glossary.resolve_ref(text) is None


def test_resolve_ref_prefers_a_canonical_name_over_another_term_s_s_form() -> None:
    """`Tags` is both the S-form of `Tag` and a term of its own."""
    tag, tags = _term('Tag'), _term('Tags')
    for glossary in (Glossary(terms=[tag, tags]), Glossary(terms=[tags, tag])):
        assert glossary.resolve_ref('tags') is tags
        assert glossary.resolve_ref('tag') is tag


def test_resolve_ref_finds_a_term_registered_after_the_first_lookup() -> None:
    glossary = Glossary(terms=[_term('Phase')])
    assert glossary.resolve_ref('steps') is None
    step = _term('Step')
    glossary.register(step)
    assert glossary.resolve_ref('steps') is step


def test_definition_bold_spans_reads_only_bold() -> None:
    definition = 'A unit in one **Phase**, which *nests* and may carry **Attachments**.'
    assert list(definition_bold_spans(definition)) == ['Phase', 'Attachments']


def test_definition_bold_spans_skips_a_bold_span_holding_a_code_span() -> None:
    definition = 'Spelled **`.l`** or **`.s` form**, by a **Handle**.'
    assert list(definition_bold_spans(definition)) == ['Handle']


def test_definition_bold_spans_reads_a_possessive_outside_the_span() -> None:
    assert list(definition_bold_spans("A **Case**'s row.")) == ['Case']
