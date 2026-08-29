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
    activity,
    clear_story_registry,
    path,
    story,
)
from pytest_given.model import (
    Activity,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    StoryId,
)
from tests.ubiquitous_language import adopt_pytest_given, pg


@pytest.fixture(autouse=True)
def _reset_story_registry():
    clear_story_registry()
    yield
    clear_story_registry()


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
@given('a search verb')
def search(g):
    return g.verb('search')


@scenario(
    t'An {pg["Actor"].low} handle in a {pg["Path"].low} becomes a {pg["Term ref"].low}',
)
def test_path_dispatches_actor_to_activity_term_ref(guest, search, room):
    with when(t'a {pg["Path"]} is built from three glossary handles'):
        p = path(guest, search, room)
    with then(t'the {pg["Actor"]} slot becomes a {pg["Term ref"]}'):
        assert isinstance(p, ActivityPath)
        assert p.parts[0] == ActivityTermRef(term_id=guest.id, display='Guest')


def test_path_dispatches_actor_instance_to_activity_term_ref_with_instance_display(
    guest,
    search,
    room,
):
    p = path(guest('Alice'), search, room)
    assert p.parts[0] == ActivityTermRef(term_id=guest.id, display='Alice')


def test_path_dispatches_work_object_to_activity_term_ref(guest, search, room):
    p = path(guest, search, room)
    assert p.parts[2] == ActivityTermRef(term_id=room.id, display='Room')


def test_path_dispatches_work_object_instance_to_activity_term_ref_with_display(
    guest,
    search,
    room,
):
    p = path(guest, search, room('Deluxe Suite'))
    assert p.parts[2] == ActivityTermRef(term_id=room.id, display='Deluxe Suite')


def test_path_dispatches_verb_to_activity_term_ref_with_canonical_display(
    guest,
    search,
    room,
):
    p = path(guest, search, room)
    assert p.parts[1] == ActivityTermRef(term_id=search.id, display='search')


@scenario(
    t'An inflected {pg["Verb"].low} keeps its {pg["Term"].low} identity '
    t'but shows the {pg["Inflection"].low}',
)
def test_path_dispatches_inflected_verb_to_activity_term_ref_with_inflected_display(
    guest,
    search,
    room,
):
    with given(t'a {pg["Verb"]} handle called with an {pg["Inflection"]}'):
        inflected = search('searches for')
    with when(t'it takes the verb slot of a {pg["Path"]}'):
        p = path(guest, inflected, room)
    with then(t'the {pg["Term ref"]} shows the inflection over the same {pg["Verb"]}'):
        assert p.parts[1] == ActivityTermRef(term_id=search.id, display='searches for')


@scenario(
    t'A bare string in a {pg["Path"].low} becomes a connective word',
)
def test_path_dispatches_bare_string_to_activity_word(guest, search, room):
    with when(t'a {pg["Path"]} is built with a bare word between term nodes'):
        p = path(guest, search, room, 'for', guest('Alice'))
    with then(
        t'the bare word becomes an {pg["Activity Part"]} word, not a {pg["Term ref"]}'
    ):
        assert p.parts[3] == ActivityWord(text='for')


# --- Task 4.2: grammar validation ---


@scenario(
    t'A {pg["Path"].low} needs at least an {pg["Actor"].low}, a '
    t'{pg["Verb"].low} and a node',
    tags=['validation'],
)
def test_path_rejects_path_with_fewer_than_three_parts(guest, search):
    with (
        when_then(
            t'a {pg["Path"]} of only two parts is built',
            'a PytestGivenError rejects it as too short',
        ),
        pytest.raises(PytestGivenError, match=r'odd|length.*3|alternate'),
    ):
        path(guest, search)


