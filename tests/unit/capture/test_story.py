from pathlib import Path

import pytest

from pytest_given import (
    FileGlossary,
    Glossary,
    PytestGivenError,
    given,
    scenario,
    then,
    when,
    when_then,
)
from pytest_given.capture import source as source_mod
from pytest_given.capture.story import (
    UnnumberedSentence,
    carried_glossaries,
    clause,
    registered_stories,
    restore_story_registry,
    sentence,
    story,
)
from pytest_given.model import (
    Clause,
    ClauseTermRef,
    ClauseWord,
    GlossaryTerm,
    Pin,
    SentenceId,
    StoryId,
    TermId,
)
from tests.ubiquitous_language import adopt_pytest_given, pg

pytestmark = pytest.mark.usefixtures('isolated_story_registry')


@pytest.fixture
def g():
    return Glossary()


@pytest.fixture
@given('a Guest actor')
def guest(g):
    return g.actor('Guest')


@pytest.fixture
@given('a Room work object')
def room(g):
    return g.work_object('Room')


@pytest.fixture
@given('a search activity')
def search(g):
    return g.activity('search')


@scenario(
    t'An {pg["Actor"].low} handle in a {pg["Clause"].low} becomes a '
    t'{pg["Term ref"].low}',
)
def test_clause_dispatches_actor_to_clause_term_ref(guest, search, room):
    with when(t'a {pg["Clause"].low} is built from three glossary handles'):
        built = clause(guest, search, room)
    with then(t'the {pg["Actor"].low} slot becomes a {pg["Term ref"].low}'):
        assert isinstance(built, Clause)
        assert built.parts[0] == ClauseTermRef(term_id=guest.id, display='Guest')


def test_clause_dispatches_actor_instance_to_clause_term_ref_with_instance_display(
    guest,
    search,
    room,
):
    built = clause(guest('Alice'), search, room)
    assert built.parts[0] == ClauseTermRef(term_id=guest.id, display='Alice')


def test_clause_dispatches_work_object_to_clause_term_ref(guest, search, room):
    built = clause(guest, search, room)
    assert built.parts[2] == ClauseTermRef(term_id=room.id, display='Room')


def test_clause_dispatches_work_object_instance_to_clause_term_ref_with_display(
    guest,
    search,
    room,
):
    built = clause(guest, search, room('Deluxe Suite'))
    assert built.parts[2] == ClauseTermRef(term_id=room.id, display='Deluxe Suite')


def test_clause_dispatches_activity_to_clause_term_ref_with_canonical_display(
    guest,
    search,
    room,
):
    built = clause(guest, search, room)
    assert built.parts[1] == ClauseTermRef(term_id=search.id, display='search')


@scenario(
    t'An inflected {pg["Activity"].low} keeps its {pg["Term"].low} identity '
    t'but shows the {pg["Inflection"].low}',
)
def test_clause_dispatches_inflected_activity_to_clause_term_ref_with_inflected_display(
    guest,
    search,
    room,
):
    with given(t'an {pg["Activity"].low} handle called with an {pg["Inflection"].low}'):
        inflected = search('searches for')
    with when(t'it takes the verb slot of a {pg["Clause"].low}'):
        built = clause(guest, inflected, room)
    with then(
        t'the {pg["Term ref"].low} shows the inflection over the same '
        t'{pg["Activity"].low}'
    ):
        assert built.parts[1] == ClauseTermRef(
            term_id=search.id, display='searches for'
        )


@scenario(
    t'A bare string in a {pg["Clause"].low} becomes a connective word',
)
def test_clause_dispatches_bare_string_to_clause_word(guest, search, room):
    with when(t'a {pg["Clause"].low} is built with a bare word between term nodes'):
        built = clause(guest, search, room, 'for', guest('Alice'))
    with then(
        t'the bare word becomes a {pg["Clause part"].low} word, not a '
        t'{pg["Term ref"].low}'
    ):
        assert built.parts[3] == ClauseWord(text='for')


# --- Task 4.2: grammar validation ---


