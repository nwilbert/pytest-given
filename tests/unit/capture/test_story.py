from pathlib import Path

import pytest

from pytest_given import PytestGivenError
from pytest_given.capture import source as source_mod
from pytest_given.capture.draft import draft
from pytest_given.capture.story import (
    activity,
    clear_story_registry,
    path,
    story,
)
from pytest_given.model import (
    Activity,
    ActivityPath,
    ActivityPlaceholder,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    StoryId,
)


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


def test_path_dispatches_inflected_verb_to_activity_term_ref_with_inflected_display(
    guest,
    search,
    room,
):
    p = path(guest, search('searches for'), room)
    assert p.parts[1] == ActivityTermRef(term_id=search.id, display='searches for')


def test_path_dispatches_draft_actor_to_activity_placeholder(guest, search, room):
    p = path(draft.actor('Concierge'), search, room)
    assert p.parts[0] == ActivityPlaceholder(kind='actor', text='Concierge')


def test_path_dispatches_draft_work_object_to_activity_placeholder(
    guest,
    search,
    room,
):
    p = path(guest, search, draft.work_object('loyalty bonus'))
    assert p.parts[2] == ActivityPlaceholder(kind='object', text='loyalty bonus')


def test_path_dispatches_draft_verb_to_activity_placeholder(guest, search, room):
    p = path(guest, draft.verb('redeems'), room)
    assert p.parts[1] == ActivityPlaceholder(kind='verb', text='redeems')


def test_path_dispatches_bare_string_to_activity_word(guest, search, room):
    p = path(guest, search, room, 'for', guest('Alice'))
    assert p.parts[3] == ActivityWord(text='for')


# --- Task 4.2: grammar validation ---


def test_path_rejects_path_with_fewer_than_three_parts(guest, search):
    with pytest.raises(PytestGivenError, match='incomplete'):
        path(guest, search)


def test_path_rejects_work_object_in_position_0(search, room):
    with pytest.raises(PytestGivenError, match=r'position 0.*actor'):
        path(room, search, room)


def test_path_rejects_verb_in_position_0(guest, search, room):
    with pytest.raises(PytestGivenError, match=r'position 0.*actor'):
        path(search, guest, room)


def test_path_rejects_bare_string_in_position_0(search, room):
    with pytest.raises(PytestGivenError, match=r'position 0.*actor'):
        path('Guest', search, room)


def test_path_rejects_draft_work_object_in_position_0(search, room):
    with pytest.raises(PytestGivenError, match=r'position 0.*actor'):
        path(draft.work_object('foo'), search, room)


def test_path_accepts_draft_actor_in_position_0(search, room):
    p = path(draft.actor('Concierge'), search, room)
    assert isinstance(p.parts[0], ActivityPlaceholder)


def test_path_rejects_actor_in_position_1(guest, room):
    with pytest.raises(PytestGivenError, match=r'position 1.*verb'):
        path(guest, guest, room)


def test_path_rejects_bare_string_in_position_1(guest, room):
    with pytest.raises(PytestGivenError, match=r'position 1.*verb'):
        path(guest, 'searches', room)


def test_path_rejects_work_object_in_position_1(guest, room):
    with pytest.raises(PytestGivenError, match=r'position 1.*verb'):
        path(guest, room, room)


def test_path_accepts_draft_verb_in_position_1(guest, room):
    p = path(guest, draft.verb('redeems'), room)
    assert isinstance(p.parts[1], ActivityPlaceholder)


def test_path_rejects_bare_string_in_position_2(guest, search):
    with pytest.raises(PytestGivenError, match=r'position 2.*noun'):
        path(guest, search, 'the room')


def test_path_rejects_verb_in_position_2(guest, search):
    with pytest.raises(PytestGivenError, match=r'position 2.*noun'):
        path(guest, search, search)


def test_path_accepts_actor_in_position_2(guest, search):
    p = path(guest, search, guest('Bob'))
    assert isinstance(p.parts[2], ActivityTermRef)


def test_path_accepts_free_form_parts_beyond_position_2(guest, search, room):
    p = path(guest, search, room, 'into', room('Inbox'), search('searches'))
    assert len(p.parts) == 6