@scenario(
    t'Position 0 of a {pg["Path"].low} must be an {pg["Actor"].low}',
    tags=['validation'],
)
def test_path_rejects_work_object_in_position_0(search, room):
    with (
        when_then(
            t'a {pg["Path"]} is built with a {pg["Work Object"]} in position 0',
            t'a PytestGivenError says position 0 is the {pg["Actor"]} slot',
        ),
        pytest.raises(PytestGivenError, match=r'position 0.*actor'),
    ):
        path(room, search, room)


@scenario(
    t'A {pg["Verb"].low} cannot open a {pg["Path"].low}',
    tags=['validation'],
)
def test_path_rejects_verb_in_position_0(guest, search, room):
    with (
        when_then(
            t'a {pg["Verb"]} is placed in position 0 of a {pg["Path"]}',
            t'a PytestGivenError says position 0 is the {pg["Actor"]} slot',
        ),
        pytest.raises(PytestGivenError, match=r'position 0.*actor'),
    ):
        path(search, guest, room)


@scenario(
    t'A bare string may stand in for the {pg["Actor"].low} {pg["Slot"].low}',
)
def test_path_allows_bare_string_in_position_0(search, room):
    with when(t'a bare string takes position 0 of a {pg["Path"]}'):
        p = path('Guest', search, room)
    with then(t'it is accepted as an {pg["Activity Part"]} word'):
        assert p.parts[0] == ActivityWord(text='Guest')


@scenario(
    t'Position 1 of a {pg["Path"].low} must be a {pg["Verb"].low}',
    tags=['validation'],
)
def test_path_rejects_actor_in_position_1(guest, room):
    with (
        when_then(
            t'an {pg["Actor"]} is placed in position 1 of a {pg["Path"]}',
            t'a PytestGivenError says position 1 is the {pg["Verb"]} slot',
        ),
        pytest.raises(PytestGivenError, match=r'position 1.*verb'),
    ):
        path(guest, guest, room)


@scenario(
    t'A {pg["Work Object"].low} cannot fill the {pg["Verb"].low} {pg["Slot"].low}',
    tags=['validation'],
)
def test_path_rejects_work_object_in_position_1(guest, room):
    with (
        when_then(
            t'a {pg["Work Object"]} is placed in position 1 of a {pg["Path"]}',
            t'a PytestGivenError says position 1 is the {pg["Verb"]} slot',
        ),
        pytest.raises(PytestGivenError, match=r'position 1.*verb'),
    ):
        path(guest, room, room)


@scenario(
    t'Position 2 of a {pg["Path"].low} must be a noun',
    tags=['validation'],
)
def test_path_rejects_verb_in_position_2(guest, search):
    with (
        when_then(
            t'a {pg["Verb"]} is placed in position 2 of a {pg["Path"]}',
            'a PytestGivenError says position 2 is the noun slot',
        ),
        pytest.raises(PytestGivenError, match=r'position 2.*noun'),
    ):
        path(guest, search, search)


@scenario(
    t'A bare {pg["Verb"].low} may sit between two real entity nodes',
)
def test_path_allows_bare_verb_between_term_nodes(guest, room):
    with when(t'a bare verb sits between an {pg["Actor"]} and a {pg["Work Object"]}'):
        p = path(guest, 'receives', room)
    with then('the entities are term refs and the verb stays a bare word'):
        assert [type(part) for part in p.parts] == [
            ActivityTermRef,
            ActivityWord,
            ActivityTermRef,
        ]
        assert p.parts[1] == ActivityWord(text='receives')


@scenario(
    t'A {pg["Path"].low} may be fully bare words',
)
def test_path_allows_fully_bare_path():
    with given('three plain words with no glossary handles'):
        words = ('Guest', 'receives', 'Confirmation')
    with when(t'a {pg["Path"]} is built from them'):
        p = path(*words)
    with then(t'every part is an {pg["Activity Part"]} word'):
        assert [type(part) for part in p.parts] == [
            ActivityWord,
            ActivityWord,
            ActivityWord,
        ]


# --- Task 5: node/edge alternation ---