@scenario(
    t'A {pg["Clause"].low} needs at least an {pg["Actor"].low}, an '
    t'{pg["Activity"].low} and a node',
    tags=['validation'],
)
def test_clause_rejects_fewer_than_three_parts(guest, search):
    with (
        when_then(
            t'a {pg["Clause"].low} of only two parts is built',
            'a PytestGivenError rejects it as too short, counting the parts',
        ),
        # The part count is the only thing separating this message from the
        # dangling-edge one below, so it is what the pin has to carry.
        pytest.raises(PytestGivenError, match=r'odd length >= 3.*got 2 part\(s\)'),
    ):
        clause(guest, search)


@scenario(
    t'A {pg["Clause"].low} position takes only the kinds its {pg["Slot"].low} accepts',
    tags=['validation'],
)
@pytest.mark.parametrize(
    ('kind', 'position', 'outcome'),
    [
        ('actor', 0, 'accepted'),
        ('actor', 1, 'refused'),
        ('actor', 2, 'accepted'),
        ('object', 0, 'refused'),
        ('object', 1, 'refused'),
        ('object', 2, 'accepted'),
        ('activity', 0, 'refused'),
        ('activity', 1, 'accepted'),
        ('activity', 2, 'refused'),
        (None, 0, 'accepted'),
        (None, 1, 'accepted'),
        (None, 2, 'accepted'),
    ],
)
def test_a_clause_position_takes_only_the_kinds_its_slot_accepts(
    g, guest, search, room, kind, position, outcome
):
    with given(t'a {pg["Term"].low} declared as {kind}'):
        g.register(GlossaryTerm(id=TermId('thing'), kind=kind, canonical='Thing'))
        part = g['Thing']
    with when(t'a {pg["Clause"].low} is built with it at position {position}'):
        parts = [guest, search, room]
        parts[position] = part
        try:
            clause(*parts)
            refusal = ''
        except PytestGivenError as error:
            refusal = str(error)
    with then(t'the {pg["Term"].low} is {outcome}'):
        assert ('refused' if refusal else 'accepted') == outcome
    with then('a refusal names the position and the declared kind'):
        assert (
            f'clause position {position} must be' in refusal
            and "'Thing' is declared" in refusal
        ) == (outcome == 'refused')


@scenario(
    t'A bare string may fill any {pg["Slot"].low} of a {pg["Clause"].low}, as a word',
)
@pytest.mark.parametrize('position', [0, 1, 2])
def test_a_bare_string_may_fill_any_slot(guest, search, room, position):
    with given('the bare string "plain"'):
        word = 'plain'
    with when(t'a {pg["Clause"].low} is built with it at position {position}'):
        parts: list[object] = [guest, search, room]
        parts[position] = word
        built = clause(*parts)
    with then(t'it becomes a {pg["Clause part"].low} word there'):
        assert built.parts[position] == ClauseWord(text='plain')
    with then(t'the other parts stay {pg["Term ref"]("term refs")}'):
        others = [part for index, part in enumerate(built.parts) if index != position]
        assert all(isinstance(part, ClauseTermRef) for part in others)


@scenario(
    t'A {pg["Clause"].low} may be fully bare words',
)
def test_clause_allows_fully_bare_words():
    with given('three plain words with no glossary handles'):
        words = ('Guest', 'receives', 'Confirmation')
    with when(t'a {pg["Clause"].low} is built from them'):
        built = clause(*words)
    with then(t'every part is a {pg["Clause part"].low} word'):
        assert [type(part) for part in built.parts] == [
            ClauseWord,
            ClauseWord,
            ClauseWord,
        ]


# --- Task 5: node/edge alternation ---


@scenario(
    'Node/edge alternation allows a trailing connective node',
)
def test_clause_allows_node_edge_alternation_with_connective():
    with given(
        t'an {pg["Actor"].low}, an {pg["Activity"].low}, a {pg["Work Object"].low} '
        t'and a second actor'
    ):
        g = Glossary()
        actor = g.actor('Organizer')
        verb = g.activity('adds')
        guest = g.actor('Guest')
        booking = g.work_object('Booking')
    with when(t'they form a five-part {pg["Clause"].low} joined by a connective'):
        result = clause(actor, verb, booking, 'to', guest)
    with then('even positions are term-ref nodes and the connective stays a word'):
        assert [type(part) for part in result.parts] == [
            ClauseTermRef,
            ClauseTermRef,
            ClauseTermRef,
            ClauseWord,
            ClauseTermRef,
        ]
        assert result.parts[3].text == 'to'


