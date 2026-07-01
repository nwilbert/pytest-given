from pathlib import Path

import pytest

from pytest_given import PytestGivenError, given, scenario, then, when
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
    Glossary,
    StoryId,
)
from tests._vocab import pg, then_raises


@pytest.fixture(autouse=True)
def _reset_story_registry():
    from pytest_given.capture.glossary import clear_glossary_registry

    clear_story_registry()
    clear_glossary_registry()
    yield
    clear_story_registry()
    clear_glossary_registry()


@pytest.fixture
def g():
    return Glossary()


@pytest.fixture
def guest(g):
    return g.actor('Guest')


@pytest.fixture
def room(g):
    return g.work_object('Room')


@pytest.fixture
def search(g):
    return g.verb('search')


def test_path_dispatches_actor_to_activity_term_ref(guest, search, room):
    p = path(guest, search, room)
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
    'An inflected verb keeps its term identity but shows the inflection',
    tags=['story-grammar', 'happy-path'],
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
    'A bare string in a path becomes a connective word',
    tags=['story-grammar', 'happy-path'],
)
def test_path_dispatches_bare_string_to_activity_word(guest, search, room):
    with given(t'a {pg["Path"]} that includes a plain connective string'):
        pass
    with when(t'the {pg["Path"]} is built with a bare word between term nodes'):
        p = path(guest, search, room, 'for', guest('Alice'))
    with then(
        t'the bare word becomes an {pg["ActivityPart"]} word, not a {pg["Term ref"]}'
    ):
        assert p.parts[3] == ActivityWord(text='for')


# --- Task 4.2: grammar validation ---


@scenario(
    'A path needs at least an actor, a verb and a node',
    tags=['story-grammar', 'validation'],
)
def test_path_rejects_path_with_fewer_than_three_parts(guest, search):
    with then_raises(
        t'a {pg["Path"]} shorter than three parts is rejected',
        PytestGivenError,
        match=r'odd|length.*3|alternate',
    ):
        path(guest, search)


@scenario(
    'Position 0 of a path must be an actor',
    tags=['story-grammar', 'validation'],
)
def test_path_rejects_work_object_in_position_0(search, room):
    with then_raises(
        t'a {pg["Work Object"]} is rejected in the {pg["Actor"]} slot',
        PytestGivenError,
        match=r'position 0.*actor',
    ):
        path(room, search, room)


@scenario(
    'A verb cannot open a path',
    tags=['story-grammar', 'validation'],
)
def test_path_rejects_verb_in_position_0(guest, search, room):
    with then_raises(
        t'a {pg["Verb"]} may not open a path — position 0 is the {pg["Actor"]} slot',
        PytestGivenError,
        match=r'position 0.*actor',
    ):
        path(search, guest, room)


@scenario(
    'A bare string may stand in for the actor slot',
    tags=['story-grammar', 'happy-path'],
)
def test_path_allows_bare_string_in_position_0(search, room):
    with when(t'a bare string takes position 0 of a {pg["Path"]}'):
        p = path('Guest', search, room)
    with then(t'it is accepted as an {pg["ActivityPart"]} word'):
        assert p.parts[0] == ActivityWord(text='Guest')


@scenario(
    'Position 1 of a path must be a verb',
    tags=['story-grammar', 'validation'],
)
def test_path_rejects_actor_in_position_1(guest, room):
    with then_raises(
        t'an {pg["Actor"]} may not fill position 1 — that is the {pg["Verb"]} slot',
        PytestGivenError,
        match=r'position 1.*verb',
    ):
        path(guest, guest, room)


@scenario(
    'A work object cannot fill the verb slot',
    tags=['story-grammar', 'validation'],
)
def test_path_rejects_work_object_in_position_1(guest, room):
    with then_raises(
        t'a {pg["Work Object"]} in position 1 is rejected',
        PytestGivenError,
        match=r'position 1.*verb',
    ):
        path(guest, room, room)


@scenario(
    'Position 2 of a path must be a noun',
    tags=['story-grammar', 'validation'],
)
def test_path_rejects_verb_in_position_2(guest, search):
    with then_raises(
        t'a {pg["Verb"]} in the noun slot is rejected',
        PytestGivenError,
        match=r'position 2.*noun',
    ):
        path(guest, search, search)