@scenario(
    'Node/edge alternation allows a trailing connective node',
)
def test_path_allows_node_edge_alternation_with_connective():
    with given(
        t'an {pg["Actor"]}, a {pg["Verb"]}, a {pg["Work Object"]} and a second actor'
    ):
        g = Glossary()
        actor = g.actor('Organizer')
        verb = g.verb('adds')
        guest = g.actor('Guest')
        booking = g.work_object('Booking')
    with when(t'they form a five-part {pg["Path"]} joined by a connective'):
        result = path(actor, verb, booking, 'to', guest)
    with then('even positions are term-ref nodes and the connective stays a word'):
        assert [type(part) for part in result.parts] == [
            ActivityTermRef,
            ActivityTermRef,
            ActivityTermRef,
            ActivityWord,
            ActivityTermRef,
        ]
        assert result.parts[3].text == 'to'


@scenario(
    t'A {pg["Path"].low} may not end on a dangling edge',
    tags=['validation'],
)
def test_path_rejects_dangling_edge():
    with given(
        t'an {pg["Actor"]}, {pg["Verb"]} and {pg["Work Object"]} plus a connective'
    ):
        g = Glossary()
        actor = g.actor('Organizer')
        verb = g.verb('adds')
        booking = g.work_object('Booking')
    with (
        when_then(
            'a path ending on a connective edge is built',
            'a PytestGivenError rejects the dangling edge',
        ),
        pytest.raises(PytestGivenError, match=r'odd|dangling|ends'),
    ):
        path(actor, verb, booking, 'to')


# --- Task 4.3: activity() constructor ---


@scenario(
    t'A single-path {pg["Activity"].low} synthesizes one {pg["Path"].low}',
    story=adopt_pytest_given,
)
def test_activity_single_path_synthesizes_one_path(guest, search, room):
    with when(t'an {pg["Activity"]} is built from handles directly', activity=2):
        a = activity(guest, search, room)
    with then(t'it wraps a single {pg["Path"]}'):
        assert isinstance(a, Activity)
        assert len(a.paths) == 1
        assert a.paths[0].parts[0].display == 'Guest'


@scenario(
    t'An {pg["Activity"].low} may branch into multiple {pg["Path"]("paths")}',
    story=adopt_pytest_given,
)
def test_activity_multi_path_accepts_multiple_paths(guest, search, room):
    with given(t'two alternate {pg["Path"]} branches'):
        p1 = path(guest, search, room)
        p2 = path(guest('Bob'), search, room)
    with when(t'they are combined into one {pg["Activity"]}', activity=2):
        a = activity(p1, p2)
    with then('the activity carries both paths'):
        assert a.paths == (p1, p2)


@scenario(
    t'Mixing loose parts and prebuilt {pg["Path"]("paths")} is rejected',
    tags=['validation'],
)
def test_activity_mixing_parts_and_paths_raises(guest, search, room):
    with given(t'a prebuilt {pg["Path"]}'):
        p = path(guest, search, room)
    with (
        when_then(
            t'it is combined with loose handles in one {pg["Activity"]}',
            'a PytestGivenError rejects the mix',
        ),
        pytest.raises(PytestGivenError, match='mix'),
    ):
        activity(p, guest, search, room)


@scenario(
    t'{pg["Activity"]} id 0 is reserved',
    tags=['validation'],
)
def test_activity_explicit_id_zero_raises(guest, search, room):
    with (
        when_then(
            t'an {pg["Activity"]} is built with explicit activity_id=0',
            'a PytestGivenError says activity_id=0 is reserved',
        ),
        pytest.raises(PytestGivenError, match=r'activity_id=0.*reserved'),
    ):
        activity(guest, search, room, activity_id=0)


# --- Task 4.4: story() constructor ---