@scenario(
    t'A {pg["Clause"].low} may not end on a dangling edge',
    tags=['validation'],
)
def test_clause_rejects_dangling_edge():
    with given(
        t'an {pg["Actor"].low}, {pg["Activity"].low} and {pg["Work Object"].low} plus '
        t'a '
        t'connective'
    ):
        g = Glossary()
        actor = g.actor('Organizer')
        verb = g.activity('adds')
        booking = g.work_object('Booking')
    with (
        when_then(
            'a clause ending on a connective edge is built',
            'a PytestGivenError names the trailing arrow with no target',
        ),
        pytest.raises(
            PytestGivenError,
            match=r'got 4 part\(s\).*trailing arrow with no target',
        ),
    ):
        clause(actor, verb, booking, 'to')


# --- Task 4.3: sentence() constructor ---


@scenario(
    t'A single-clause {pg["Sentence"].low} synthesizes one {pg["Clause"].low}',
    stories=adopt_pytest_given,
)
def test_sentence_single_clause_synthesizes_one_clause(guest, search, room):
    with when(
        t'a {pg["Sentence"].low} is built from handles directly',
        pins=adopt_pytest_given['capture'],
    ):
        a = sentence(guest, search, room)
    with then(t'it wraps a single {pg["Clause"].low}'):
        assert isinstance(a, UnnumberedSentence)
        assert len(a.clauses) == 1
        assert a.clauses[0].parts[0].display == 'Guest'


@scenario(
    t'A {pg["Sentence"].low} may hold several {pg["Clause"]("clauses")}',
    stories=adopt_pytest_given,
)
def test_sentence_accepts_multiple_clauses(guest, search, room):
    with given(t'two {pg["Clause"]("clauses")}'):
        first = clause(guest, search, room)
        second = clause(guest('Bob'), search, room)
    with when(
        t'they are combined into one {pg["Sentence"].low}',
        pins=adopt_pytest_given['capture'],
    ):
        a = sentence(first, second)
    with then('the sentence carries both clauses'):
        assert a.clauses == (first, second)


@scenario(
    t'Mixing loose parts and prebuilt {pg["Clause"]("clauses")} is rejected',
    tags=['validation'],
)
def test_sentence_mixing_parts_and_clauses_raises(guest, search, room):
    with given(t'a prebuilt {pg["Clause"].low}'):
        built = clause(guest, search, room)
    with (
        when_then(
            t'it is combined with loose handles in one {pg["Sentence"].low}',
            'a PytestGivenError rejects the mix',
        ),
        pytest.raises(PytestGivenError, match='mix'),
    ):
        sentence(built, guest, search, room)


# --- Task 4.4: story() constructor ---


@scenario(
    t'A {pg["Story"].low} auto-numbers its {pg["Sentence"]("sentences")} from one',
    stories=adopt_pytest_given,
)
def test_story_auto_numbers_sentences_from_one(guest, search, room):
    with when(
        t'a {pg["Story"].low} is built from two {pg["Sentence"].low} rows',
        pins=adopt_pytest_given['capture'],
    ):
        s = story(
            'Book a Room',
            [sentence(guest, search, room), sentence(guest('Alice'), search, room)],
        )
    with then('the sentences are numbered 1 and 2'):
        assert s.sentences[0].id == 1
        assert s.sentences[1].id == 2


@scenario(
    t'A {pg["Story"].low} derives its id from its title',
)
def test_story_derives_id_from_title():
    with given('a human-readable story title'):
        title = 'Book a Room'
    with when(t'a {pg["Story"].low} is built from it'):
        s = story(title, [])
    with then('its id is the slugified title'):
        assert s.id == StoryId('book-a-room')