@scenario(
    'A bare verb may sit between two real entity nodes',
    tags=['story-grammar', 'happy-path'],
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
    'A path may be fully bare words',
    tags=['story-grammar', 'happy-path'],
)
def test_path_allows_fully_bare_path():
    with when(t'a {pg["Path"]} is built from plain strings only'):
        p = path('Guest', 'receives', 'Confirmation')
    with then(t'every part is an {pg["ActivityPart"]} word'):
        assert [type(part) for part in p.parts] == [
            ActivityWord,
            ActivityWord,
            ActivityWord,
        ]


# --- Task 5: node/edge alternation ---


@scenario(
    'Node/edge alternation allows a trailing connective node',
    tags=['story-grammar', 'happy-path'],
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
    'A path may not end on a dangling edge',
    tags=['story-grammar', 'validation'],
)
def test_path_rejects_dangling_edge():
    with given(
        t'an {pg["Actor"]}, {pg["Verb"]} and {pg["Work Object"]} plus a connective'
    ):
        g = Glossary()
        actor = g.actor('Organizer')
        verb = g.verb('adds')
        booking = g.work_object('Booking')
    with then_raises(
        'a path ending on an edge (even length) is rejected',
        PytestGivenError,
        match=r'odd|dangling|ends',
    ):
        path(actor, verb, booking, 'to')


# --- Task 4.3: activity() constructor ---


@scenario(
    'A single-path activity synthesizes one path',
    tags=['story-grammar', 'happy-path'],
)
def test_activity_single_path_synthesizes_one_path(guest, search, room):
    with when(t'an {pg["Activity"]} is built from handles directly'):
        a = activity(guest, search, room)
    with then(t'it wraps a single {pg["Path"]}'):
        assert isinstance(a, Activity)
        assert len(a.paths) == 1
        assert a.paths[0].parts[0].display == 'Guest'


@scenario(
    'An activity may branch into multiple paths',
    tags=['story-grammar', 'happy-path'],
)
def test_activity_multi_path_accepts_multiple_paths(guest, search, room):
    with given(t'two alternate {pg["Path"]} branches'):
        p1 = path(guest, search, room)
        p2 = path(guest('Bob'), search, room)
    with when(t'they are combined into one {pg["Activity"]}'):
        a = activity(p1, p2)
    with then('the activity carries both paths'):
        assert a.paths == (p1, p2)


@scenario(
    'Mixing loose parts and prebuilt paths is rejected',
    tags=['story-grammar', 'validation'],
)
def test_activity_mixing_parts_and_paths_raises(guest, search, room):
    with given(t'a prebuilt {pg["Path"]}'):
        p = path(guest, search, room)
    with then_raises(
        'mixing it with loose handles in one activity raises',
        PytestGivenError,
        match='mix',
    ):
        activity(p, guest, search, room)


@scenario(
    'Activity id 0 is reserved',
    tags=['story-grammar', 'validation'],
)
def test_activity_explicit_id_zero_raises(guest, search, room):
    with then_raises(
        t'building an {pg["Activity"]} with explicit id=0 is rejected',
        PytestGivenError,
        match=r'id=0.*reserved',
    ):
        activity(guest, search, room, id=0)


# --- Task 4.4: story() constructor ---


@scenario(
    'A story auto-numbers its activities from one',
    tags=['story-grammar', 'happy-path'],
)
def test_story_auto_numbers_activities_from_one(guest, search, room):
    with when(t'a {pg["Story"]} is built from two {pg["Activity"]} rows'):
        s = story(
            'Book a Room',
            [activity(guest, search, room), activity(guest('Alice'), search, room)],
        )
    with then('the activities are numbered 1 and 2'):
        assert s.activities[0].id == 1
        assert s.activities[1].id == 2


@scenario(
    'Auto-numbering skips ids already taken explicitly',
    tags=['story-grammar', 'happy-path'],
)
def test_story_auto_numbering_skips_taken_explicit_ids(guest, search, room):
    with given(t'a mix of explicit and auto {pg["Activity"]} ids'):
        activities = [
            activity(guest, search, room, id=1),
            activity(guest('Alice'), search, room),
            activity(guest('Bob'), search, room, id=3),
            activity(guest('Cara'), search, room),
        ]
    with when(t'they are assembled into a {pg["Story"]}'):
        s = story('Book a Room', activities)
    with then('auto picks skip the ids already used explicitly'):
        assert [a.id for a in s.activities] == [1, 2, 3, 4]


@scenario(
    'Duplicate activity ids in a story are rejected',
    tags=['story-grammar', 'validation'],
)
def test_story_rejects_duplicate_activity_ids(guest, search, room):
    with then_raises(
        t'two {pg["Activity"]} rows sharing an explicit id are rejected',
        PytestGivenError,
        match='duplicate activity id',
    ):
        story(
            'Book',
            [
                activity(guest, search, room, id=1),
                activity(guest('Alice'), search, room, id=1),
            ],
        )