# --- Task 4.3: activity() constructor ---


def test_activity_single_path_synthesizes_one_path(guest, search, room):
    a = activity(guest, search, room)
    assert isinstance(a, Activity)
    assert len(a.paths) == 1
    assert a.paths[0].parts[0].display == 'Guest'


def test_activity_multi_path_accepts_multiple_paths(guest, search, room):
    p1 = path(guest, search, room)
    p2 = path(guest('Bob'), search, room)
    a = activity(p1, p2)
    assert a.paths == (p1, p2)


def test_activity_mixing_parts_and_paths_raises(guest, search, room):
    p = path(guest, search, room)
    with pytest.raises(PytestGivenError, match='mix'):
        activity(p, guest, search, room)


def test_activity_id_defaults_to_zero_when_unspecified(guest, search, room):
    a = activity(guest, search, room)
    assert a.id == 0


def test_activity_explicit_id_overrides_default(guest, search, room):
    a = activity(guest, search, room, id=7)
    assert a.id == 7


def test_activity_explicit_id_zero_raises(guest, search, room):
    with pytest.raises(PytestGivenError, match=r'id=0.*reserved'):
        activity(guest, search, room, id=0)


def test_activity_explicit_id_with_multipath(guest, search, room):
    p1 = path(guest, search, room)
    p2 = path(guest('Bob'), search, room)
    a = activity(p1, p2, id=3)
    assert a.id == 3
    assert a.paths == (p1, p2)


# --- Task 4.4: story() constructor ---


def test_story_auto_numbers_activities_from_one(guest, search, room):
    s = story(
        'Book a Room',
        [activity(guest, search, room), activity(guest('Alice'), search, room)],
    )
    assert s.activities[0].id == 1
    assert s.activities[1].id == 2


def test_story_keeps_explicit_activity_ids(guest, search, room):
    s = story(
        'Book a Room',
        [activity(guest, search, room, id=10), activity(guest('Alice'), search, room)],
    )
    assert s.activities[0].id == 10
    assert s.activities[1].id == 1


def test_story_auto_numbering_skips_taken_explicit_ids(guest, search, room):
    """A mix of explicit and auto ids: auto picks must skip ids already used
    explicitly elsewhere in the story."""
    s = story(
        'Book a Room',
        [
            activity(guest, search, room, id=1),
            activity(guest('Alice'), search, room),
            activity(guest('Bob'), search, room, id=3),
            activity(guest('Cara'), search, room),
        ],
    )
    assert [a.id for a in s.activities] == [1, 2, 3, 4]


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


def test_story_rejects_duplicate_activity_ids(guest, search, room):
    with pytest.raises(PytestGivenError, match='duplicate activity id'):
        story(
            'Book',
            [
                activity(guest, search, room, id=1),
                activity(guest('Alice'), search, room, id=1),
            ],
        )


def test_story_derives_id_from_title():
    s = story('Book a Room', [])
    assert s.id == StoryId('book-a-room')


def test_story_rejects_two_glossaries(guest, search, room):
    other = Glossary()
    other_search = other.verb('search')
    with pytest.raises(PytestGivenError, match='spans multiple glossaries'):
        story(
            'Book',
            [activity(guest, search, room), activity(guest, other_search, room)],
        )


def test_story_with_only_drafts_has_empty_glossary_set():
    s = story(
        'Sketch',
        [
            activity(
                draft.actor('Concierge'),
                draft.verb('redeems'),
                draft.work_object('loyalty bonus'),
            )
        ],
    )
    assert s.activities[0].paths[0].parts[0].kind == 'actor'


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


def test_story_id_collision_raises_with_both_sites():
    story('Book a Room', [])
    with pytest.raises(PytestGivenError, match='already declared'):
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


# --- Task 4.6: top-level re-exports ---


def test_top_level_imports():
    from pytest_given import Glossary, activity, draft, path, story

    g = Glossary()
    guest = g.actor('Guest')
    search = g.verb('search')
    room = g.work_object('Room')
    p = path(guest, search, room)
    a = activity(p, path(draft.actor('Concierge'), search, room))
    s = story('Smoke', [a])
    assert s.title == 'Smoke'