@scenario(
    t'A {pg["Story"].low} may span only one {pg["Glossary"].low}',
    tags=['validation'],
)
def test_story_rejects_two_glossaries(guest, search, room):
    with given('two sentences that reach two different glossaries'):
        other = Glossary()
        other_search = other.activity('search')
    with (
        when_then(
            t'a {pg["Story"].low} is built spanning both glossaries',
            'a PytestGivenError says a story spans multiple glossaries',
        ),
        pytest.raises(PytestGivenError, match='spans multiple glossaries'),
    ):
        story(
            'Book',
            [sentence(guest, search, room), sentence(guest, other_search, room)],
        )


def test_story_empty_title_raises():
    with pytest.raises(PytestGivenError, match='derived id is empty'):
        story('---', [])


def test_story_captures_source_from_call_site(g):
    repo_root = Path(__file__).resolve().parents[3]
    source_mod.set_rootdir(repo_root)
    try:
        guest = g.actor('Guest')
        room = g.work_object('Room')
        books = g.activity('books')

        s = story('Checkout', [sentence(guest, books, room)])

        assert s.source is not None
        assert s.source.relpath.endswith('test_story.py')
        assert s.source.line > 0
    finally:
        source_mod.restore_rootdir(None)


# --- Task 1 (pins): sentence numbers, names and sentence handles ---


@scenario(
    t'A {pg["Sentence"].low} {pg["Handle"].low} is looked up by name or by number',
)
def test_story_hands_out_a_sentence_by_name_and_by_number(guest, search, room):
    with given(t'a {pg["Story"].low} whose second {pg["Sentence"].low} is named'):
        built = story(
            'Lookup',
            [
                sentence(guest, search, room),
                sentence(guest('Alice'), search, room, name='cancel'),
            ],
        )
    with when(t'the {pg["Sentence"].low} is looked up by its name and by its number'):
        by_name = built['cancel']
        by_number = built[2]
    with then(
        t'both {pg["Handle"]("handles")} name sentence 2 of that {pg["Story"].low}'
    ):
        expected = Pin(story_id=built.id, sentence_id=SentenceId(2))
        assert by_name.pin == by_number.pin == expected


@scenario(t'Iterating a {pg["Story"].low} yields its {pg["Sentence"].low} handles')
def test_iterating_a_story_yields_its_sentence_handles(guest, search, room):
    with given(t'a {pg["Story"].low} of two {pg["Sentence"]("sentences")}'):
        built = story(
            'Iterated',
            [sentence(guest, search, room), sentence(guest('Alice'), search, room)],
        )
    with when(t'the {pg["Story"].low} is iterated'):
        handles = list(built)
    with then(t'it yields each {pg["Sentence"].low} handle in order'):
        assert handles == [built[1], built[2]]


def test_story_reads_a_one_shot_iterable_of_sentences_once(guest, search, room):
    built = story('Generated', (sentence(guest, search, room) for _ in range(2)))
    assert [one.id for one in built.sentences] == [1, 2]
    assert carried_glossaries(built) == frozenset({guest.glossary})


def test_a_story_that_fails_its_checks_leaves_its_id_free(guest, search, room):
    with pytest.raises(PytestGivenError, match='names two sentences'):
        story(
            'Retried',
            [
                sentence(guest, search, room, name='x'),
                sentence(guest, search, room, name='x'),
            ],
        )
    assert story('Retried', [sentence(guest, search, room)]).title == 'Retried'


def test_the_registry_lists_declared_stories_in_order(guest, search, room):
    first = story('First', [sentence(guest, search, room)])
    second = story('Second')
    assert registered_stories() == [first, second]


@scenario(
    t'Looking up a {pg["Sentence"].low} the {pg["Story"].low} lacks lists the '
    t'ones it has',
)
def test_story_lookup_miss_lists_the_sentences(guest, search, room):
    with given(t'a {pg["Story"].low} with an unnamed and a named {pg["Sentence"].low}'):
        built = story(
            'Lookup Miss',
            [
                sentence(guest, search, room),
                sentence(guest('Alice'), search, room, name='search'),
            ],
        )
    with (
        when_then(
            'an unknown name is looked up',
            "a PytestGivenError lists the story's sentences",
        ),
        pytest.raises(
            PytestGivenError,
            match=r"story 'Lookup Miss' has no sentence 'serch'.*1, 2 'search'",
        ),
    ):
        _ = built['serch']