@scenario(
    'A story derives its id from its title',
    tags=['story-grammar', 'happy-path'],
)
def test_story_derives_id_from_title():
    with when(t'a {pg["Story"]} is built with a human title'):
        s = story('Book a Room', [])
    with then('its id is the slugified title'):
        assert s.id == StoryId('book-a-room')


@scenario(
    'A story may span only one glossary',
    tags=['story-grammar', 'validation'],
)
def test_story_rejects_two_glossaries(guest, search, room):
    with given('two activities that reach two different glossaries'):
        other = Glossary()
        other_search = other.verb('search')
    with then_raises(
        t'the {pg["Story"]} spanning both glossaries is rejected',
        PytestGivenError,
        match='spans multiple glossaries',
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
        source_mod._reset_rootdir()


# --- Task 4.5: story-id duplicate detection ---


@scenario(
    'Two stories with the same id collide',
    tags=['story-grammar', 'validation'],
)
def test_story_id_collision_raises_with_both_sites():
    with given(t'a {pg["Story"]} already declared under an id'):
        story('Book a Room', [])
    with then_raises(
        'declaring a second story with the same slug raises',
        PytestGivenError,
        match='already declared',
    ):
        story('book-a-room', [])


def test_story_id_collision_does_not_fire_after_registry_clear():
    story('Book', [])
    clear_story_registry()
    story('Book', [])


def test_path_records_single_glossary_id(guest, search, room):
    """Glossary identity is stashed as a frozenset of object-ids on the path so
    the single-glossary invariant can be enforced at story construction."""
    p = path(guest, search, room)
    assert getattr(p, '_glossary_ids', frozenset()) == frozenset({id(guest.glossary)})


def test_activity_unions_glossary_ids_across_paths(g, guest, search, room):
    # Two paths, same glossary — id set must dedup, not double-count.
    p1 = path(guest, search, room)
    p2 = path(guest('Alice'), search, room)
    a = activity(p1, p2)
    assert getattr(a, '_glossary_ids', frozenset()) == frozenset({id(g)})


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


def test_path_allows_second_verb_edge():
    g = Glossary()
    actor = g.actor('System')
    confirm = g.verb('confirms')
    booking = g.work_object('Booking')
    send = g.verb('sends')
    note = g.work_object('Confirmation')
    # actor verb object verb object  (len 5) — all five are term refs, no words
    result = path(actor, confirm, booking, send, note)
    assert [type(part) for part in result.parts] == [ActivityTermRef] * 5


def test_path_allows_bare_string_at_later_even_position(guest, search, room):
    # actor verb node connective bare-node — even index 4 is a bare word
    p = path(guest, search, room, 'into', 'Inbox')
    assert p.parts[4] == ActivityWord(text='Inbox')


def test_activity_id_defaults_to_zero_when_unspecified(guest, search, room):
    a = activity(guest, search, room)
    assert a.id == 0


def test_activity_explicit_id_overrides_default(guest, search, room):
    a = activity(guest, search, room, id=7)
    assert a.id == 7


def test_activity_explicit_id_with_multipath(guest, search, room):
    p1 = path(guest, search, room)
    p2 = path(guest('Bob'), search, room)
    a = activity(p1, p2, id=3)
    assert a.id == 3
    assert a.paths == (p1, p2)


def test_story_keeps_explicit_activity_ids(guest, search, room):
    s = story(
        'Book a Room',
        [activity(guest, search, room, id=10), activity(guest('Alice'), search, room)],
    )
    assert s.activities[0].id == 10
    assert s.activities[1].id == 1


def test_story_auto_numbering_skips_taken_ids_even_when_earlier_auto(
    guest, search, room
):
    """Explicit id=1 anywhere takes precedence over the auto counter."""
    s = story(
        'Book a Room',
        [
            activity(guest('Alice'), search, room),
            activity(guest, search, room, id=1),
        ],
    )
    assert [a.id for a in s.activities] == [2, 1]


# --- Task 4.6: top-level re-exports ---


def test_top_level_imports():
    from pytest_given import Glossary, activity, path, story

    g = Glossary()
    guest = g.actor('Guest')
    search = g.verb('search')
    room = g.work_object('Room')
    p = path(guest, search, room)
    a = activity(p)
    s = story('Smoke', [a])
    assert s.title == 'Smoke'