@scenario(
    t'A {pg["Story"].low} auto-numbers its {pg["Activity"]("activities")} from one',
    story=adopt_pytest_given,
)
def test_story_auto_numbers_activities_from_one(guest, search, room):
    with when(t'a {pg["Story"]} is built from two {pg["Activity"]} rows', activity=2):
        s = story(
            'Book a Room',
            [activity(guest, search, room), activity(guest('Alice'), search, room)],
        )
    with then('the activities are numbered 1 and 2'):
        assert s.activities[0].id == 1
        assert s.activities[1].id == 2


@scenario(
    'Auto-numbering skips ids already taken explicitly',
)
def test_story_auto_numbering_skips_taken_explicit_ids(guest, search, room):
    with given(t'a mix of explicit and auto {pg["Activity"]} ids'):
        activities = [
            activity(guest, search, room, activity_id=1),
            activity(guest('Alice'), search, room),
            activity(guest('Bob'), search, room, activity_id=3),
            activity(guest('Cara'), search, room),
        ]
    with when(t'they are assembled into a {pg["Story"]}'):
        s = story('Book a Room', activities)
    with then('auto picks skip the ids already used explicitly'):
        assert [a.id for a in s.activities] == [1, 2, 3, 4]


@scenario(
    t'Duplicate {pg["Activity"].low} ids in a {pg["Story"].low} are rejected',
    tags=['validation'],
)
def test_story_rejects_duplicate_activity_ids(guest, search, room):
    with given(t'two {pg["Activity"]} rows sharing an explicit id'):
        rows = [
            activity(guest, search, room, activity_id=1),
            activity(guest('Alice'), search, room, activity_id=1),
        ]
    with (
        when_then(
            t'they are assembled into a {pg["Story"]}',
            'a PytestGivenError reports the duplicate activity id',
        ),
        pytest.raises(PytestGivenError, match='duplicate activity id'),
    ):
        story('Book', rows)


@scenario(
    t'A {pg["Story"].low} derives its id from its title',
)
def test_story_derives_id_from_title():
    with given('a human-readable story title'):
        title = 'Book a Room'
    with when(t'a {pg["Story"]} is built from it'):
        s = story(title, [])
    with then('its id is the slugified title'):
        assert s.id == StoryId('book-a-room')