@pytest.mark.parametrize('key', [0, -1, 3, True])
def test_story_lookup_refuses_a_number_that_is_no_sentence_number(
    guest, search, room, key
):
    built = story(
        'Bad Numbers', [sentence(guest, search, room), sentence(guest, search, room)]
    )
    with pytest.raises(PytestGivenError, match='has no sentence'):
        _ = built[key]


def test_story_lookup_miss_is_a_lookup_error(guest, search, room):
    """A live run's report renders this capture story, and Jinja's attribute
    fallback probes it with `story[name]`, catching only `LookupError`."""
    built = story('Probed', [sentence(guest, search, room)])
    with pytest.raises(LookupError):
        _ = built['description']


def test_story_lookup_reads_a_numeric_string_as_a_name(guest, search, room):
    built = story(
        'Numeric Name',
        [
            sentence(guest, search, room),
            sentence(guest('Alice'), search, room, name='1'),
        ],
    )
    assert built['1'].pin.sentence_id == 2
    assert built[1].pin.sentence_id == 1
    with pytest.raises(PytestGivenError, match=r"has no sentence '2'"):
        _ = built['2']


def test_story_numbers_sentences_by_position(guest, search, room):
    built = story(
        'Positions',
        [sentence(guest, search, room, name='first'), sentence(guest, search, room)],
    )
    assert [one.id for one in built.sentences] == [1, 2]
    assert [one.name for one in built.sentences] == ['first', None]


@scenario(
    t'Two {pg["Sentence"]("sentences")} of one {pg["Story"].low} cannot share a name',
    tags=['validation'],
)
def test_story_rejects_duplicate_sentence_names(guest, search, room):
    with given(t'two {pg["Sentence"]("sentences")} both named "cancel"'):
        first = sentence(guest, search, room, name='cancel')
        second = sentence(guest('Alice'), search, room, name='cancel')
    with (
        when_then(
            t'a {pg["Story"].low} is built from them',
            'a PytestGivenError names the duplicate and both numbers',
        ),
        pytest.raises(PytestGivenError, match=r"'cancel'.*sentences 1 and 2"),
    ):
        story('Duplicate Names', [first, second])


@scenario(
    t'A {pg["Sentence"].low} name must be non-empty and unpadded',
    tags=['validation'],
)
@pytest.mark.parametrize(
    ('name', 'outcome'),
    [
        ('cancel', 'accepted'),
        ('', 'refused'),
        (' cancel', 'refused'),
        ('cancel ', 'refused'),
    ],
)
def test_a_sentence_name_must_be_non_empty_and_unpadded(
    guest, search, room, name, outcome
):
    with given(t'the {pg["Sentence"].low} name {name!r}'):
        sentence_name = name
    with when(t'a {pg["Sentence"].low} is built with that name'):
        try:
            sentence(guest, search, room, name=sentence_name)
            refusal = ''
        except PytestGivenError as error:
            refusal = str(error)
    with then(t'the name is {outcome}'):
        assert ('refused' if refusal else 'accepted') == outcome
    with then('a refusal says what a name must be'):
        assert (
            'a sentence name must be a non-empty str, with no leading or' in refusal
        ) == (outcome == 'refused')


# --- Task 4.5: story-id duplicate detection ---


@scenario(
    t'Two {pg["Story"]("stories")} with the same id collide',
    tags=['validation'],
)
def test_story_id_collision_raises_with_both_sites():
    with given(t'a {pg["Story"].low} already declared under an id'):
        story('Book a Room', [])
    with (
        when_then(
            'a second story is declared with the same slug',
            'a PytestGivenError reports the id was already declared',
        ),
        pytest.raises(PytestGivenError, match='already declared'),
    ):
        story('book-a-room', [])


def test_story_id_collision_reports_a_rootdir_relative_site():
    repo_root = Path(__file__).resolve().parents[3]
    source_mod.set_rootdir(repo_root)
    try:
        story('Book a Room', [])
        with pytest.raises(PytestGivenError, match='already declared') as excinfo:
            story('book-a-room', [])
    finally:
        source_mod.restore_rootdir(None)
    assert 'tests/unit/capture/test_story.py:' in str(excinfo.value)
    assert str(repo_root) not in str(excinfo.value)


def test_story_id_collision_does_not_fire_after_registry_clear():
    story('Book', [])
    restore_story_registry({})
    story('Book', [])


def test_clause_records_single_glossary(guest, search, room):
    """The live Glossary the clause references is pinned so the single-glossary
    invariant can be enforced at story construction and the plugin can resolve
    the report glossary from the story tree."""
    built = clause(guest, search, room)
    assert carried_glossaries(built) == frozenset({guest.glossary})


def test_sentence_unions_glossaries_across_clauses(g, guest, search, room):
    # Two clauses, same glossary — the pin must dedup by identity, not double-count.
    first = clause(guest, search, room)
    second = clause(guest('Alice'), search, room)
    a = sentence(first, second)
    assert carried_glossaries(a) == frozenset({g})


def test_story_stashes_its_glossary(guest, search, room):
    """story() carries the referenced Glossary on the Story tree so
    plugin._resolve_glossary can pick it without any session-global."""
    s = story('Book', [sentence(guest, search, room)])
    assert carried_glossaries(s) == frozenset({guest.glossary})


# --- Additional grammar/constructor cases (kept as plain unit checks) ---


def test_clause_allows_bare_string_in_position_1(guest, room):
    built = clause(guest, 'searches', room)
    assert built.parts[1] == ClauseWord(text='searches')


def test_clause_allows_bare_string_in_position_2(guest, search):
    built = clause(guest, search, 'the room')
    assert built.parts[2] == ClauseWord(text='the room')


def test_clause_accepts_actor_in_position_2(guest, search):
    built = clause(guest, search, guest('Bob'))
    assert isinstance(built.parts[2], ClauseTermRef)


def test_clause_accepts_extended_alternation(guest, search, room):
    # actor verb node connective node — valid 5-part alternation ending on a node
    built = clause(guest, search, room, 'into', room('Inbox'))
    assert len(built.parts) == 5


@scenario(
    t'A {pg["Clause"].low} may chain a second verb-object pair',
)
def test_clause_allows_second_verb_edge():
    with given(
        t'an {pg["Actor"].low}, two {pg["Activity"].low} and two '
        t'{pg["Work Object"].low} '
        t'handles'
    ):
        g = Glossary()
        actor = g.actor('System')
        confirm = g.activity('confirms')
        booking = g.work_object('Booking')
        send = g.activity('sends')
        note = g.work_object('Confirmation')
    with when(
        t'they form a five-node {pg["Clause"].low} (actor verb object verb object)'
    ):
        result = clause(actor, confirm, booking, send, note)
    with then(t'every slot is a {pg["Term ref"].low}, with no bare words'):
        assert [type(part) for part in result.parts] == [ClauseTermRef] * 5


def test_clause_allows_bare_string_at_later_even_position(guest, search, room):
    # actor verb node connective bare-node — even index 4 is a bare word
    built = clause(guest, search, room, 'into', 'Inbox')
    assert built.parts[4] == ClauseWord(text='Inbox')


# --- Task 4.6: top-level re-exports ---


def test_top_level_imports():
    # Deliberately function-level: this module imports these names from their
    # internal paths, so the assertion here is that the *package root* also
    # re-exports them. Hoisting would shadow the internal imports and test
    # nothing.
    from pytest_given import Glossary, sentence, story

    g = Glossary()
    guest = g.actor('Guest')
    search = g.activity('search')
    room = g.work_object('Room')
    built = clause(guest, search, room)
    a = sentence(built)
    s = story('Smoke', [a])
    assert s.title == 'Smoke'