@scenario(
    t'A {pg["Story"].low} may span only one {pg["Glossary"].low}',
    tags=['validation'],
)
def test_story_rejects_two_glossaries(guest, search, room):
    with given('two activities that reach two different glossaries'):
        other = Glossary()
        other_search = other.verb('search')
    with (
        when_then(
            t'a {pg["Story"]} is built spanning both glossaries',
            'a PytestGivenError says a story spans multiple glossaries',
        ),
        pytest.raises(PytestGivenError, match='spans multiple glossaries'),
    ):
        story(
            'Book',
            [activity(guest, search, room), activity(guest, other_search, room)],
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
        books = g.verb('books')

        s = story('Checkout', [activity(guest, books, room)])

        assert s.source is not None
        assert s.source.relpath.endswith('test_story.py')
        assert s.source.line > 0
    finally:
        source_mod.restore_rootdir(None)


# --- Task 4.5: story-id duplicate detection ---


@scenario(
    t'Two {pg["Story"]("stories")} with the same id collide',
    tags=['validation'],
)
def test_story_id_collision_raises_with_both_sites():
    with given(t'a {pg["Story"]} already declared under an id'):
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
    clear_story_registry()
    story('Book', [])


def test_path_records_single_glossary(guest, search, room):
    """The live Glossary the path references is stashed (keyed by object id) so
    the single-glossary invariant can be enforced at story construction and the
    plugin can resolve the report glossary from the story tree."""
    p = path(guest, search, room)
    assert getattr(p, '_glossaries', {}) == {id(guest.glossary): guest.glossary}


def test_activity_unions_glossaries_across_paths(g, guest, search, room):
    # Two paths, same glossary — the stash must dedup by identity, not double-count.
    p1 = path(guest, search, room)
    p2 = path(guest('Alice'), search, room)
    a = activity(p1, p2)
    assert getattr(a, '_glossaries', {}) == {id(g): g}


def test_story_stashes_its_glossary(guest, search, room):
    """story() carries the referenced Glossary on the Story tree so
    plugin._resolve_glossary can pick it without any session-global."""
    s = story('Book', [activity(guest, search, room)])
    assert getattr(s, '_glossaries', {}) == {id(guest.glossary): guest.glossary}


# --- Additional grammar/constructor cases (kept as plain unit checks) ---


def test_path_allows_bare_string_in_position_1(guest, room):
    p = path(guest, 'searches', room)
    assert p.parts[1] == ActivityWord(text='searches')


def test_path_allows_bare_string_in_position_2(guest, search):
    p = path(guest, search, 'the room')
    assert p.parts[2] == ActivityWord(text='the room')


def test_path_accepts_actor_in_position_2(guest, search):
    p = path(guest, search, guest('Bob'))
    assert isinstance(p.parts[2], ActivityTermRef)


def test_path_accepts_extended_alternation(guest, search, room):
    # actor verb node connective node — valid 5-part alternation ending on a node
    p = path(guest, search, room, 'into', room('Inbox'))
    assert len(p.parts) == 5


@scenario(
    t'A {pg["Path"].low} may chain a second verb-object pair',
)
def test_path_allows_second_verb_edge():
    with given(
        t'an {pg["Actor"]}, two {pg["Verb"]} and two {pg["Work Object"]} handles'
    ):
        g = Glossary()
        actor = g.actor('System')
        confirm = g.verb('confirms')
        booking = g.work_object('Booking')
        send = g.verb('sends')
        note = g.work_object('Confirmation')
    with when(t'they form a five-node {pg["Path"]} (actor verb object verb object)'):
        result = path(actor, confirm, booking, send, note)
    with then(t'every slot is a {pg["Term ref"]}, with no bare words'):
        assert [type(part) for part in result.parts] == [ActivityTermRef] * 5


def test_path_allows_bare_string_at_later_even_position(guest, search, room):
    # actor verb node connective bare-node — even index 4 is a bare word
    p = path(guest, search, room, 'into', 'Inbox')
    assert p.parts[4] == ActivityWord(text='Inbox')


def test_activity_id_defaults_to_zero_when_unspecified(guest, search, room):
    a = activity(guest, search, room)
    assert a.id == 0


def test_activity_explicit_id_overrides_default(guest, search, room):
    a = activity(guest, search, room, activity_id=7)
    assert a.id == 7


def test_activity_explicit_id_with_multipath(guest, search, room):
    p1 = path(guest, search, room)
    p2 = path(guest('Bob'), search, room)
    a = activity(p1, p2, activity_id=3)
    assert a.id == 3
    assert a.paths == (p1, p2)


def test_story_keeps_explicit_activity_ids(guest, search, room):
    s = story(
        'Book a Room',
        [
            activity(guest, search, room, activity_id=10),
            activity(guest('Alice'), search, room),
        ],
    )
    assert s.activities[0].id == 10
    assert s.activities[1].id == 1


def test_story_auto_numbering_skips_taken_ids_even_when_earlier_auto(
    guest, search, room
):
    """Explicit activity_id=1 anywhere takes precedence over the auto counter."""
    s = story(
        'Book a Room',
        [
            activity(guest('Alice'), search, room),
            activity(guest, search, room, activity_id=1),
        ],
    )
    assert [a.id for a in s.activities] == [2, 1]


# --- Task 4.6: top-level re-exports ---


def test_top_level_imports():
    # Deliberately function-level: this module imports these names from their
    # internal paths, so the assertion here is that the *package root* also
    # re-exports them. Hoisting would shadow the internal imports and test
    # nothing.
    from pytest_given import Glossary, activity, path, story

    g = Glossary()
    guest = g.actor('Guest')
    search = g.verb('search')
    room = g.work_object('Room')
    p = path(guest, search, room)
    a = activity(p)
    s = story('Smoke', [a])
    assert s.title == 'Smoke'


# --- Declared-kind slot checking at construction ---


@scenario(
    t'A declared {pg["Work Object"].low} in a {pg["Verb"].low} {pg["Slot"].low} '
    t'is rejected at construction',
    tags=['validation'],
)
def test_file_glossary_declared_kind_in_wrong_slot_raises(tmp_path):
    with given(t'a {pg["File glossary"]} declaring Room a work object'):
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
            t'Room is placed in the {pg["Verb"].low} {pg["Slot"].low}',
            'a PytestGivenError names the term and its declared kind',
        ),
        pytest.raises(PytestGivenError, match=r"'Room'.*declared a work object"),
    ):
        path(fg['Guest'], fg['Room'], fg['Guest'])