# --- Declared-kind slot checking at construction ---


@scenario(
    t'A declared {pg["Work Object"].low} in a verb {pg["Slot"].low} '
    t'is rejected at construction',
    tags=['validation'],
)
def test_file_glossary_declared_kind_in_wrong_slot_raises(tmp_path):
    with given(t'a {pg["File glossary"].low} declaring Room a work object'):
        glossary_file = tmp_path / 'GLOSSARY.md'
        glossary_file.write_text(
            '| Term | Meaning | Kind |\n'
            '|---|---|---|\n'
            '| Guest | A person | actor |\n'
            '| Room | A place | object |\n',
            encoding='utf-8',
        )
        fg = FileGlossary(glossary_file, kind_column='Kind')
    with (
        when_then(
            t'Room is placed in the verb {pg["Slot"].low}',
            'a PytestGivenError names the term and its declared kind',
        ),
        pytest.raises(PytestGivenError, match=r"'Room'.*declared a work object"),
    ):
        clause(fg['Guest'], fg['Room'], fg['Guest'])


@scenario(
    t'A {pg["Slot"].low} error names the {pg["Term"].low}, not its repr',
    tags=['diagnostics'],
)
def test_slot_error_message_stays_compact(guest, room, search):
    with (
        when_then(
            t'a {pg["Work Object"].low} is placed in the verb slot',
            'the message names the term without dumping the glossary',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        clause(guest, room, room)
    with then('the message is short and free of dataclass reprs'):
        message = str(excinfo.value)
        assert 'Glossary(terms=' not in message
        assert 'GlossaryTerm(' not in message
        assert len(message) < 300
        assert "'Room'" in message


@scenario(
    t'A non-handle {pg["Clause part"].low} names its type',
    tags=['validation', 'diagnostics'],
)
def test_non_handle_part_names_its_type(guest, room):
    with (
        when_then(
            t'an int is passed where an {pg["Activity"].low} handle belongs',
            'a PytestGivenError names the offending type and the clause',
        ),
        pytest.raises(
            PytestGivenError,
            match=r'must be a verb: got int.*Clause: Guest → int → Room',
        ),
    ):
        clause(guest, 42, room)


def test_sentence_rejects_a_non_str_name(guest, search, room):
    with pytest.raises(PytestGivenError, match='sentence name'):
        sentence(guest, search, room, name=3)


def test_story_lookup_on_empty_story_says_it_has_no_sentences():
    built = story('Empty', [])
    with pytest.raises(PytestGivenError, match='it has no sentences'):
        _ = built[1]


def test_misplaced_instances_name_their_canonical_term(g, tmp_path):
    # Plain, not narrated: one rule ("a misplaced part names its term") is
    # already covered above; these are its surface forms, and a scenario each
    # would be report noise.
    guest = g.actor('Guest')
    room = g.work_object('Room')
    search = g.activity('search')
    deferred = g('loyalty points')
    cases = [
        # Each puts one instance form in a slot its kind cannot fill.
        ((guest, guest('Alice'), room), r"'Guest' is declared an actor"),
        ((guest, search, search('searches for')), r"'search' is declared an activity"),
        ((guest, room('Suite'), room), r"'Room' is declared a work object"),
    ]
    for parts, expected in cases:
        with pytest.raises(PytestGivenError, match=expected):
            clause(*parts)
    # A deferred instance carries no declared kind, so it stays valid anywhere.
    assert len(clause(deferred('points'), deferred, deferred).parts) == 3
    # But a deferred handle from a kind_column glossary does carry one, so its
    # instance form is checked the same way an eager instance is.
    glossary_file = tmp_path / 'GLOSSARY.md'
    glossary_file.write_text(
        '| Term | Meaning | Kind |\n|---|---|---|\n| Room | A place | object |\n',
        encoding='utf-8',
    )
    fg = FileGlossary(glossary_file, kind_column='Kind')
    with pytest.raises(PytestGivenError, match=r"'Room' is declared a work object"):
        clause(fg['Room'], fg['Room']('Suite'), fg['Room'])