@scenario(
    t'A {pg["Slot"].low} error names the {pg["Term"].low}, not its repr',
    tags=['diagnostics'],
)
def test_slot_error_message_stays_compact(guest, room, search):
    with (
        when_then(
            t'a {pg["Work Object"].low} is placed in the {pg["Verb"].low} slot',
            'the message names the term without dumping the glossary',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        path(guest, room, room)
    with then('the message is short and free of dataclass reprs'):
        message = str(excinfo.value)
        assert 'Glossary(terms=' not in message
        assert 'GlossaryTerm(' not in message
        assert len(message) < 300
        assert "'Room'" in message


@scenario(
    t'A kindless {pg["Term"].low} stays valid in any {pg["Slot"].low}',
    tags=['validation'],
)
def test_kindless_term_is_accepted_in_either_slot(g):
    with given(t'a {pg["Kindless"]} {pg["Term"]} declared with g(...)'):
        loyalty = g('loyalty points')
    with when(t'it is placed in a node {pg["Slot"].low} and a verb slot'):
        node_path = path(loyalty, 'given to', loyalty)
        verb_path = path(loyalty, loyalty, loyalty)
    with then('both paths construct, leaving the kind to inference'):
        assert len(node_path.parts) == 3
        assert len(verb_path.parts) == 3


@scenario(
    t'A non-handle {pg["Activity Part"].low} names its type',
    tags=['validation', 'diagnostics'],
)
def test_non_handle_part_names_its_type(guest, room):
    with (
        when_then(
            t'an int is passed where a {pg["Verb"].low} handle belongs',
            'a PytestGivenError names the offending type and the path',
        ),
        pytest.raises(PytestGivenError, match=r'must be a verb: got int'),
    ):
        path(guest, 42, room)


def test_misplaced_instances_name_their_canonical_term(g, tmp_path):
    # Plain, not narrated: one rule ("a misplaced part names its term") is
    # already covered above; these are its surface forms, and a scenario each
    # would be report noise.
    guest = g.actor('Guest')
    room = g.work_object('Room')
    search = g.verb('search')
    deferred = g('loyalty points')
    cases = [
        # Each puts one instance form in a slot its kind cannot fill.
        ((guest, guest('Alice'), room), r"'Guest' is declared an actor"),
        ((guest, search, search('searches for')), r"'search' is declared a verb"),
        ((guest, room('Suite'), room), r"'Room' is declared a work object"),
    ]
    for parts, expected in cases:
        with pytest.raises(PytestGivenError, match=expected):
            path(*parts)
    # A deferred instance carries no declared kind, so it stays valid anywhere.
    assert len(path(deferred('points'), deferred, deferred).parts) == 3
    # But a deferred handle from a kind_column glossary does carry one, so its
    # instance form is checked the same way an eager instance is.
    glossary_file = tmp_path / 'GLOSSARY.md'
    glossary_file.write_text(
        '| Term | Meaning | Kind |\n|---|---|---|\n| Room | A place | object |\n',
        encoding='utf-8',
    )
    fg = FileGlossary(glossary_file, kind_column='Kind')
    with pytest.raises(PytestGivenError, match=r"'Room' is declared a work object"):
        path(fg['Room'], fg['Room']('Suite'), fg['Room'])
